"""Netmiko-Specific Classes & Utilities.

https://github.com/ktbyers/netmiko
"""

# Standard Library
import re
import math
import time
import random
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


# RouterOS 7 (`routing route`) and RouterOS 6 (`ip route`, `ipv6 route`) BGP route scans.
ROUTE_PRINT = re.compile(r"(?:routing|ip|ipv6) route ")

netmiko_device_send_args = {
    "mikrotik_routeros": {"last_read": 5.0},
    "mikrotik_switchos": {"last_read": 5.0},
}


# Platforms that drop new SSH sessions above a rate. IOS-XR accepts about one new
# session per second and resets the rest before login (#140).
PLATFORM_CONNECT_RETRIES = {"cisco_xr": 3}

# Connect-phase errors a session rate limit causes. Netmiko wraps each one in a
# timeout exception, so match the chained cause and the message.
CONNECT_REFUSALS = (ConnectionResetError, ConnectionRefusedError)
CONNECT_REFUSAL_TEXT = (
    "Error reading SSH protocol banner",
    "Connection reset by peer",
    "Connection refused",
)


def device_connect_retries(device: "Device") -> int:
    """Return the connect retries a device's config resolves to."""
    retries = getattr(device, "connect_retries", None)
    if retries is None:
        return PLATFORM_CONNECT_RETRIES.get(device.platform, 0)
    return retries


def is_connect_refusal(error: BaseException) -> bool:
    """Return True when the device dropped the session before login."""
    seen = set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        if isinstance(error, CONNECT_REFUSALS):
            return True
        if any(text in str(error) for text in CONNECT_REFUSAL_TEXT):
            return True
        error = error.__cause__ or error.__context__
    return False


def connect_with_retry(
    connect: t.Callable[[], t.Any],
    retries: int,
    budget: float,
    device: t.Optional[str] = None,
    sleep: t.Optional[t.Callable[[float], None]] = None,
    clock: t.Optional[t.Callable[[], float]] = None,
) -> t.Any:
    """Open a session, and retry with backoff when the device drops it before login.

    Only the connect step runs here, so no query command is ever sent twice. Each
    wait doubles from 1 s to at most 4 s, plus up to 1 s of jitter so workers spread
    out. Retries stop when the next wait would pass `budget` seconds.
    """
    sleep = sleep or time.sleep
    clock = clock or time.monotonic
    started = clock()
    attempt = 0
    while True:
        try:
            return connect()
        except Exception as error:
            if attempt >= retries or not is_connect_refusal(error):
                raise
            delay = min(2**attempt, 4) + random.uniform(0, 1)  # noqa: S311 (jitter, not crypto)
            if clock() - started + delay > budget:
                raise
            attempt += 1
            log.bind(device=device, attempt=attempt, retries=retries, delay=round(delay, 1)).info(
                "Device dropped the SSH session before login, retrying"
            )
            sleep(delay)


def open_session(driver_kwargs: t.Dict[str, t.Any], disable_paging: bool) -> t.Any:
    """Open a netmiko session. Without paging commands, connect after replacing them."""
    session = ConnectHandler(**driver_kwargs)
    if not disable_paging:
        session.disable_paging = lambda *args, **kwargs: ""
        session.set_terminal_width = lambda *args, **kwargs: ""
        session._open()
    return session


def collect_commands(
    connection, platform: str, queries, timeout: int, fallbacks=(), device=None, trace=None
) -> tuple:
    """Read each command fully and always release the SSH session.

    When the device rejects a command that has a fallback, run the fallback instead.
    An optional trace list records attempted commands and their replies for CLI diagnostics.
    """
    try:
        # These platforms require privileged mode for built-in diagnostics.
        if platform in ("arista_eos", "extreme_vsp", "ipinfusion_ocnos"):
            connection.enable()
        responses = []
        for index, query in enumerate(queries):
            # RouterOS BGP scans can be silent for a minute before the first row.
            timing = platform in netmiko_device_send_args and not ROUTE_PRINT.match(query)
            send = connection.send_command_timing if timing else connection.send_command
            args = netmiko_device_send_args[platform] if timing else {}
            attempt = {"command": query, "fallback": False, "output": None}
            if trace is not None:
                trace.append(attempt)
            response = send(query, read_timeout=timeout, **args)
            attempt["output"] = response
            fallback = fallbacks[index] if index < len(fallbacks) else None
            if fallback is not None and command_error((response,)):
                log.bind(device=device, command=query, fallback=fallback).warning(
                    "{!r} rejected {!r}, so {!r} ran instead. Set os_version on this device "
                    "in devices.yaml to run the supported command directly",
                    device,
                    query,
                    fallback,
                )
                attempt = {"command": fallback, "fallback": True, "output": None}
                if trace is not None:
                    trace.append(attempt)
                response = send(fallback, read_timeout=timeout, **args)
                attempt["output"] = response
            responses.append(response)
            # FortiOS diagnostic setup must succeed before sending probes.
            if platform == "fortinet" and command_error((response,)):
                break
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
                # Half the request timeout at most, so the query keeps time to run.
                nm_connect_direct = connect_with_retry(
                    lambda: open_session(driver_kwargs, self.device.disable_paging),
                    device_connect_retries(self.device),
                    params.request_timeout / 2,
                    device=self.device.name,
                )
                return collect_commands(
                    nm_connect_direct,
                    self.device.platform,
                    self.query,
                    params.request_timeout,
                    fallbacks=getattr(self, "fallbacks", ()),
                    device=self.device.name,
                    trace=getattr(self, "command_trace", None),
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
