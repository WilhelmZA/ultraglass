"""Provide an isolated Redis store for backend tests."""

# Third Party
import pytest
import fakeredis

# Project
from hyperglass.state import manager
from hyperglass.state import use_state
from hyperglass.state.hooks import _use_state
from hyperglass.models.config.params import Params
from hyperglass.defaults.directives import init_builtin_directives


@pytest.fixture(autouse=True)
def isolated_redis(monkeypatch):
    """Keep tests independent of local Redis services and application state."""
    server = fakeredis.FakeServer()
    _use_state.cache_clear()
    monkeypatch.setattr(manager, "Redis", lambda **kwargs: fakeredis.FakeRedis(server=server))
    state = use_state()
    state.redis.set("params", Params())
    state.redis.set("directives", init_builtin_directives())
    yield
    _use_state.cache_clear()
