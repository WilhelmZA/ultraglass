"""Parse OpenBGPD JSON Response to Structured Data."""

# Standard Library
import json
import typing as t

# Third Party
from pydantic import PrivateAttr, ValidationError

# Project
from hyperglass.log import log
from hyperglass.exceptions.private import ParsingError
from hyperglass.models.parsing.openbgpd import OpenBGPDRib

# Local
from .._output import OutputPlugin

if t.TYPE_CHECKING:
    # Project
    from hyperglass.models.data import OutputDataModel
    from hyperglass.models.api.query import Query

    # Local
    from .._output import OutputType


def parse_openbgpd(output: t.Sequence[str]) -> "OutputDataModel":
    """Parse an OpenBGPD `bgpctl -j` RIB response."""
    result = None

    _log = log.bind(plugin=BGPRoutePluginOpenBGPD.__name__)

    for response in output:
        try:
            parsed: t.Dict = json.loads(response)

            _log.debug("Pre-parsed data", data=parsed)

            # A filter with no matching routes returns an empty object.
            if not parsed.get("rib"):
                continue

            bgp_table = OpenBGPDRib(**parsed).bgp_table()
            if result is None:
                result = bgp_table
            else:
                result += bgp_table

        except json.JSONDecodeError as err:
            _log.bind(error=str(err)).critical("Failed to decode JSON")
            raise ParsingError("Error parsing response data") from err

        except ValidationError as err:
            _log.critical(err)
            raise ParsingError("Error parsing response data") from err

    return result


class BGPRoutePluginOpenBGPD(OutputPlugin):
    """Coerce an OpenBGPD RIB in JSON format to a standard BGP Table structure."""

    _hyperglass_builtin: bool = PrivateAttr(True)
    platforms: t.Sequence[str] = ("openbgpd",)
    directives: t.Sequence[str] = (
        "__hyperglass_openbgpd_bgp_route_table__",
        "__hyperglass_openbgpd_bgp_aspath_table__",
        "__hyperglass_openbgpd_bgp_community_table__",
    )

    def process(self, *, output: "OutputType", query: "Query") -> "OutputType":
        """Parse OpenBGPD response if data is a string (and is therefore unparsed)."""
        should_process = all(
            (
                isinstance(output, (list, tuple)),
                query.device.platform in self.platforms,
                query.device.structured_output is True,
                query.device.has_directives(*self.directives),
            )
        )
        if should_process:
            return parse_openbgpd(output)
        return output
