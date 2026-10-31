"""Coerce a Huawei route table in text format to a standard BGP Table structure."""

# Standard Library
import re
from typing import TYPE_CHECKING, List, Optional, Sequence

# Third Party
from pydantic import PrivateAttr, ValidationError

# Project
from hyperglass.log import log
from hyperglass.exceptions.private import ParsingError
from hyperglass.models.parsing.huawei import HuaweiBGPTable

# Local
from .._output import OutputPlugin

if TYPE_CHECKING:
    # Project
    from hyperglass.models.data import OutputDataModel
    from hyperglass.models.api.query import Query

    # Local
    from .._output import OutputType


def parse_huawei(output: Sequence[str], vrf: Optional[str] = None) -> "OutputDataModel":
    """Parse a Huawei BGP text response.

    VRP prints the VPN instance only in some formats, so the VRF comes from the device.
    """
    result = None

    _log = log.bind(plugin=BGPSTRRoutePluginHuawei.__name__)

    for response in output:
        try:
            # Parse the text output using the Huawei parser
            validated = HuaweiBGPTable.parse_text(response)

            # A target or filter with no matching routes returns no paths.
            if not validated.routes:
                continue

            bgp_table = validated.bgp_table(vrf=vrf or "default")

            if result is None:
                result = bgp_table
            else:
                result += bgp_table

        except ValidationError as err:
            _log.critical(err)
            raise ParsingError(err) from err
        except Exception as err:
            _log.bind(error=str(err)).critical("Failed to parse Huawei BGP output")
            raise ParsingError("Error parsing response data") from err

    return result


class BGPSTRRoutePluginHuawei(OutputPlugin):
    """Coerce a Huawei route table in text format to a standard BGP Table structure."""

    _hyperglass_builtin: bool = PrivateAttr(True)
    platforms: Sequence[str] = ("huawei", "huawei_vrpv8")
    directives: Sequence[str] = (
        "__hyperglass_huawei_bgp_route_table__",
        "__hyperglass_huawei_bgp_aspath_table__",
        "__hyperglass_huawei_bgp_community_table__",
    )

    def process(self, *, output: "OutputType", query: "Query") -> "OutputType":
        """Parse Huawei response if data is a string (and is therefore unparsed)."""
        _log = log.bind(plugin=self.__class__.__name__)
        _log.debug("Processing Huawei output with structured parser")

        should_process = all(
            (
                isinstance(output, (list, tuple)),
                query.device.platform in self.platforms,
                query.device.structured_output is True,
                query.device.has_directives(*self.directives),
            )
        )
        if should_process:
            return parse_huawei(output, vrf=getattr(query.device, "vrf", None))
        return output
