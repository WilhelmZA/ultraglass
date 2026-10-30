"""Batch RPKI validation dedupes, bounds concurrency and reuses one session (#134)."""

# Standard Library
import time
import threading
from unittest.mock import Mock

# Third Party
import pytest

# Project
from hyperglass.external import rpki
from hyperglass.models.data import bgp_route
from hyperglass.models.config.params import Params

PAIRS = [(f"1.1.{n}.0/24", 13335) for n in range(12)]


def _graphql(state="valid"):
    return {"data": {"validation": {"state": state}}}


@pytest.fixture
def session_test(monkeypatch):
    """Count connection tests instead of opening sockets."""
    test = Mock(return_value=True)
    monkeypatch.setattr(rpki.BaseExternal, "_test", test)
    return test


def test_dedupes_and_caches(monkeypatch, session_test):
    post = Mock(return_value=_graphql())
    monkeypatch.setattr(rpki.BaseExternal, "_post", post)
    pairs = PAIRS * 5 + [(prefix, str(asn)) for prefix, asn in PAIRS]
    states = rpki.rpki_states(pairs)
    assert post.call_count == len(PAIRS)
    assert states == {(prefix, str(asn)): 1 for prefix, asn in PAIRS}
    # Second batch is served from Redis without HTTP or a connection test.
    assert rpki.rpki_states(pairs) == states
    assert post.call_count == len(PAIRS)
    assert session_test.call_count == 1
    # Single lookups share the same cache entries.
    assert rpki.rpki_state(*PAIRS[0]) == 1
    assert post.call_count == len(PAIRS)


def test_concurrency_is_bounded(monkeypatch, session_test):
    lock = threading.Lock()
    active = {"now": 0, "peak": 0}

    def post(*_, **__):
        with lock:
            active["now"] += 1
            active["peak"] = max(active["peak"], active["now"])
        time.sleep(0.05)
        with lock:
            active["now"] -= 1
        return _graphql()

    monkeypatch.setattr(rpki.BaseExternal, "_post", post)
    rpki.rpki_states(PAIRS, max_concurrency=3)
    assert active["peak"] == 3


def test_cloudflare_reuses_one_session(monkeypatch, session_test):
    sessions = []
    original = rpki.BaseExternal.__init__

    def init(self, *args, **kwargs):
        sessions.append(self)
        original(self, *args, **kwargs)

    post = Mock(return_value=_graphql("invalid"))
    monkeypatch.setattr(rpki.BaseExternal, "__init__", init)
    monkeypatch.setattr(rpki.BaseExternal, "_post", post)
    states = rpki.rpki_states(PAIRS)
    assert set(states.values()) == {0}
    assert len(sessions) == 1
    assert session_test.call_count == 1
    assert {call.args[0] for call in post.call_args_list} == {"/api/graphql"}


def test_routinator_reuses_one_client(monkeypatch):
    clients = []

    class Client:
        def __init__(self, *_, **__):
            self.get = Mock(
                return_value=Mock(
                    json=lambda: {"validated_route": {"validity": {"state": "valid"}}}
                )
            )
            clients.append(self)

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    monkeypatch.setattr(rpki.httpx, "Client", Client)
    states = rpki.rpki_states(PAIRS, backend="routinator", rpki_server_url="https://r.test/")
    assert set(states.values()) == {1}
    assert len(clients) == 1
    assert clients[0].get.call_count == len(PAIRS)
    assert clients[0].get.call_args.args[0] == "https://r.test/validity"


def test_failed_lookups_are_default_and_not_cached(monkeypatch, session_test):
    post = Mock(side_effect=RuntimeError("timed out"))
    monkeypatch.setattr(rpki.BaseExternal, "_post", post)
    assert set(rpki.rpki_states(PAIRS[:2]).values()) == {3}
    rpki.rpki_states(PAIRS[:2])
    assert post.call_count == 4


def test_unreachable_backend_tests_connection_once(monkeypatch):
    test = Mock(side_effect=OSError("unreachable"))
    post = Mock()
    monkeypatch.setattr(rpki.BaseExternal, "_test", test)
    monkeypatch.setattr(rpki.BaseExternal, "_post", post)
    assert set(rpki.rpki_states(PAIRS).values()) == {3}
    assert test.call_count == 1
    assert post.call_count == 0


def _route(prefix, as_path):
    return {
        "prefix": prefix,
        "active": True,
        "age": 0,
        "weight": 0,
        "med": 0,
        "local_preference": 100,
        "as_path": as_path,
        "communities": [],
        "next_hop": "192.0.2.1",
        "source_as": 65000,
        "source_rid": "192.0.2.1",
        "peer_rid": "192.0.2.1",
        "rpki_state": 3,
    }


def test_route_table_validates_in_one_batch(monkeypatch, session_test):
    params = Params()
    params.structured.rpki.mode = "external"
    monkeypatch.setattr(bgp_route, "use_state", lambda _: params)
    single = Mock(side_effect=AssertionError("per-route lookup"))
    monkeypatch.setattr(bgp_route, "rpki_state", single)
    batch = Mock(wraps=rpki.rpki_states)
    monkeypatch.setattr(bgp_route, "rpki_states", batch)
    post = Mock(return_value=_graphql())
    monkeypatch.setattr(rpki.BaseExternal, "_post", post)

    # Twelve paths per prefix, as with add-path on a full table.
    routes = [_route(prefix, [65001, path, asn]) for prefix, asn in PAIRS for path in range(12)]
    routes += [_route("10.0.0.0/8", [65001]), _route("1.1.1.0/24", []) | {"rpki_state": 1}]
    table = bgp_route.BGPRouteTable(vrf="default", routes=routes, winning_weight="low")

    assert batch.call_count == 1
    assert post.call_count == len(PAIRS)
    states = {route.prefix: route.rpki_state for route in table.routes if route.as_path}
    assert states["10.0.0.0/8"] == 3  # Not global: keeps the router value.
    assert all(states[prefix] == 1 for prefix, _ in PAIRS)
    assert [r.rpki_state for r in table.routes if not r.as_path] == [3]
