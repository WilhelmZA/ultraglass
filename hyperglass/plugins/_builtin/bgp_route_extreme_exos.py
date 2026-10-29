"""Parse Extreme EXOS Text Response to Structured Data."""

# Standard Library
import typing as t

# Third Party
from pydantic import PrivateAttr, ValidationError

# Project
from hyperglass.log import log
from hyperglass.exceptions.private import ParsingError
from hyperglass.models.parsing.extreme_exos import (
    extreme_exos_bgp_table,
    parse_extreme_exos_routes,
)

# Local
from .._output import OutputPlugin

if t.TYPE_CHECKING:
    # Project
    from hyperglass.models.data import OutputDataModel
    from hyperglass.models.api.query import Query

    # Local
    from .._output import OutputType


def parse_extreme_exos(output: t.Sequence[str]) -> "OutputDataModel":
    """Parse EXOS `show bgp routes detail` responses."""
    _log = log.bind(plugin=BGPRoutePluginExtremeEXOS.__name__)

    try:
        routes = [route for response in output for route in parse_extreme_exos_routes(response)]

        # A target or filter with no matching routes returns no paths.
        if not routes:
            return None

        return extreme_exos_bgp_table(routes)

    except (ValueError, ValidationError) as err:
        _log.critical(err)
        raise ParsingError("Error parsing response data") from err


class BGPRoutePluginExtremeEXOS(OutputPlugin):
    """Coerce an EXOS route table in text format to a standard BGP Table structure."""

    _hyperglass_builtin: bool = PrivateAttr(True)
    platforms: t.Sequence[str] = ("extreme_exos",)
    directives: t.Sequence[str] = (
        "__hyperglass_extreme_exos_bgp_route_table__",
        "__hyperglass_extreme_exos_bgp_aspath_table__",
        "__hyperglass_extreme_exos_bgp_community_table__",
    )

    def process(self, *, output: "OutputType", query: "Query") -> "OutputType":
        """Parse EXOS response if data is a string (and is therefore unparsed)."""
        should_process = all(
            (
                isinstance(output, (list, tuple)),
                query.device.platform in self.platforms,
                query.device.structured_output is True,
                query.device.has_directives(*self.directives),
            )
        )
        if should_process:
            return parse_extreme_exos(output)
        return output
