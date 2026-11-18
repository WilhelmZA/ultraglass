"""Server-side My IP endpoint (#49)."""

# Third Party
import pytest
from litestar.testing import create_test_client
from litestar import Request
from litestar.datastructures import Address
from hyperglass.util.tests.test_client_address import ProxyRequest, TRUSTED
from hyperglass.state import use_state
from hyperglass.models.config.params import Params


@pytest.fixture
def client():
    # Project
    from hyperglass.api.routes import myip

    with create_test_client([myip], request_class=ProxyRequest) as test_client:
        yield test_client


@pytest.mark.parametrize(
    "headers,family,expected",
    (
        ({"x-real-ip": "1.1.1.1"}, 4, "1.1.1.1"),
        ({"x-real-ip": "1.1.1.1"}, 6, None),
        ({"x-forwarded-for": "2606:4700::1111, 10.0.0.1"}, 6, "2606:4700::1111"),
        ({"x-forwarded-for": "::ffff:1.1.1.1"}, 4, "1.1.1.1"),
        ({"x-real-ip": "not-an-ip"}, 4, None),
        ({"x-real-ip": "127.0.0.1"}, 4, None),
        ({"x-real-ip": "10.0.0.1"}, 4, None),
        ({"x-real-ip": "192.168.0.1"}, 4, None),
        ({"x-real-ip": "169.254.169.254"}, 4, None),
        ({"x-real-ip": "100.64.0.1"}, 4, None),
        ({"x-real-ip": "224.0.0.1"}, 4, None),
        ({"x-real-ip": "::1"}, 6, None),
        ({"x-real-ip": "fe80::1"}, 6, None),
        ({"x-real-ip": "fc00::1"}, 6, None),
        ({"x-real-ip": "ff02::1"}, 6, None),
        ({"x-real-ip": "::ffff:127.0.0.1"}, 4, None),
    ),
)
def test_myip(client, headers, family, expected):
    use_state().redis.set(
        "params",
        Params(
            web={
                "client_ip": {
                    **TRUSTED,
                    "header": "x-real-ip" if "x-real-ip" in headers else None,
                }
            }
        ),
    )
    assert client.get("/api/myip", params={"family": family}, headers=headers).json() == {
        "ip": expected
    }


@pytest.mark.parametrize(
    "peer,settings,expected",
    [
        ("127.0.0.1", {}, None),
        ("::1", {}, None),
        ("10.0.0.2", {}, None),
        ("172.18.0.1", {}, None),
        ("1.1.1.1", {}, "1.1.1.1"),
        (
            "172.18.0.1",
            {"header": "X-Real-IP", "trusted_proxies": ["172.18.0.1/32"]},
            "8.8.8.8",
        ),
        (
            "1.1.1.1",
            {"header": "X-Real-IP", "trusted_proxies": ["172.18.0.1/32"]},
            "1.1.1.1",
        ),
        (
            "127.0.0.1",
            {"header": "X-Real-IP", "trusted_proxies": ["127.0.0.1/32"]},
            "8.8.8.8",
        ),
        (
            "::1",
            {"header": "X-Real-IP", "trusted_proxies": ["::1/128"]},
            "8.8.8.8",
        ),
    ],
)
def test_proxy_setup_and_direct_client(peer, settings, expected):
    from hyperglass.api.routes import myip

    class PeerRequest(Request):
        @property
        def client(self):
            """Return the actual connecting peer."""
            return Address(peer, 1234)

    use_state().redis.set("params", Params(web={"client_ip": settings}))
    with create_test_client([myip], request_class=PeerRequest) as test_client:
        result = test_client.get(
            "/api/myip",
            headers={"X-Real-IP": "8.8.8.8", "X-Forwarded-For": "9.9.9.9"},
        )
        assert result.json() == {"ip": expected}


def test_my_ip_option():
    # Project
    from hyperglass.models.config.web import Web

    # Server detection is the default, so no third party is contacted (#90).
    assert Web().my_ip == "server"
    assert Web(my_ip="external").my_ip == "external"
    assert Web(my_ip="off").my_ip == "off"
