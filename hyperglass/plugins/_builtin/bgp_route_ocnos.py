"""OcNOS detailed routes reuse the IOS-shaped path parser with OcNOS status lines."""

# Standard Library
import re
import typing as t
from ipaddress import ip_address

# Third Party
from pydantic import PrivateAttr

# Project
from hyperglass.models.data import BGPRouteTable
from hyperglass.models.parsing.cisco_ios import parse_detail

# Local
from .._output import OutputPlugin


def parse_ocnos(text: str, vrf: str = "default") -> BGPRouteTable:
    """Reject incomplete detail and leave summaries to text mode."""
    count = re.search(r"Paths:\s*\((\d+) available", text)
    if not count or "BGP routing table entry for" not in text:
        raise ValueError("Not an OcNOS detailed prefix")
    # OcNOS can put validity/best flags on the line following Origin attributes.
    normalized = re.sub(
        r"^(\s+)((?:valid|invalid|sourced|internal|external|best)\b[^\n]*)$",
        r"\1Origin \2",
        text,
        flags=re.MULTILINE,
    )
    routes = parse_detail(normalized)
    if len(routes) != int(count[1]) or not routes:
        raise ValueError("Incomplete OcNOS BGP paths")
    for route in routes:
        route["next_hop"] = str(ip_address(route["next_hop"]))
        # Last update has no timezone and is not a reliable route-age timestamp.
        route["age"] = -1
        route["rpki_state"] = 3
    return BGPRouteTable(vrf=vrf, count=len(routes), routes=routes, winning_weight="high")


class BGPRoutePluginOcNOS(OutputPlugin):
    """Parse only the structured OcNOS single-prefix directive."""

    _hyperglass_builtin: bool = PrivateAttr(True)
    platforms: t.Sequence[str] = ("ipinfusion_ocnos",)
    directives: t.Sequence[str] = ("__hyperglass_ipinfusion_ocnos_bgp_route_table__",)

    def process(self, *, output, query):
        """Retain unrecognized replies for inspection."""
        if not query.device.structured_output:
            return output
        text = output if isinstance(output, str) else "\n".join(output)
        try:
            return parse_ocnos(text, query.device.vrf or "default")
        except ValueError:
            return output
