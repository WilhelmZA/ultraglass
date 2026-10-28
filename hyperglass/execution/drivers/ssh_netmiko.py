"""Netmiko-Specific Classes & Utilities.

https://github.com/ktbyers/netmiko
"""

# Standard Library
import math
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

netmiko_device_globals = {
    # Netmiko doesn't currently handle Mikrotik echo verification well,
    # see ktbyers/netmiko#1600
    "mikrotik_routeros": {"global_cmd_verify": False},
    "mikrotik_switchos": {"global_cmd_verify": False},
}

netmiko_device_send_args = {
    "mikrotik_routeros": {"last_read": 5.0},
    "mikrotik_switchos": {"last_read": 5.0},
}


def collect_commands(connection, platform: str, queries, timeout: int) -> tuple:
    """Read each command fully and always release the SSH session."""
    try:
        if platform == "arista_eos":
            connection.enable()
        responses = []
        for query in queries:
            # RouterOS BGP scans can be silent for a minute before the first row.
            timing = platform in netmiko_device_send_args and not query.startswith("routing route ")
            send = connection.send_command_timing if timing else connection.send_command
            args = netmiko_device_send_args[platform] if timing else {}
            responses.append(send(query, read_timeout=timeout, **args))
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

        global_args = netmiko_device_globals.get(self.device.platform, {})

        driver_kwargs = {
            "host": host or self.device._target,
            "port": port or self.device.port,
            "device_type": self.device.get_device_type(),
            "username": self.device.credential.username,
            "global_delay_factor": 0.1,
            "timeout": math.floor(params.request_timeout * 1.25),
            "session_timeout": math.ceil(params.request_timeout - 1),
            **global_args,
            **self.device.driver_config,
        }

        if params.logging.session_log:
            date = datetime.now(UTC).strftime("%Y%m%d")
            driver_kwargs["session_log"] = str(
                params.logging.directory / f"{self.device.id}-{date}.log"
            )
            driver_kwargs["session_log_file_mode"] = "append"

        if not self.device.disable_paging:
            # Connect after replacing the paging and terminal width commands.
            driver_kwargs["auto_connect"] = False

        if "_telnet" in self.device.platform:
            # Telnet devices with a low delay factor (default) tend to
            # throw login errors.
            driver_kwargs["global_delay_factor"] = 2

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
                    nm_connect_direct, self.device.platform, self.query, params.request_timeout
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
