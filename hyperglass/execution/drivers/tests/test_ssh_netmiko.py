"""Regression coverage for prompt reads, device errors and enable mode."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from netmiko.exceptions import ReadTimeout

from hyperglass.execution.drivers import ssh_netmiko
from hyperglass.execution.drivers._common import Connection, command_error
from hyperglass.exceptions.public import DeviceCommandError, DeviceTimeout

PARAMS = SimpleNamespace(request_timeout=90, logging=SimpleNamespace(session_log=False))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "platform", ["frr", "cisco_ios", "juniper", "huawei", "arista_eos", "mikrotik_routeros"]
)
async def test_driver_reads_to_prompt_except_mikrotik(monkeypatch, platform):
    driver = object.__new__(ssh_netmiko.NetmikoConnection)
    driver.device = SimpleNamespace(
        name="lab",
        platform=platform,
        proxy=None,
        _target="127.0.0.1",
        port=22,
        credential=SimpleNamespace(username="lg", _method="key", key="/test/lab-key"),
        driver_config={},
        disable_paging=True,
        get_device_type=lambda: platform,
    )
    driver.query = ["traceroute 192.0.2.1"]
    session = Mock()
    session.send_command.return_value = "first hop\nlast hop"
    session.send_command_timing.return_value = "MikroTik output"
    monkeypatch.setattr(ssh_netmiko, "ConnectHandler", Mock(return_value=session))
    monkeypatch.setattr(ssh_netmiko, "use_state", lambda _: PARAMS)
    result = await driver.collect()
    if platform == "mikrotik_routeros":
        session.send_command.assert_not_called()
        session.send_command_timing.assert_called_once_with(
            driver.query[0], read_timeout=90, last_read=5.0
        )
        assert result == ("MikroTik output",)
    else:
        session.send_command_timing.assert_not_called()
        session.send_command.assert_called_once_with(driver.query[0], read_timeout=90)
        assert result == ("first hop\nlast hop",)
    assert session.enable.call_count == (1 if platform == "arista_eos" else 0)
    session.disconnect.assert_called_once()

    session.reset_mock()
    session.send_command.side_effect = ReadTimeout("prompt missing")
    session.send_command_timing.side_effect = ReadTimeout("prompt missing")
    with pytest.raises(DeviceTimeout):
        await driver.collect()
    session.disconnect.assert_called_once()


@pytest.mark.parametrize(
    "output",
    [
        "% Invalid input (privileged mode required)",
        "vtysh_connect(/run/frr/mgmtd.vty): stat = Permission denied",
        "BIRD 2.17.2 ready.\nsyntax error, unexpected CF_SYM_UNDEFINED",
        "traceroute: socket: Operation not permitted",
        "unknown argument: _13335$\nvalid commands/args:\n  <asnum>",
        "    ^\nError: Wrong parameter found at '^' position.",
    ],
)
@pytest.mark.asyncio
async def test_device_errors_precede_parsing(output):
    driver = SimpleNamespace(device=SimpleNamespace(name="test"), plugin_manager=Mock())
    with pytest.raises(DeviceCommandError) as error:
        await Connection.response(driver, (output,))
    assert error.value.level == "warning"
    driver.plugin_manager.execute.assert_not_called()


@pytest.mark.parametrize(
    "output",
    [
        "",
        "No matching routes",
        " 1 * * *\n 2 192.0.2.1 0.1 ms",
        "5 packets transmitted, 0 received, 100% packet loss",
    ],
)
def test_empty_or_unreachable_results_are_not_command_errors(output):
    assert not command_error((output,))


def test_mikrotik_bgp_scan_waits_for_prompt():
    session = Mock()
    session.send_command.return_value = "complete route output"
    command = 'routing route print detail without-paging where bgp.as-path~"13335"'
    assert ssh_netmiko.collect_commands(session, "mikrotik_routeros", [command], 300) == (
        "complete route output",
    )
    session.send_command.assert_called_once_with(command, read_timeout=300)
    session.send_command_timing.assert_not_called()


@pytest.mark.asyncio
async def test_session_log_and_skipped_paging(monkeypatch, tmp_path):
    driver = object.__new__(ssh_netmiko.NetmikoConnection)
    driver.device = SimpleNamespace(
        id="lab_ios",
        name="lab-ios",
        platform="cisco_ios",
        proxy=None,
        _target="127.0.0.1",
        port=22,
        credential=SimpleNamespace(username="lg", _method="key", key="/test/lab-key"),
        driver_config={},
        disable_paging=False,
        get_device_type=lambda: "cisco_ios",
    )
    driver.query = ["show ip bgp 192.0.2.1 | no-more"]
    session = Mock()
    session.send_command.return_value = "route"
    handler = Mock(return_value=session)
    params = SimpleNamespace(
        request_timeout=90, logging=SimpleNamespace(session_log=True, directory=tmp_path)
    )
    monkeypatch.setattr(ssh_netmiko, "ConnectHandler", handler)
    monkeypatch.setattr(ssh_netmiko, "use_state", lambda _: params)

    assert await driver.collect() == ("route",)

    kwargs = handler.call_args.kwargs
    assert kwargs["auto_connect"] is False
    assert kwargs["session_log_file_mode"] == "append"
    assert kwargs["session_log"].startswith(str(tmp_path / "lab_ios-"))
    session._open.assert_called_once()
    assert session.disable_paging() == ""
    assert session.set_terminal_width() == ""
