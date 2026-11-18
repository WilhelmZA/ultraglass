"""Server-side DNS resolution endpoint (#48)."""

# Standard Library

# Third Party
import pytest
from litestar.testing import create_test_client


@pytest.fixture
def client(monkeypatch):
    # Project
    from hyperglass.api.routes import dns
    from hyperglass.api import auxiliary
    from hyperglass.state import use_state
    from hyperglass.models.config.params import Params

    async def lookup(host, record_type):
        if host == "missing.example.com":
            return {"Status": 3, "Answer": []}
        code, address = (28, "2606:4700::1111") if record_type == "AAAA" else (1, "1.1.1.1")
        return {"Status": 0, "Answer": [{"type": code, "data": address}] * 2}

    monkeypatch.setattr(auxiliary, "_dns_query", lookup)
    use_state().redis.set("params", Params(web={"dns_provider": {"name": "server"}}))
    with create_test_client([dns]) as test_client:
        yield test_client


@pytest.mark.parametrize(
    "record,code,address", (("A", 1, "1.1.1.1"), ("AAAA", 28, "2606:4700::1111"))
)
def test_dns_returns_doh_json(client, record, code, address):
    body = client.get("/api/dns", params={"name": "one.one.one.one", "type": record}).json()

    assert body == {
        "Status": 0,
        "Question": [{"name": "one.one.one.one", "type": code}],
        "Answer": [{"name": "one.one.one.one", "type": code, "TTL": 60, "data": address}],
    }


def test_dns_not_found(client):
    body = client.get("/api/dns", params={"name": "missing.example.com", "type": "A"}).json()

    assert body["Status"] == 3
    assert body["Answer"] == []


@pytest.mark.parametrize("name,record", (("1.1.1.1", "A"), ("bad name.com", "A"), ("a.com", "MX")))
def test_dns_rejects_invalid_input(client, name, record):
    assert client.get("/api/dns", params={"name": name, "type": record}).json()["Status"] == 1


def test_dns_is_rate_limited(client):
    statuses = [
        client.get("/api/dns", params={"name": "one.one.one.one"}).status_code for _ in range(121)
    ]

    assert statuses[:120] == [200] * 120
    assert statuses[120] == 429


def test_untrusted_headers_cannot_reset_dns_limit(client):
    for _ in range(120):
        client.get(
            "/api/dns",
            params={"name": "one.one.one.one"},
            headers={"x-forwarded-for": "198.51.100.1, 10.0.0.2"},
        )

    limited = client.get(
        "/api/dns",
        params={"name": "one.one.one.one"},
        headers={"x-forwarded-for": "198.51.100.1, 10.0.0.2"},
    )
    other = client.get(
        "/api/dns",
        params={"name": "one.one.one.one"},
        headers={"x-forwarded-for": "198.51.100.2, 10.0.0.2"},
    )

    assert limited.status_code == 429
    assert other.status_code == 429


def test_server_dns_provider():
    # Project
    from hyperglass.models.config.web import DnsOverHttps

    assert DnsOverHttps(name="server").url == "/api/dns"


def test_server_dns_message():
    # Project
    from hyperglass.models.config.web import Web

    assert Web(dns_provider={"name": "server"}).text.fqdn_message.startswith("Ultraglass")
    assert Web().text.fqdn_message.startswith("Your browser")
    custom = Web(dns_provider={"name": "server"}, text={"fqdn_message": "{fqdn} is"})
    assert custom.text.fqdn_message == "{fqdn} is"
