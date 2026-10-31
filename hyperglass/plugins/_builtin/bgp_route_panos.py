"""Parse PAN-OS classic virtual-router loc-rib-detail replies."""

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

PREFIX = re.compile(r"^\s*Prefix:[ \t]*(\S+)([ \t]*\*)?[ \t]*$", re.MULTILINE)
FIELD = re.compile(r"^\s*([A-Za-z][A-Za-z ]*):[ \t]*([^\n]*)", re.MULTILINE)


def _path(prefix: re.Match, block: str) -> dict:
    fields = dict(FIELD.findall(block))
    required = {"Nexthop", "AS Path", "Origin", "MED", "Local Preference", "Weight", "Flap"}
    if not required.issubset(fields):
        raise ValueError("Incomplete PAN-OS path")
    path = fields["AS Path"].strip()
    if path and not re.fullmatch(r"\d+(?:\.\d+)?(?:[, ]+\d+(?:\.\d+)?)*", path):
        raise ValueError("Unsupported AS path")
    as_path = [parse_asn(asn) for asn in re.split(r"[, ]+", path) if asn]
    if None in as_path:
        raise ValueError("Invalid ASN")
    return {
        "prefix": str(ip_network(prefix[1])),
        "next_hop": str(ip_address(fields["Nexthop"].strip())),
        "active": bool(prefix[2]),
        "as_path": as_path,
        "source_as": as_path[-1] if as_path else 0,
        # Originator ID is not the neighbor router ID; Received from is a peer name.
        "source_rid": "",
        "peer_rid": "",
        "local_preference": int(fields["Local Preference"]),
        "med": int(fields["MED"]),
        "weight": int(fields["Weight"]),
        "communities": fields.get("Community", "").split(),
        "age": -1,
        "rpki_state": 3,
    }


def parse_panos(text: str, vrf: str = "default") -> BGPRouteTable:
    """Require one matching virtual router and a complete route-count footer."""
    contexts = re.findall(r"^VIRTUAL ROUTER: (.+) \(id \d+\)", text, re.MULTILINE)
    footer = re.search(r"total routes shown: (\d+)\s*\Z", text)
    starts = list(PREFIX.finditer(text))
    if contexts != [vrf] or not footer or not starts or len(starts) != int(footer[1]):
        raise ValueError("Incomplete PAN-OS reply or mismatched virtual router")
    routes = [
        _path(
            start,
            text[start.end() : starts[i + 1].start() if i + 1 < len(starts) else footer.start()],
        )
        for i, start in enumerate(starts)
    ]
    return BGPRouteTable(vrf=vrf, count=len(routes), routes=routes, winning_weight="high")


class BGPRoutePluginPANOS(OutputPlugin):
    """Keep the advanced routing engine and summary output outside this parser."""

    _hyperglass_builtin: bool = PrivateAttr(True)
    platforms: t.Sequence[str] = ("paloalto_panos",)
    directives: t.Sequence[str] = ("__hyperglass_paloalto_panos_bgp_route_table__",)

    def process(self, *, output, query):
        """Leave unknown formats available as text."""
        if not query.device.structured_output:
            return output
        text = output if isinstance(output, str) else "\n".join(output)
        try:
            return parse_panos(text, query.device.vrf or "default")
        except ValueError:
            return output
