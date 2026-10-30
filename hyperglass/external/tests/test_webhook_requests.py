"""Capture outgoing webhook requests with a mocked HTTP transport."""

# Standard Library
import ssl
import base64
import asyncio
from datetime import UTC, datetime

# Third Party
import httpx
import pytest

# Project
from hyperglass.constants import __version__
from hyperglass.models.config.logging import Http

# Local
from .. import _base
from .._base import BaseExternal
from ..webhooks import Webhook

QUERY = {
    "query_location": "lab-frr",
    "query_type": "bgp_route",
    "query_target": "1.1.1.1",
    "headers": {"user-agent": "pytest"},
    "source": "192.0.2.10",
    "network": {"prefix": "192.0.2.0/24", "asn": "64496"},
    "timestamp": datetime.now(UTC),
}


@pytest.fixture
def capture(monkeypatch):
    """Route every BaseExternal client through a mock transport and record the traffic."""
    captured = {"requests": [], "clients": []}
    real_client = httpx.AsyncClient

    def handler(request: httpx.Request) -> httpx.Response:
        captured["requests"].append(request)
        return httpx.Response(200, json={})

    def client_factory(**kwargs):
        captured["clients"].append(kwargs)
        return real_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(_base.httpx, "AsyncClient", client_factory)
    return captured


def _send(config: Http) -> None:
    async def run():
        hook = Webhook(config)
        await hook.send(query=QUERY)

    asyncio.run(run())


def test_generic_sends_headers_params_and_api_key(capture):
    config = Http(
        provider="generic",
        host="https://hooks.example.net:8443/hook",
        headers={"x-custom": "one", "x-number": 2},
        params={"source": "ultraglass"},
        authentication={"mode": "api_key", "header": "x-api-key", "password": "secret-key"},
    )
    _send(config)

    request = capture["requests"][0]
    assert request.method == "POST"
    assert str(request.url) == "https://hooks.example.net:8443/hook?source=ultraglass"
    assert request.headers["x-custom"] == "one"
    assert request.headers["x-number"] == "2"
    assert request.headers["x-api-key"] == "secret-key"
    assert request.headers["user-agent"] == f"hyperglass/{__version__}"
    assert "authorization" not in request.headers


def test_generic_sends_basic_auth(capture):
    config = Http(
        provider="generic",
        host="https://hooks.example.net/hook",
        authentication={"mode": "basic", "username": "glass", "password": "pass"},
    )
    _send(config)

    request = capture["requests"][0]
    expected = base64.b64encode(b"glass:pass").decode()
    assert request.headers["authorization"] == f"Basic {expected}"
    assert "x-api-key" not in request.headers


def test_generic_without_authentication(capture):
    _send(Http(provider="generic", host="https://hooks.example.net/hook"))

    request = capture["requests"][0]
    assert "authorization" not in request.headers
    assert "x-api-key" not in request.headers


@pytest.mark.parametrize("verify_ssl", (True, False))
def test_generic_applies_verify_ssl_and_timeout(capture, verify_ssl):
    config = Http(
        provider="generic",
        host="https://hooks.example.net/hook",
        verify_ssl=verify_ssl,
        timeout=2.5,
    )
    _send(config)

    client = capture["clients"][0]
    expected_mode = ssl.CERT_REQUIRED if verify_ssl else ssl.CERT_NONE
    assert client["verify"].verify_mode == expected_mode
    assert client["timeout"] == 2.5
    assert len(capture["requests"]) == 1


def test_config_keeps_headers_unchanged():
    config = Http(
        provider="generic",
        host="https://hooks.example.net/hook",
        headers={"x-custom": "one"},
        authentication={"mode": "api_key", "password": "secret-key"},
    )

    assert config.headers == {"x-custom": "one"}
    assert config.request_headers()["x-api-key"] == "secret-key"


def test_base_external_without_headers_keeps_default_user_agent(capture):
    async def run():
        client = BaseExternal(base_url="https://api.example.net")
        await client._apost("/graphql", data={"query": "x"})

    asyncio.run(run())

    request = capture["requests"][0]
    assert request.headers["user-agent"] == f"hyperglass/{__version__}"
    assert "authorization" not in request.headers
    assert capture["clients"][0]["timeout"] == 10
    assert "auth" not in capture["clients"][0]
