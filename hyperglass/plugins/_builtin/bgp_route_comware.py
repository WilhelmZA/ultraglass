"""Parse Comware 7 detailed BGP prefixes, retaining unfamiliar replies as text."""

# Standard Library
import re
import typing as t
from ipaddress import ip_address, ip_network

# Third Party
from pydantic import PrivateAttr

# Project
from hyperglass.util import parse_asn
from hyperglass.models.data.bgp_route import BGPRouteTable

# Local
from .._output import OutputPlugin


def _fields(text: str) -> dict[str, str]:
    """Read labelled fields, including wrapped values, without splitting IPv6 addresses."""
    matches = list(re.finditer(r"^\s*([A-Za-z][A-Za-z -]*?)\s*:\s*", text, re.MULTILINE))
    return {
        match[1]
        .strip()
        .lower(): " ".join(
            text[match.end() : matches[i + 1].start() if i + 1 < len(matches) else None].split()
        )
        for i, match in enumerate(matches)
    }


def _route(prefix: str, block: str) -> dict:
    """Map one path without inventing origin validation or route age."""
    fields = _fields(block)
    path = fields["as-path"]
    if path == "(null)":
        as_path = []
    elif re.fullmatch(r"\d+(?:\.\d+)?(?:\s+\d+(?:\.\d+)?)*", path):
        as_path = [parse_asn(item) for item in path.split()]
        if None in as_path:
            raise ValueError("Invalid AS number")
    else:
        raise ValueError("Unsupported Comware AS path")
    attributes = fields["attribute value"]

    def number(name: str, default: int) -> int:
        match = re.search(rf"\b{re.escape(name)}\s+(\d+)", attributes, re.IGNORECASE)
        return int(match[1]) if match else default

    peer = re.fullmatch(r"(\S+)\s*\(([^)]+)\)", fields.get("from", ""))
    communities = re.findall(r"\d+:\d+(?::\d+)?", fields.get("community", ""))
    return {
        "prefix": prefix,
        "active": "best" in re.split(r"[,\s]+", fields["state"]),
        "age": -1,
        "weight": number("pref-val", 0),
        "med": number("MED", 0),
        "local_preference": number("localpref", 100),
        "as_path": as_path,
        "communities": communities,
        "next_hop": str(ip_address(fields["original nexthop"])),
        "source_as": as_path[0] if as_path else 0,
        "source_rid": peer[2] if peer else "",
        "peer_rid": peer[1] if peer else "",
        "rpki_state": 3,
    }


def parse_comware(text: str, vrf: str = "default") -> BGPRouteTable:
    """Accept complete single-prefix detail output; never return a partial path set."""
    text = text.replace("\xa0", " ")
    header = re.search(r"BGP routing table information of\s+(\S+/\d+):", text)
    count = re.search(r"Paths:\s*(\d+)\s+available", text)
    if not header or not count:
        raise ValueError("Not a Comware detailed prefix")
    prefix = str(ip_network(header[1]))
    body = text[header.end() :]
    starts = list(re.finditer(r"^\s*(?:Imported route\.|From\s*:)", body, re.MULTILINE))
    routes = [
        _route(prefix, body[start.start() : starts[i + 1].start() if i + 1 < len(starts) else None])
        for i, start in enumerate(starts)
    ]
    if len(routes) != int(count[1]) or not routes:
        raise ValueError("Incomplete Comware BGP paths")
    return BGPRouteTable(vrf=vrf, count=len(routes), routes=routes, winning_weight="high")


class BGPRoutePluginComware(OutputPlugin):
    """Select Comware detail parsing only for the structured route directive."""

    _hyperglass_builtin: bool = PrivateAttr(True)
    platforms: t.Sequence[str] = ("hp_comware",)
    directives: t.Sequence[str] = ("__hyperglass_hp_comware_bgp_route_table__",)

    def process(self, *, output, query):
        """Keep text mode and unsupported or incomplete responses intact."""
        if not query.device.structured_output:
            return output
        text = output if isinstance(output, str) else "\n".join(output)
        try:
            return parse_comware(text, query.device.vrf or "default")
        except (ValueError, KeyError):
            return output
