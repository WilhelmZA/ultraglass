"""Parse complete FortiOS BGP detail paths in a single routing context."""

# Standard Library
import re
import typing as t
from ipaddress import ip_address, ip_network

# Third Party
from pydantic import PrivateAttr

# Project
from hyperglass.util import parse_asn
from hyperglass.models.data import BGPRouteTable

# Local
from .._output import OutputPlugin

HEADER = re.compile(r"^(?:VRF (\d+) )?BGP routing table entry for (\S+)", re.MULTILINE)
PATH = re.compile(r"^  (Local|[\d({\[].*)$", re.MULTILINE)
HOP = re.compile(r"^    (\S+)(?: \(inaccessible\))? from (\S+) \(([^)]+)\)", re.MULTILINE)


def _path(prefix: str, path: str, block: str) -> dict:
    hop = HOP.search(block)
    origin = re.search(r"^      Origin ([^\n]+)", block, re.MULTILINE)
    if not hop or not origin or "Last update:" not in block:
        raise ValueError("Incomplete FortiOS path")
    if path != "Local" and not re.fullmatch(r"\d+(?:\.\d+)?(?: +\d+(?:\.\d+)?)*", path):
        raise ValueError("Unsupported AS path")
    as_path = [] if path == "Local" else [parse_asn(asn) for asn in path.split()]
    if None in as_path:
        raise ValueError("Invalid ASN")
    # MED and weight may be omitted when zero. Local preference must be present.
    pref = re.search(r"\blocalpref (\d+)\b", origin[1])
    if not pref:
        raise ValueError("Missing local preference")
    metric = re.search(r"\bmetric (\d+)\b", origin[1])
    weight = re.search(r"\bweight (\d+)\b", origin[1])
    communities = re.search(r"^      Community: ([^\n]*)", block, re.MULTILINE)
    return {
        "prefix": prefix,
        "next_hop": str(ip_address(hop[1])),
        "peer_rid": str(ip_address(hop[2])),
        "source_rid": str(ip_address(hop[3])),
        "as_path": as_path,
        "source_as": as_path[-1] if as_path else 0,
        "active": bool(re.search(r"(?:^|,\s*)best(?:,|$)", origin[1])),
        "local_preference": int(pref[1]),
        "med": int(metric[1]) if metric else 0,
        "weight": int(weight[1]) if weight else 0,
        "communities": communities[1].split() if communities else [],
        "age": -1,
        "rpki_state": 3,
    }


def parse_fortinet(text: str) -> BGPRouteTable:
    """Require the advertised path count and reject combined VRF responses."""
    headers = list(HEADER.finditer(text))
    counts = re.findall(r"^Paths: \((\d+) available", text, re.MULTILINE)
    if len(headers) != 1 or len(counts) != 1:
        raise ValueError("Not a single FortiOS route detail")
    paths = list(PATH.finditer(text))
    if not paths or len(paths) != int(counts[0]):
        raise ValueError("Incomplete FortiOS paths")
    prefix = str(ip_network(headers[0][2]))
    routes = [
        _path(
            prefix,
            path[1].strip(),
            text[path.end() : paths[i + 1].start() if i + 1 < len(paths) else None],
        )
        for i, path in enumerate(paths)
    ]
    return BGPRouteTable(
        vrf=headers[0][1] or "default", count=len(routes), routes=routes, winning_weight="high"
    )


class BGPRoutePluginFortinet(OutputPlugin):
    """Parse only the structured FortiOS route directive."""

    _hyperglass_builtin: bool = PrivateAttr(True)
    platforms: t.Sequence[str] = ("fortinet",)
    directives: t.Sequence[str] = ("__hyperglass_fortinet_bgp_route_table__",)

    def process(self, *, output, query):
        """Leave unknown formats available as text."""
        if not query.device.structured_output:
            return output
        text = output if isinstance(output, str) else "\n".join(output)
        try:
            return parse_fortinet(text)
        except ValueError:
            return output
