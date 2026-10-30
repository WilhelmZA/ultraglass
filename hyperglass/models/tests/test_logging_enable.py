"""Test that `enable` switches syslog and webhook logging on and off."""

# Standard Library
import asyncio
from types import SimpleNamespace
from datetime import UTC, datetime

# Third Party
import httpx
import pytest

# Project
from hyperglass import log as log_module
from hyperglass.external import _base
from hyperglass.models.config.logging import Http, Syslog, Logging


@pytest.mark.parametrize(
    ("syslog", "expected"),
    (
        (None, []),
        (Syslog(host="log.example.com"), [("log.example.com", 514)]),
        (Syslog(host="log.example.com", port=1514, enable=True), [("log.example.com", 1514)]),
        (Syslog(host="log.example.com", enable=False), []),
    ),
)
def test_configure_syslog_checks_enable(monkeypatch, syslog, expected):
    calls = []
    monkeypatch.setattr(
        log_module, "enable_syslog_logging", lambda *, host, port: calls.append((host, port))
    )

    assert log_module.configure_syslog(syslog) is bool(expected)
    assert calls == expected


def test_enable_defaults_to_true():
    assert Syslog(host="log.example.com").enable is True
    assert Http(host="https://hooks.example.net/hook").enable is True


class _Query:
    def dict(self):
        return {"query_location": "lab-frr", "query_type": "bgp_route", "query_target": "1.1.1.1"}


def _send_webhook(monkeypatch, http: Http) -> list:
    # Project
    from hyperglass.api import tasks

    requests = []
    real_client = httpx.AsyncClient

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={})

    monkeypatch.setattr(
        _base.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    )

    async def network_info(host):
        return {host: {"prefix": "192.0.2.0/24", "asn": "64496"}}

    async def no_test(self):
        return True

    monkeypatch.setattr(tasks, "network_info", network_info)
    monkeypatch.setattr(_base.BaseExternal, "_atest", no_test)

    params = SimpleNamespace(logging=Logging(http=http))
    request = SimpleNamespace(
        headers={"user-agent": "pytest"}, client=SimpleNamespace(host="192.0.2.10")
    )
    asyncio.run(
        tasks.send_webhook(
            params=params, data=_Query(), request=request, timestamp=datetime.now(UTC)
        )
    )
    return requests


def test_webhook_enabled_sends(monkeypatch):
    requests = _send_webhook(monkeypatch, Http(host="https://hooks.example.net/hook"))

    assert len(requests) == 1


def test_webhook_disabled_sends_nothing(monkeypatch):
    requests = _send_webhook(monkeypatch, Http(host="https://hooks.example.net/hook", enable=False))

    assert requests == []
