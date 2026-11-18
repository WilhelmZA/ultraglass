"""Client address resolution behind reverse proxies and CDNs (#241)."""

# Third Party
import pytest
from litestar.testing import create_test_client
from litestar import Request
from litestar.datastructures import Address

# Project
from hyperglass.state import use_state
from hyperglass.models.config.web import Web, ClientIP, WebPublic
from hyperglass.models.config.params import Params

CDN = {"header": "CF-Connecting-IP"}
TRUSTED = {"trusted_proxies": ["10.0.0.0/8", "2001:db8:ffff::/48"]}


class ProxyRequest(Request):
    """Simulate a connection from an explicitly trusted proxy."""

    @property
    def client(self):
        """Return the connecting proxy's socket address."""
        return Address("10.0.0.2", 1234)


@pytest.mark.parametrize(
    "settings,headers,peer,expected",
    (
        # Default: ignore every forwarding header and use the socket peer.
        ({}, {}, "192.0.2.1", "192.0.2.1"),
        ({}, {"x-real-ip": "198.51.100.1"}, "10.0.0.2", "10.0.0.2"),
        ({}, {"x-forwarded-for": "198.51.100.1, 10.0.0.3"}, "10.0.0.2", "10.0.0.2"),
        (
            {},
            {"x-real-ip": "198.51.100.1", "x-forwarded-for": "198.51.100.9"},
            "10.0.0.2",
            "10.0.0.2",
        ),
        # An unset header ignores the CDN header.
        ({}, {"cf-connecting-ip": "203.0.113.7"}, "10.0.0.2", "10.0.0.2"),
        # A value that is not an address is skipped.
        ({}, {"x-real-ip": "not-an-ip"}, "10.0.0.2", "10.0.0.2"),
        ({}, {"x-forwarded-for": "unknown, 10.0.0.3"}, "10.0.0.2", "10.0.0.2"),
        # A configured header still requires an explicitly trusted peer.
        (
            CDN,
            {"cf-connecting-ip": "203.0.113.7", "x-real-ip": "172.70.0.1"},
            "10.0.0.2",
            "10.0.0.2",
        ),
        (CDN, {"cf-connecting-ip": "2001:db8::7"}, "10.0.0.2", "10.0.0.2"),
        (CDN, {"x-real-ip": "198.51.100.1"}, "10.0.0.2", "10.0.0.2"),
        (
            CDN,
            {"cf-connecting-ip": "junk", "x-real-ip": "198.51.100.1"},
            "10.0.0.2",
            "10.0.0.2",
        ),
        # Trusted proxies: headers from any other peer are ignored.
        (
            {**CDN, **TRUSTED},
            {"cf-connecting-ip": "203.0.113.7", "x-real-ip": "203.0.113.8"},
            "192.0.2.50",
            "192.0.2.50",
        ),
        ({**CDN, **TRUSTED}, {"cf-connecting-ip": "203.0.113.7"}, "10.0.0.2", "203.0.113.7"),
        ({**CDN, **TRUSTED}, {"cf-connecting-ip": "203.0.113.7"}, "::ffff:10.0.0.2", "203.0.113.7"),
        (
            {**CDN, **TRUSTED},
            {"cf-connecting-ip": "203.0.113.7"},
            "2001:db8:ffff::2",
            "203.0.113.7",
        ),
        ({**CDN, **TRUSTED}, {"cf-connecting-ip": "203.0.113.7"}, "testclient", "testclient"),
        # Trusted proxies: the client is the last X-Forwarded-For entry that is not a proxy,
        # so an entry the client forged is not used.
        (
            TRUSTED,
            {"x-forwarded-for": "192.0.2.99, 198.51.100.1, 10.0.0.3"},
            "10.0.0.2",
            "198.51.100.1",
        ),
        (TRUSTED, {"x-forwarded-for": "10.0.0.4, 10.0.0.3"}, "10.0.0.2", "10.0.0.2"),
        (TRUSTED, {"x-forwarded-for": "198.51.100.1, junk"}, "10.0.0.2", "10.0.0.2"),
        ({**CDN, **TRUSTED}, {"x-real-ip": "198.51.100.1"}, "10.0.0.2", "10.0.0.2"),
        (TRUSTED, {"x-real-ip": "198.51.100.1"}, "10.0.0.2", "10.0.0.2"),
        (TRUSTED, {"x-forwarded-for": "::ffff:198.51.100.1"}, "10.0.0.2", "198.51.100.1"),
    ),
)
def test_resolve_client_address(settings, headers, peer, expected):
    # Project
    from hyperglass.api.client_address import resolve_client_address

    assert resolve_client_address(headers, peer, ClientIP(**settings)) == expected


def test_resolve_client_address_without_peer():
    # Project
    from hyperglass.api.client_address import resolve_client_address

    assert resolve_client_address({}, None, ClientIP()) is None


def test_client_ip_option():
    assert Web().client_ip.header is None
    assert Web().client_ip.trusted_proxies == []
    assert ClientIP(header=" CF-Connecting-IP ").header == "cf-connecting-ip"
    assert ClientIP(header="").header is None
    with pytest.raises(ValueError):
        ClientIP(header="bad header:")
    with pytest.raises(ValueError):
        ClientIP(trusted_proxies=["not-a-network"])


def test_client_ip_is_not_sent_to_the_ui():
    params = Params(web={"client_ip": {**CDN, **TRUSTED}})

    assert "client_ip" not in params.frontend()["web"]
    assert "my_ip" in params.frontend()["web"]
    assert WebPublic.model_fields["client_ip"].exclude is True


def _configure(**client_ip):
    use_state().redis.set("params", Params(web={"client_ip": client_ip}))


def test_myip_uses_configured_header():
    # Project
    from hyperglass.api.routes import myip

    _configure(**CDN, **TRUSTED)
    headers = {"cf-connecting-ip": "1.1.1.1", "x-real-ip": "172.70.0.1"}
    with create_test_client([myip], request_class=ProxyRequest) as client:
        assert client.get("/api/myip", headers=headers).json() == {"ip": "1.1.1.1"}


def test_myip_ignores_headers_from_untrusted_peer():
    # Project
    from hyperglass.api.routes import myip

    _configure(**CDN, **TRUSTED)
    headers = {"cf-connecting-ip": "203.0.113.7", "x-real-ip": "203.0.113.8"}
    with create_test_client([myip]) as client:
        # The test client's peer is not an address in a trusted network.
        assert client.get("/api/myip", headers=headers).json() == {"ip": None}


def test_dns_rate_limit_is_per_configured_header():
    # Project
    from hyperglass.api.routes import dns

    use_state().redis.set(
        "params", Params(web={"client_ip": {**CDN, **TRUSTED}, "dns_provider": {"name": "server"}})
    )
    with create_test_client([dns], request_class=ProxyRequest) as client:

        def get(address):
            return client.get(
                "/api/dns",
                params={"name": "bad name"},
                headers={"cf-connecting-ip": address, "x-real-ip": "172.70.0.1"},
            ).status_code

        assert [get("203.0.113.7") for _ in range(121)][-1] == 429
        assert get("203.0.113.8") == 200


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "settings,headers,peer,expected",
    [
        ({**CDN, **TRUSTED}, {"cf-connecting-ip": "1.1.1.1"}, "10.0.0.2", "1.1.1.1"),
        (
            {"header": "X-Real-IP", "trusted_proxies": ["127.0.0.1/32", "::1/128"]},
            {"x-real-ip": "1.1.1.1", "x-forwarded-for": "8.8.8.8"},
            "127.0.0.1",
            "1.1.1.1",
        ),
        ({}, {"x-real-ip": "1.1.1.1"}, "127.0.0.1", "127.0.0.1"),
        (
            {"header": "X-Real-IP", "trusted_proxies": ["172.18.0.1/32"]},
            {"x-real-ip": "1.1.1.1", "x-forwarded-for": "8.8.8.8"},
            "172.18.0.1",
            "1.1.1.1",
        ),
        ({**CDN, **TRUSTED}, {"cf-connecting-ip": "8.8.8.8"}, "1.1.1.1", "1.1.1.1"),
    ],
)
async def test_webhook_source_is_the_resolved_client(
    monkeypatch, settings, headers, peer, expected
):
    # Project
    from hyperglass.api import tasks

    sent = {}

    class Hook:
        def __init__(self, config):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def send(self, query):
            sent.update(query)

    request = type(
        "Request",
        (),
        {
            "headers": headers,
            "client": type("Client", (), {"host": peer})(),
        },
    )()

    class Data:
        def dict(self):
            return {}

    async def network_info(host):
        return {host: {"asn": "64500"}}

    monkeypatch.setattr(tasks, "Webhook", Hook)
    monkeypatch.setattr(tasks, "network_info", network_info)
    params = Params(
        logging={"http": {"host": "https://hook.example.com"}},
        web={"client_ip": settings},
    )

    await tasks.send_webhook(params=params, data=Data(), request=request, timestamp=None)

    assert sent["source"] == expected
    assert sent["network"] == {"asn": "64500"}
