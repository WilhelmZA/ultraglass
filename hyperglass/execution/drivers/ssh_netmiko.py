"""Netmiko-Specific Classes & Utilities.

https://github.com/ktbyers/netmiko
"""

# Standard Library
import math
import typing as t
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Iterable

# Third Party
from netmiko import (  # type: ignore
    ConnectHandler,
    NetMikoTimeoutException,
    NetMikoAuthenticationException,
)
from netmiko.exceptions import ReadTimeout

# Project
from hyperglass.log import log
from hyperglass.state import use_state
from hyperglass.exceptions.public import AuthError, DeviceTimeout, ResponseEmpty

# Local
from .ssh import SSHConnection
from ._common import command_error

if t.TYPE_CHECKING:
    from hyperglass.models.config.devices import Device

DEFAULT_DELAY_FACTOR = 0.1

# RouterOS answers slowly. At 0.1 a high-latency link returns the prompt before
# the route output, so the query parses to an empty table (#106).
MIKROTIK_DELAY_FACTOR = 1

netmiko_device_globals = {
    # Netmiko doesn't currently handle Mikrotik echo verification well,
    # see ktbyers/netmiko#1600
    "mikrotik_routeros": {"global_cmd_verify": False, "global_delay_factor": MIKROTIK_DELAY_FACTOR},
    "mikrotik_switchos": {"global_cmd_verify": False, "global_delay_factor": MIKROTIK_DELAY_FACTOR},
}

# Set by the API's empty-table retry to run one attempt at a higher delay factor.
delay_factor_override: ContextVar[t.Optional[float]] = ContextVar(
    "delay_factor_override", default=None
)


def device_driver_args(device: "Device") -> t.Dict[str, t.Any]:
    """Return the netmiko arguments a device's config resolves to.

    Defaults apply first and the device's `driver_config` last, so an operator's
    value always wins.
    """
    args: t.Dict[str, t.Any] = {"global_delay_factor": DEFAULT_DELAY_FACTOR}
    if "_telnet" in device.platform:
        # Telnet devices with a low delay factor (default) tend to
        # throw login errors.
        args["global_delay_factor"] = 2
    return {**args, **netmiko_device_globals.get(device.platform, {}), **device.driver_config}


def device_delay_factor(device: "Device") -> float:
    """Return the delay factor a device's config resolves to."""
    return device_driver_args(device)["global_delay_factor"]


netmiko_device_send_args = {
    "mikrotik_routeros": {"last_read": 5.0},
    "mikrotik_switchos": {"last_read": 5.0},
}


def collect_commands(
    connection, platform: str, queries, timeout: int, fallbacks=(), device=None
) -> tuple:
    """Read each command fully and always release the SSH session.

    When the device rejects a command that has a fallback, run the fallback instead.
    """
    try:
        if platform == "arista_eos":
            connection.enable()
        responses = []
        for index, query in enumerate(queries):
            # RouterOS BGP scans can be silent for a minute before the first row.
            timing = platform in netmiko_device_send_args and not query.startswith("routing route ")
            send = connection.send_command_timing if timing else connection.send_command
            args = netmiko_device_send_args[platform] if timing else {}
            response = send(query, read_timeout=timeout, **args)
            fallback = fallbacks[index] if index < len(fallbacks) else None
            if fallback is not None and command_error((response,)):
                log.bind(device=device, command=query, fallback=fallback).warning(
                    "{!r} rejected {!r}, so {!r} ran instead. Set os_version on this device "
                    "in devices.yaml to run the supported command directly",
                    device,
                    query,
                    fallback,
                )
                response = send(fallback, read_timeout=timeout, **args)
            responses.append(response)
        return tuple(responses)
    finally:
        connection.disconnect()


class NetmikoConnection(SSHConnection):
    """Handle a device connection via Netmiko."""

    async def collect(self, host: str = None, port: int = None) -> Iterable:
        """Connect directly to a device.

        Directly connects to the router via Netmiko library, returns the
        command output.
        """
        params = use_state("params")
        _log = log.bind(
            device=self.device.name,
            address=f"{host}:{port}",
            proxy=str(self.device.proxy.address) if self.device.proxy is not None else None,
        )

        _log.debug("Connecting to device")

        driver_kwargs = {
            "host": host or self.device._target,
            "port": port or self.device.port,
            "device_type": self.device.get_device_type(),
            "username": self.device.credential.username,
            "timeout": math.floor(params.request_timeout * 1.25),
            "session_timeout": math.ceil(params.request_timeout - 1),
            **device_driver_args(self.device),
        }

        override = delay_factor_override.get()
        if override is not None:
            driver_kwargs["global_delay_factor"] = override

        if params.logging.session_log:
            date = datetime.now(UTC).strftime("%Y%m%d")
            driver_kwargs["session_log"] = str(
                params.logging.directory / f"{self.device.id}-{date}.log"
            )
            driver_kwargs["session_log_file_mode"] = "append"

        if not self.device.disable_paging:
            # Connect after replacing the paging and terminal width commands.
            driver_kwargs["auto_connect"] = False

        if self.device.credential._method == "password":
            # Use password auth if no key is defined.
            driver_kwargs["password"] = self.device.credential.password.get_secret_value()
        else:
            # Otherwise, use key auth.
            driver_kwargs["use_keys"] = True
            driver_kwargs["key_file"] = self.device.credential.key
            if self.device.credential._method == "encrypted_key":
                # If the key is encrypted, use the password field as the
                # private key password.
                driver_kwargs["passphrase"] = self.device.credential.password.get_secret_value()

        # Run blocking netmiko operations in thread executor to prevent blocking the event loop
        import asyncio

        def _netmiko_connect():
            """Execute blocking netmiko operations in a separate thread."""
            try:
                nm_connect_direct = ConnectHandler(**driver_kwargs)
                if not self.device.disable_paging:
                    nm_connect_direct.disable_paging = lambda *args, **kwargs: ""
                    nm_connect_direct.set_terminal_width = lambda *args, **kwargs: ""
                    nm_connect_direct._open()
                return collect_commands(
                    nm_connect_direct,
                    self.device.platform,
                    self.query,
                    params.request_timeout,
                    fallbacks=getattr(self, "fallbacks", ()),
                    device=self.device.name,
                )

            except (NetMikoTimeoutException, ReadTimeout) as scrape_error:
                raise DeviceTimeout(error=scrape_error, device=self.device) from scrape_error

            except NetMikoAuthenticationException as auth_error:
                raise AuthError(error=auth_error, device=self.device) from auth_error

        try:
            # Execute blocking netmiko operations in thread pool
            loop = asyncio.get_event_loop()
            responses = await loop.run_in_executor(None, _netmiko_connect)
        except (DeviceTimeout, AuthError):
            # Re-raise our custom exceptions as-is
            raise

        if not responses:
            raise ResponseEmpty(query=self.query_data)

        return responses
