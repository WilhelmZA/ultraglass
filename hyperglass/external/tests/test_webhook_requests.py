"""Capture outgoing webhook requests with a mocked HTTP transport."""

# Standard Library
import ssl
import json
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


TEAMS_WORKFLOW_URL = (
    "https://prod-01.westeurope.logic.azure.com:443/workflows/abc123/triggers/manual/paths/invoke"
    "?api-version=2016-06-01&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=s1gn4ture"
)


@pytest.mark.parametrize(
    ("provider", "host", "expected_host", "expected_path"),
    (
        ("generic", "https://relay.example.net:8443/hook", "relay.example.net", "/hook"),
        (
            "slack",
            "https://hooks.slack.com/services/T0/B0/XYZ",
            "hooks.slack.com",
            "/services/T0/B0/XYZ",
        ),
        (
            "slack",
            "https://relay.example.net/services/T0/B0/XYZ",
            "relay.example.net",
            "/services/T0/B0/XYZ",
        ),
        (
            "msteams",
            "https://contoso.webhook.office.com/webhookb2/abc/IncomingWebhook/def",
            "contoso.webhook.office.com",
            "/webhookb2/abc/IncomingWebhook/def",
        ),
        (
            "msteams",
            TEAMS_WORKFLOW_URL,
            "prod-01.westeurope.logic.azure.com",
            "/workflows/abc123/triggers/manual/paths/invoke",
        ),
    ),
)
def test_provider_uses_configured_host(capture, provider, host, expected_host, expected_path):
    _send(Http(provider=provider, host=host))

    request = capture["requests"][0]
    assert request.url.host == expected_host
    assert request.url.path == expected_path


def test_msteams_keeps_workflow_query_string(capture):
    _send(Http(provider="msteams", host=TEAMS_WORKFLOW_URL, params={"extra": "1"}))

    params = capture["requests"][0].url.params
    assert params["api-version"] == "2016-06-01"
    assert params["sp"] == "/triggers/manual/run"
    assert params["sv"] == "1.0"
    assert params["sig"] == "s1gn4ture"
    assert params["extra"] == "1"


def test_msteams_sends_adaptive_card(capture):
    _send(Http(provider="msteams", host=TEAMS_WORKFLOW_URL))

    body = json.loads(capture["requests"][0].content)
    assert body["type"] == "message"
    attachment = body["attachments"][0]
    assert attachment["contentType"] == "application/vnd.microsoft.card.adaptive"
    card = attachment["content"]
    assert card["type"] == "AdaptiveCard"
    facts = {
        f["title"]: f["value"] for b in card["body"] if b["type"] == "FactSet" for f in b["facts"]
    }
    assert facts["Query Location"] == "lab-frr"
    assert facts["Query Target"] == "`1.1.1.1`"
    assert facts["ASN"] == "`64496`"
    assert all(isinstance(v, str) for v in facts.values())


def test_slack_sends_blocks(capture):
    _send(Http(provider="slack", host="https://hooks.slack.com/services/T0/B0/XYZ"))

    body = json.loads(capture["requests"][0].content)
    assert body["blocks"]
    assert body["text"]


@pytest.mark.parametrize("provider", ("generic", "msteams", "slack"))
@pytest.mark.parametrize("mode", ("none", "basic", "api_key"))
def test_provider_auth_modes(capture, provider, mode):
    kwargs = {}
    if mode == "basic":
        kwargs["authentication"] = {"mode": "basic", "username": "glass", "password": "pass"}
    elif mode == "api_key":
        kwargs["authentication"] = {"mode": "api_key", "header": "x-hook-key", "password": "k3y"}
    config = Http(
        provider=provider,
        host="https://hooks.example.net/hook",
        headers={"x-custom": "one"},
        verify_ssl=False,
        timeout=3,
        **kwargs,
    )
    _send(config)

    request = capture["requests"][0]
    client = capture["clients"][0]
    assert request.headers["x-custom"] == "one"
    assert client["verify"].verify_mode == ssl.CERT_NONE
    assert client["timeout"] == 3
    if mode == "basic":
        expected = base64.b64encode(b"glass:pass").decode()
        assert request.headers["authorization"] == f"Basic {expected}"
    else:
        assert "authorization" not in request.headers
    if mode == "api_key":
        assert request.headers["x-hook-key"] == "k3y"
    else:
        assert "x-hook-key" not in request.headers
