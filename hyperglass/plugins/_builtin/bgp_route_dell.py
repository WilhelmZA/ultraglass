"""Dell OS9 and OS10 detailed prefix format with Received-from path blocks."""

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

PEER = re.compile(r"^[ \t]*([\da-fA-F:.]+)[ \t]*\(([\d.]+)\)([^\n]*)", re.MULTILINE)


def _path(prefix: str, block: str, peer: re.Match) -> dict:
    path = re.search(r"^[ \t]*AS_PATH\s*:[ \t]*([^\n]*)", block, re.MULTILINE)
    hop = re.search(r"Next-Hop\s*:\s*([^,]+),", block)
    attrs = re.search(
        r"Origin\s+\w+,\s*Metric\s+(\d+),\s*LocalPref\s+(\d+),\s*Weight\s+(\d+)", block
    )
    if not path or not hop or not attrs:
        raise ValueError("Incomplete Dell path")
    value = path[1].strip()
    if value and not re.fullmatch(r"\d+(?:\.\d+)?(?:\s+\d+(?:\.\d+)?)*", value):
        raise ValueError("Unsupported AS set or confederation")
    as_path = [parse_asn(asn) for asn in value.split()]
    if None in as_path:
        raise ValueError("Invalid ASN")
    community = re.search(r"^[ \t]*Communities\s*:[ \t]*([^\n]*)", block, re.MULTILINE)
    return {
        "prefix": prefix,
        "as_path": as_path,
        "active": bool(re.search(r"\bBest\b", peer[3])),
        "next_hop": str(ip_address(hop[1].strip())),
        "peer_rid": str(ip_address(peer[1])),
        "source_rid": str(ip_address(peer[2])),
        "source_as": as_path[-1] if as_path else 0,
        "med": int(attrs[1]),
        "local_preference": int(attrs[2]),
        "weight": int(attrs[3]),
        "communities": re.findall(r"\d+:\d+(?::\d+)?", community[1]) if community else [],
        "age": -1,
        "rpki_state": 3,
    }


def parse_dell(text: str, vrf: str = "default") -> BGPRouteTable:
    """Return all numbered-next-hop paths or reject the entire response."""
    header = re.search(r"^BGP routing table entry for (\S+)", text, re.MULTILINE)
    count = re.search(r"Paths:\s*\((\d+) available", text)
    if not header or not count:
        raise ValueError("Not Dell prefix detail")
    prefix = str(ip_network(header[1]))
    peers = list(PEER.finditer(text))
    if len(peers) != int(count[1]) or not peers:
        raise ValueError("Incomplete or unnumbered Dell paths")
    routes = [
        _path(
            prefix, text[peer.start() : peers[i + 1].start() if i + 1 < len(peers) else None], peer
        )
        for i, peer in enumerate(peers)
    ]
    return BGPRouteTable(vrf=vrf, count=len(routes), routes=routes, winning_weight="high")


class BGPRoutePluginDell(OutputPlugin):
    """Parse only detailed OS9 and OS10 route directives."""

    _hyperglass_builtin: bool = PrivateAttr(True)
    platforms: t.Sequence[str] = ("dell_force10", "dell_os10")
    directives: t.Sequence[str] = (
        "__hyperglass_dell_force10_bgp_route_table__",
        "__hyperglass_dell_os10_bgp_route_table__",
    )

    def process(self, *, output, query):
        """Preserve unsupported replies as text."""
        if not query.device.structured_output:
            return output
        text = output if isinstance(output, str) else "\n".join(output)
        try:
            return parse_dell(text, query.device.vrf or "default")
        except ValueError:
            return output
