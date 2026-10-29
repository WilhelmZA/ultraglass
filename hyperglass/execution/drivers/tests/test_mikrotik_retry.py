"""MikroTik empty-table retry escalates the delay factor (#106)."""

# Standard Library
from types import SimpleNamespace
from unittest.mock import Mock

# Third Party
import pytest

# Project
from hyperglass.execution.drivers.ssh_netmiko import delay_factor_override


def _query(platform="mikrotik_routeros"):
    return SimpleNamespace(
        query_type="__hyperglass_mikrotik_bgp_route_table__",
        directive=None,
        device=SimpleNamespace(name="JHB-1", platform=platform, driver_config={}),
    )


@pytest.fixture
def routes():
    # Importing the API reads application state, which the autouse fixture provides.
    from hyperglass.api import routes

    return routes


@pytest.fixture
def harness(monkeypatch, routes):
    seen = []
    results = []

    async def execute(_):
        seen.append(delay_factor_override.get())
        return results.pop(0)

    async def no_sleep(_):
        return None

    log = Mock()
    monkeypatch.setattr(routes, "execute", execute)
    monkeypatch.setattr(routes.asyncio, "sleep", no_sleep)
    monkeypatch.setattr(routes, "_is_empty_bgp_table", lambda output: output == "empty")
    monkeypatch.setattr(routes, "device_delay_factor", lambda _: 1)
    monkeypatch.setattr(routes, "log", log)
    return SimpleNamespace(seen=seen, results=results, log=log.bind.return_value)


@pytest.mark.parametrize(
    ("start", "steps"),
    [(0.1, [0.1, 3, 6, 10]), (1, [1, 3, 6, 10]), (3, [3, 6, 10, 10]), (6, [6, 10, 10, 10])],
)
def test_delay_factor_steps_start_at_device_value(routes, start, steps):
    assert routes._delay_factor_steps(start) == steps


@pytest.mark.asyncio
async def test_retry_escalates_and_logs_working_factor(routes, harness):
    harness.results.extend(["empty", "empty", "routes"])
    assert await routes._execute_query(_query()) == "routes"
    assert harness.seen == [None, 3, 6]
    harness.log.warning.assert_called_with(
        "{!r} returned no routes at global_delay_factor={} and returned routes at {}. "
        "Set driver_config: {{global_delay_factor: {}}} on this device in devices.yaml",
        "JHB-1",
        1,
        6,
        6,
    )
    assert delay_factor_override.get() is None


@pytest.mark.asyncio
async def test_first_attempt_success_does_not_override_or_warn(routes, harness):
    harness.results.append("routes")
    assert await routes._execute_query(_query()) == "routes"
    assert harness.seen == [None]
    harness.log.warning.assert_not_called()


@pytest.mark.asyncio
async def test_empty_at_every_factor_is_reported_once(routes, harness):
    harness.results.extend(["empty"] * 4)
    assert await routes._execute_query(_query()) == "empty"
    assert harness.seen == [None, 3, 6, 10]
    harness.log.bind.return_value.info.assert_called_once_with(
        "MikroTik returned no routes at the highest delay factor"
    )


@pytest.mark.asyncio
async def test_other_platforms_run_once(routes, harness):
    harness.results.append("empty")
    assert await routes._execute_query(_query(platform="frr")) == "empty"
    assert harness.seen == [None]
