"""Exercise optional lookup boundaries through real request and Redis handling."""

# Standard Library
import asyncio
import importlib
import json
import socket
from unittest.mock import AsyncMock, Mock

# Third Party
import httpx
import pytest
from litestar.testing import create_test_client
from litestar.exceptions import HTTPException
from redis.exceptions import ConnectionError as RedisConnectionError

# Project
from hyperglass.state import use_state
from hyperglass.models.config.params import Params
from hyperglass.util.tests.test_client_address import ProxyRequest, TRUSTED


def configure(**web):
    use_state().redis.set("params", Params(web=web))


@pytest.fixture
def lookups(monkeypatch):
    from hyperglass.api import auxiliary

    dns = AsyncMock(return_value={"Status": 0, "Answer": [{"type": 1, "data": "1.1.1.1"}]})
    asns = AsyncMock(return_value={"13335": {"name": "Cloudflare", "country": "US"}})
    monkeypatch.setattr(auxiliary, "_dns_query", dns)
    monkeypatch.setattr(auxiliary, "_asn_query", asns)
    return dns, asns


def test_disabled_routes_do_no_work(lookups):
    from hyperglass.api.routes import dns, aspath_enrich

    with create_test_client([dns, aspath_enrich]) as client:
        assert client.get("/api/dns", params={"name": "host.internal"}).status_code == 404
        assert client.post("/api/aspath/enrich", json={"as_path": [13335]}).status_code == 404
    for lookup in lookups:
        lookup.assert_not_called()


@pytest.mark.parametrize("enabled", [False, True])
def test_route_registration_is_opt_in(monkeypatch, enabled):
    from hyperglass.settings import Settings

    monkeypatch.setattr(Settings, "disable_ui", True)
    configure(
        dns_provider={"name": "server" if enabled else "cloudflare"}, aspath_enrichment=enabled
    )
    api = importlib.reload(importlib.import_module("hyperglass.api"))
    paths = {route.path for route in api.app.routes}
    assert ("/api/dns" in paths) is enabled
    assert ("/api/aspath/enrich" in paths) is enabled
    configure()
    importlib.reload(api)


def test_runtime_disable_blocks_registered_routes(lookups):
    from hyperglass.api.routes import dns, aspath_enrich

    configure(dns_provider={"name": "server"}, aspath_enrichment=True)
    with create_test_client([dns, aspath_enrich]) as client:
        configure()
        assert client.get("/api/dns", params={"name": "example.com"}).status_code == 404
        assert client.post("/api/aspath/enrich", json={"as_path": [13335]}).status_code == 404
    assert not any(lookup.called for lookup in lookups)


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.1.2.3",
        "172.16.0.1",
        "192.168.0.1",
        "169.254.169.254",
        "100.64.0.1",
        "0.0.0.0",  # noqa: S104 - reject this DNS answer, never bind to it
        "224.0.0.1",
        "::1",
        "::",
        "fc00::1",
        "fe80::1",
        "ff02::1",
        "::ffff:127.0.0.1",
        "64:ff9b::a00:1",
        "2002:7f00:1::",
    ],
)
def test_dns_never_returns_private_or_special_answers(lookups, address):
    from hyperglass.api.routes import dns

    code, record = (28, "AAAA") if ":" in address else (1, "A")
    lookups[0].return_value = {
        "Status": 0,
        "Answer": [{"type": code, "data": address}, {"type": code, "data": "1.1.1.1"}],
    }
    configure(dns_provider={"name": "server"})
    with create_test_client([dns]) as client:
        result = client.get("/api/dns", params={"name": "public.example", "type": record}).json()
    assert result["Status"] == 3
    assert result["Answer"] == []


@pytest.mark.parametrize("name", ["router", "router.local", "host.internal", "host.home.arpa"])
def test_internal_names_do_not_reach_resolver(lookups, name):
    from hyperglass.api.routes import dns

    configure(dns_provider={"name": "server"})
    with create_test_client([dns]) as client:
        assert client.get("/api/dns", params={"name": name}).json()["Status"] == 1
    lookups[0].assert_not_called()


@pytest.mark.asyncio
async def test_dns_transport_is_public_and_has_no_system_resolver(monkeypatch):
    from hyperglass.api import auxiliary

    def forbidden(*args, **kwargs):
        raise AssertionError("System DNS must not be used")

    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    real_client = httpx.AsyncClient
    calls = []

    def transport(request):
        calls.append(request)
        return httpx.Response(200, json={"Status": 0, "Answer": []})

    def factory(**kwargs):
        assert kwargs == {
            "trust_env": False,
            "follow_redirects": False,
            "timeout": auxiliary.LOOKUP_TIMEOUT,
        }
        return real_client(transport=httpx.MockTransport(transport), **kwargs)

    monkeypatch.setattr(auxiliary.httpx, "AsyncClient", factory)
    await auxiliary._dns_query("example.com", "A")
    assert str(calls[0].url).startswith("https://1.1.1.1/dns-query?")
    assert calls[0].url.params["name"] == "example.com."


@pytest.mark.parametrize(
    "as_path",
    [
        [],
        [0],
        [4294967296],
        [True],
        [1.5],
        [-1],
        ["AS13335"],
        ["1\nend"],
        ["9" * 100],
        "13335",
        {"13335": 1},
        [13335] * 65,
    ],
)
def test_invalid_asns_never_start_outbound_work(lookups, as_path):
    from hyperglass.api.routes import aspath_enrich

    configure(aspath_enrichment=True)
    with create_test_client([aspath_enrich]) as client:
        assert client.post("/api/aspath/enrich", json={"as_path": as_path}).status_code == 400
    lookups[1].assert_not_called()


@pytest.mark.asyncio
async def test_dns_cache_obeys_upstream_ttl(monkeypatch):
    from hyperglass.api import auxiliary

    lookup = AsyncMock(
        return_value={"Status": 0, "Answer": [{"type": 1, "data": "1.1.1.1", "TTL": 5}]}
    )
    monkeypatch.setattr(auxiliary, "_dns_query", lookup)
    first = await auxiliary.resolve_public_dns("EXAMPLE.COM.", "A")
    second = await auxiliary.resolve_public_dns("example.com", "A")
    assert first == second
    assert first["Answer"][0]["TTL"] == 5
    assert 0 < use_state("redis").instance.ttl(auxiliary._key("dns:cache:A:example.com")) <= 5
    lookup.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("status,body", [(302, b""), (200, b"x" * 16385)])
async def test_dns_transport_rejects_redirects_and_large_responses(monkeypatch, status, body):
    from hyperglass.api import auxiliary

    real_client = httpx.AsyncClient
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(status, content=body, headers={"Location": "http://127.0.0.1"})

    monkeypatch.setattr(
        auxiliary.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(respond), **kwargs),
    )
    result = await auxiliary.resolve_public_dns("example.com", "A")
    assert result["Status"] == 2
    assert result["Answer"] == []
    assert len(requests) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("oversized", [False, True])
async def test_asn_transport_is_bounded_and_closes_socket(monkeypatch, oversized):
    from hyperglass.api import auxiliary

    response = b"13335 | AS13335 | NA | US | ARIN | 2010-01-01 | Cloudflare\n"
    chunks = [b"x" * 4096] * 17 if oversized else [response, b""]
    reader = Mock(read=AsyncMock(side_effect=chunks))
    writer = Mock(drain=AsyncMock())
    connect = AsyncMock(return_value=(reader, writer))
    monkeypatch.setattr(auxiliary.asyncio, "open_connection", connect)
    if oversized:
        with pytest.raises(ValueError, match="too large"):
            await auxiliary._asn_query(["13335"])
    else:
        assert await auxiliary._asn_query(["13335"]) == {
            "13335": {"name": "Cloudflare", "country": "US"}
        }
    connect.assert_awaited_once_with("bgp.tools", 43)
    writer.write.assert_called_once_with(b"begin\nAS13335\nend\n")
    writer.close.assert_called_once()


def test_asn_body_limit_and_deduplication(lookups):
    from hyperglass.api.routes import aspath_enrich

    configure(aspath_enrichment=True)
    with create_test_client([aspath_enrich]) as client:
        response = client.post("/api/aspath/enrich", json={"as_path": [13335, "013335", "13335"]})
        assert response.status_code == 201
        assert response.json()["asn_organizations"]["13335"]["name"] == "Cloudflare"
        oversized = client.post(
            "/api/aspath/enrich",
            content=json.dumps({"as_path": ["1" * 9000]}),
            headers={"Content-Type": "application/json"},
        )
        assert oversized.status_code == 413
    lookups[1].assert_awaited_once_with(["13335"])


def test_cache_and_quota_are_shared_between_apps(lookups):
    from hyperglass.api.routes import aspath_enrich

    configure(aspath_enrichment=True)
    with (
        create_test_client([aspath_enrich]) as first,
        create_test_client([aspath_enrich]) as second,
    ):
        for index in range(30):
            client = first if index % 2 else second
            assert client.post("/api/aspath/enrich", json={"as_path": [13335]}).status_code == 201
        denied = second.post(
            "/api/aspath/enrich",
            json={"as_path": [13335]},
            headers={"X-Real-IP": "8.8.8.8", "X-Forwarded-For": "9.9.9.9"},
        )
        assert denied.status_code == 429
    lookups[1].assert_awaited_once()


def test_global_quota_bounds_many_trusted_clients(lookups):
    from hyperglass.api.routes import aspath_enrich

    configure(aspath_enrichment=True, client_ip=TRUSTED)
    with create_test_client([aspath_enrich], request_class=ProxyRequest) as client:
        for index in range(120):
            response = client.post(
                "/api/aspath/enrich",
                json={"as_path": [13335]},
                headers={"X-Forwarded-For": f"192.0.2.{index + 1}"},
            )
            assert response.status_code == 201
        assert (
            client.post(
                "/api/aspath/enrich",
                json={"as_path": [13335]},
                headers={"X-Forwarded-For": "198.51.100.1"},
            ).status_code
            == 429
        )


@pytest.mark.asyncio
async def test_concurrency_is_shared_and_released():
    from hyperglass.api import auxiliary

    slots = [auxiliary._outbound_slot() for _ in range(auxiliary.MAX_CONCURRENT)]
    try:
        for slot in slots:
            await slot.__aenter__()
        with pytest.raises(HTTPException, match="busy"):
            async with auxiliary._outbound_slot():
                pytest.fail("Over capacity")
    finally:
        for slot in slots:
            await slot.__aexit__(None, None, None)
    assert use_state("redis").instance.zcard(auxiliary._key("outbound")) == 0


@pytest.mark.asyncio
async def test_deadline_cancels_work_and_releases_slot(monkeypatch):
    from hyperglass.api import auxiliary

    cancelled = asyncio.Event()

    async def slow(asns):
        try:
            await asyncio.sleep(10)
        finally:
            cancelled.set()

    monkeypatch.setattr(auxiliary, "_asn_query", slow)
    # Keep the lease duration an integer while making the request deadline short.
    real_wait = asyncio.wait_for

    async def quick_wait(task, timeout):
        return await real_wait(task, 0.01)

    monkeypatch.setattr(auxiliary.asyncio, "wait_for", quick_wait)
    with pytest.raises(HTTPException, match="failed"):
        await auxiliary.enrich_public_asns(["13335"])
    assert cancelled.is_set()
    assert use_state("redis").instance.zcard(auxiliary._key("outbound")) == 0


def test_redis_failure_denies_outbound_work(monkeypatch, lookups):
    from hyperglass.api.routes import aspath_enrich

    configure(aspath_enrichment=True)

    def fail(*args, **kwargs):
        raise RedisConnectionError("offline")

    monkeypatch.setattr(use_state("redis").instance, "eval", fail)
    with create_test_client([aspath_enrich]) as client:
        assert client.post("/api/aspath/enrich", json={"as_path": [13335]}).status_code == 503
    lookups[1].assert_not_called()


def test_launcher_preserves_peer_even_with_proxy_environment(monkeypatch):
    from hyperglass.settings import Settings
    from hyperglass import plugins

    monkeypatch.setattr(Settings, "disable_ui", True)
    from hyperglass import main

    run = Mock()
    monkeypatch.setenv("FORWARDED_ALLOW_IPS", "*")
    monkeypatch.setattr(plugins, "register_all_plugins", Mock())
    monkeypatch.setattr(main.uvicorn, "run", run)
    main.start(log_level="ERROR", workers=1)
    assert run.call_args.kwargs["proxy_headers"] is False
