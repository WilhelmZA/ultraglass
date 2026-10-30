"""Connect-phase retry for routers that rate-limit new SSH sessions (#140)."""

# Standard Library
from types import SimpleNamespace
from unittest.mock import Mock

# Third Party
import pytest
from netmiko import NetMikoTimeoutException, NetMikoAuthenticationException
from paramiko.ssh_exception import SSHException

# Project
from hyperglass.execution.drivers import ssh_netmiko
from hyperglass.exceptions.public import AuthError, DeviceTimeout

PARAMS = SimpleNamespace(request_timeout=90, logging=SimpleNamespace(session_log=False))


def _wrapped(cause: BaseException) -> NetMikoTimeoutException:
    """Raise the way netmiko does: a timeout exception chained to the socket error."""
    try:
        try:
            raise cause
        except BaseException:
            # Netmiko raises without `from`, so the cause is only the context.
            raise NetMikoTimeoutException("TCP connection to device failed.")  # noqa: B904
    except NetMikoTimeoutException as error:
        return error


BANNER = NetMikoTimeoutException(
    "A paramiko SSHException occurred during connection creation:\n\n"
    "Error reading SSH protocol banner[Errno 104] Connection reset by peer"
)
RESET = _wrapped(ConnectionResetError(104, "Connection reset by peer"))
REFUSED = _wrapped(ConnectionRefusedError(111, "Connection refused"))


def _device(platform="cisco_xr", connect_retries=None):
    return SimpleNamespace(
        name="xrd",
        platform=platform,
        proxy=None,
        _target="127.0.0.1",
        port=22,
        credential=SimpleNamespace(username="lg", _method="key", key="/test/lab-key"),
        driver_config={},
        disable_paging=True,
        connect_retries=connect_retries,
        get_device_type=lambda: platform,
    )


@pytest.fixture
def driver(monkeypatch):
    sleeps = []
    monkeypatch.setattr(ssh_netmiko, "use_state", lambda _: PARAMS)
    monkeypatch.setattr(ssh_netmiko.time, "sleep", sleeps.append)
    monkeypatch.setattr(ssh_netmiko.random, "uniform", lambda a, b: 0)

    def make(results, **device):
        connection = object.__new__(ssh_netmiko.NetmikoConnection)
        connection.device = _device(**device)
        connection.query = ["show bgp ipv4 unicast 192.0.2.0/24"]
        session = Mock()
        session.send_command.return_value = "route output"
        handler = Mock(side_effect=[session if r is None else r for r in results])
        monkeypatch.setattr(ssh_netmiko, "ConnectHandler", handler)
        return SimpleNamespace(connection=connection, handler=handler, session=session)

    make.sleeps = sleeps
    return make


@pytest.mark.parametrize(
    ("platform", "configured", "expected"),
    [
        ("cisco_xr", None, 3),
        ("cisco_ios", None, 0),
        ("juniper", None, 0),
        ("cisco_xr", 0, 0),
        ("frr", 2, 2),
    ],
)
def test_retries_default_to_platform(platform, configured, expected):
    device = _device(platform=platform, connect_retries=configured)
    assert ssh_netmiko.device_connect_retries(device) == expected


@pytest.mark.parametrize(
    "error", [BANNER, RESET, REFUSED, SSHException("Error reading SSH protocol banner")]
)
def test_rate_limit_errors_are_connect_refusals(error):
    assert ssh_netmiko.is_connect_refusal(error)


@pytest.mark.parametrize(
    "error",
    [
        NetMikoTimeoutException("TCP connection to device failed."),
        _wrapped(TimeoutError("timed out")),
        NetMikoAuthenticationException("Authentication to device failed."),
        ValueError("Pattern not detected"),
    ],
)
def test_other_errors_are_not_connect_refusals(error):
    assert not ssh_netmiko.is_connect_refusal(error)


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [BANNER, RESET, REFUSED])
async def test_xr_retries_until_session_opens(driver, error):
    run = driver([error, error, None])
    result = await run.connection.collect()
    assert result == ("route output",)
    assert run.handler.call_count == 3
    assert driver.sleeps == [1, 2]
    run.session.send_command.assert_called_once()
    run.session.disconnect.assert_called_once()


@pytest.mark.asyncio
async def test_xr_gives_up_after_retries(driver):
    run = driver([BANNER] * 4)
    with pytest.raises(DeviceTimeout):
        await run.connection.collect()
    assert run.handler.call_count == 4
    assert driver.sleeps == [1, 2, 4]
    run.session.send_command.assert_not_called()


@pytest.mark.asyncio
async def test_other_platforms_keep_single_attempt(driver):
    run = driver([BANNER, None], platform="cisco_ios")
    with pytest.raises(DeviceTimeout):
        await run.connection.collect()
    assert run.handler.call_count == 1
    assert driver.sleeps == []


@pytest.mark.asyncio
async def test_setting_enables_retry_on_any_platform(driver):
    run = driver([RESET, None], platform="juniper", connect_retries=1)
    assert await run.connection.collect() == ("route output",)
    assert run.handler.call_count == 2


@pytest.mark.asyncio
async def test_auth_and_timeout_errors_are_not_retried(driver):
    run = driver([NetMikoAuthenticationException("Authentication to device failed.")])
    with pytest.raises(AuthError):
        await run.connection.collect()
    assert run.handler.call_count == 1

    run = driver([_wrapped(TimeoutError("timed out"))])
    with pytest.raises(DeviceTimeout):
        await run.connection.collect()
    assert run.handler.call_count == 1
    assert driver.sleeps == []


@pytest.mark.asyncio
async def test_command_failure_is_not_retried(driver):
    run = driver([None, None])
    run.session.send_command.side_effect = ConnectionResetError(104, "Connection reset by peer")
    with pytest.raises(ConnectionResetError):
        await run.connection.collect()
    assert run.handler.call_count == 1
    run.session.send_command.assert_called_once()
    run.session.disconnect.assert_called_once()


def test_retry_stays_inside_budget(monkeypatch):
    monkeypatch.setattr(ssh_netmiko.random, "uniform", lambda a, b: 0)
    now = [0.0]
    sleeps = []

    def sleep(seconds):
        sleeps.append(seconds)
        now[0] += seconds

    connect = Mock(side_effect=[BANNER] * 4)
    with pytest.raises(NetMikoTimeoutException):
        ssh_netmiko.connect_with_retry(
            connect, retries=3, budget=3.5, sleep=sleep, clock=lambda: now[0]
        )
    # 1 s then 2 s fit in 3.5 s; the 4 s wait would not, so the third retry is skipped.
    assert sleeps == [1, 2]
    assert connect.call_count == 3
