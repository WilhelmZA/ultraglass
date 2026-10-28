"""Data Models for Parsing OpenBGPD JSON Response."""

# Standard Library
import typing as t

# Third Party
from pydantic import ConfigDict, model_validator

# Project
from hyperglass.log import log
from hyperglass.util import parse_asn, parse_as_path
from hyperglass.models.data import BGPRouteTable

# Local
from ..main import HyperglassModel

RPKI_STATE_MAP = {
    "invalid": 0,
    "valid": 1,
    "not-found": 2,
}


class _OpenBGPDBase(HyperglassModel):
    model_config = ConfigDict(extra="ignore")


class OpenBGPDRoute(_OpenBGPDBase):
    """OpenBGPD `bgpctl -j show rib detail` entry."""

    prefix: str
    aspath: t.List[int]
    exit_nexthop: str
    peer_rid: str = ""
    valid: bool = False
    best: bool = False
    ovs: str = ""
    metric: int = 0
    localpref: int = 100
    weight: int = 0
    last_update_sec: int = 0
    communities: t.List[str] = []
    large_communities: t.List[str] = []
    aggregator_as: int = 0
    aggregator_id: str = ""

    @model_validator(mode="before")
    def validate_route(cls, values):
        """Flatten the AS path, neighbor and aggregator attributes."""
        new = values.copy()
        new["aspath"] = parse_as_path(values.get("aspath", ""))
        new["peer_rid"] = values.get("neighbor", {}).get("bgp_id", "")
        for attribute in values.get("attributes", []):
            if attribute.get("type") == "Aggregator":
                new["aggregator_as"] = parse_asn(attribute.get("AS", 0)) or 0
                new["aggregator_id"] = attribute.get("router_id", "")
        return new


class OpenBGPDRib(_OpenBGPDBase):
    """OpenBGPD RIB Model."""

    rib: t.List[OpenBGPDRoute] = []

    def bgp_table(self) -> BGPRouteTable:
        """Convert the OpenBGPD-specific fields to standard parsed data model."""
        routes = [
            {
                "prefix": route.prefix,
                "active": route.best,
                "age": route.last_update_sec,
                "weight": route.weight,
                "med": route.metric,
                "local_preference": route.localpref,
                "as_path": route.aspath,
                "communities": [*route.communities, *route.large_communities],
                "next_hop": route.exit_nexthop,
                "source_as": route.aggregator_as,
                "source_rid": route.aggregator_id,
                "peer_rid": route.peer_rid,
                "rpki_state": RPKI_STATE_MAP.get(route.ovs, 3),
            }
            for route in self.rib
        ]

        serialized = BGPRouteTable(
            vrf="default",
            count=len(routes),
            routes=routes,
            winning_weight="high",
        )

        log.bind(platform="openbgpd", response=repr(serialized)).debug("Serialized response")
        return serialized
