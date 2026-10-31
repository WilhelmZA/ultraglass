"""Base Connection Class."""

# Standard Library
import typing as t
import re
from abc import ABC, abstractmethod

# Project
from hyperglass.types import Series
from hyperglass.plugins import OutputPluginManager
from hyperglass.exceptions.public import DeviceCommandError

# Local
from ._construct import Construct

COMMAND_ERROR = re.compile(
    r"^(?:%%?\s*(?:Invalid (?:input|command)|Incomplete|Unknown command|Unrecognized command"
    r"|Error|Permission denied)"
    r"|(?:birdc?:\s*)?syntax error\b"
    r"|vtysh_connect\([^\n]*Permission denied"
    r"|sudo:\s[^\n]*(?:password is required|not allowed|not in the sudoers|command not found)"
    r"|(?:[\w/.-]+:\s*)?(?:Permission denied|Operation not permitted)\s*$"
    r"|(?:traceroute|ping|bgpctl|birdc):[^\n]*(?:not permitted|Permission denied|invalid|unknown)"
    # Huawei VRP: `Error: Too many parameters ...`, `Error[4]: ...` on the NE40E (#155).
    r"|Error(?:\[\d+\])?:\s*(?:Wrong parameter|Unrecognized command|Incomplete command"
    r"|Too many parameters)"
    r"|unknown argument:|failure:\s|bad command name\b"
    r"|Command fail\. Return code|command parse error before|Invalid syntax\.)",
    re.IGNORECASE | re.MULTILINE,
)


def command_error(output: Series[str]) -> bool:
    """Recognize device command failures before structured parsers consume them."""
    responses = [output] if isinstance(output, str) else output
    return any(COMMAND_ERROR.search(response.strip()) for response in responses)


if t.TYPE_CHECKING:
    # Project
    from hyperglass.compat import SSHTunnelForwarder
    from hyperglass.models.api import Query
    from hyperglass.models.data import OutputDataModel
    from hyperglass.models.config.devices import Device


class Connection(ABC):
    """Base transport driver class."""

    def __init__(self, device: "Device", query_data: "Query") -> None:
        """Initialize connection to device."""
        self.device = device
        self.query_data = query_data
        self.query_type = self.query_data.query_type
        self.query_target = self.query_data.query_target
        self._query = Construct(device=self.device, query=self.query_data)
        self.query = self._query.queries()
        self.fallbacks = self._query.fallbacks
        self.plugin_manager = OutputPluginManager()

    @abstractmethod
    def setup_proxy(self: "Connection") -> "SSHTunnelForwarder":
        """Return a preconfigured sshtunnel.SSHTunnelForwarder instance."""
        pass

    async def response(self, output: Series[str]) -> t.Union["OutputDataModel", str]:
        """Send output through common parsers."""

        if command_error(output):
            raise DeviceCommandError(device_name=self.device.name)

        response = self.plugin_manager.execute(output=output, query=self.query_data)

        if response is None:
            response = ()

        return response
