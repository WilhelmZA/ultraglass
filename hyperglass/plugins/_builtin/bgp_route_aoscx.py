"""Read AOS-CX labelled BGP prefix detail, including wrapped communities."""

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

# A field starts at a line boundary or in the second aligned column. Requiring
# whitespace before ':' prevents IPv6 and community values from becoming labels.
FIELD = re.compile(r"(?:^|[ \t]{2,})([A-Za-z][A-Za-z. -]*?)[ \t]+:[ \t]*", re.MULTILINE)
NETWORK = re.compile(r"^\s*Network\s+:\s*", re.MULTILINE)


def _path(block: str) -> dict:
    matches = list(FIELD.finditer(block))
    fields = {
        match[1].strip(): " ".join(
            block[match.end() : matches[i + 1].start() if i + 1 < len(matches) else None].split()
        )
        for i, match in enumerate(matches)
    }
    # A complete detail contains these labels even when their values are empty.
    required = {
        "Network",
        "Nexthop",
        "Peer",
        "Metric",
        "Local Pref",
        "Weight",
        "Best",
        "Valid",
        "AS-Path",
        "Communities",
        "Extd. Communities",
    }
    if not required.issubset(fields) or fields["Best"] not in ("Yes", "No"):
        raise ValueError("Incomplete AOS-CX path")
    path = fields["AS-Path"]
    if path and not re.fullmatch(r"\d+(?:\.\d+)?(?:\s+\d+(?:\.\d+)?)*", path):
        raise ValueError("Unsupported AS set or confederation")
    as_path = [parse_asn(asn) for asn in path.split()]
    if None in as_path:
        raise ValueError("Invalid ASN")
    communities = [item for item in re.split(r"[,\s]+", fields["Communities"]) if item]
    return {
        "prefix": str(ip_network(fields["Network"])),
        "next_hop": str(ip_address(fields["Nexthop"])),
        "peer_rid": str(ip_address(fields["Peer"])),
        # The peer's router ID is not present; Originator ID has different semantics.
        "source_rid": "",
        "source_as": as_path[-1] if as_path else 0,
        "as_path": as_path,
        "communities": communities,
        "med": int(fields["Metric"]),
        "local_preference": int(fields["Local Pref"]),
        "weight": int(fields["Weight"]),
        "active": fields["Best"] == "Yes",
        "age": -1,
        "rpki_state": 3,
    }


def parse_aoscx(text: str, vrf: str = "default") -> BGPRouteTable:
    """Reject the entire response if any detail block is incomplete or unfamiliar."""
    starts = list(NETWORK.finditer(text))
    if not starts:
        raise ValueError("Not AOS-CX prefix detail")
    routes = [
        _path(text[start.start() : starts[i + 1].start() if i + 1 < len(starts) else None])
        for i, start in enumerate(starts)
    ]
    return BGPRouteTable(vrf=vrf, count=len(routes), routes=routes, winning_weight="high")


class BGPRoutePluginAOSCX(OutputPlugin):
    """Select the structured AOS-CX prefix directive only."""

    _hyperglass_builtin: bool = PrivateAttr(True)
    platforms: t.Sequence[str] = ("aruba_aoscx",)
    directives: t.Sequence[str] = ("__hyperglass_aruba_aoscx_bgp_route_table__",)

    def process(self, *, output, query):
        """Keep unknown responses available as text."""
        if not query.device.structured_output:
            return output
        text = output if isinstance(output, str) else "\n".join(output)
        try:
            return parse_aoscx(text, query.device.vrf or "default")
        except (ValueError, KeyError):
            return output
