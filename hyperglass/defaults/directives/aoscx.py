"""Aruba AOS-CX 10.14 BGP and diagnostic command forms."""

# Project
from hyperglass.models.directive import (
    Text,
    RuleWithIPv4,
    RuleWithIPv6,
    RuleWithPattern,
    BuiltinDirective,
)

__all__ = (
    "AOSCX_BGPRoute",
    "AOSCX_BGPRouteTable",
    "AOSCX_BGPCommunity",
    "AOSCX_Ping",
    "AOSCX_Traceroute",
)
NAME = "Aruba AOS-CX"
PLATFORMS = ["aruba_aoscx"]

AOSCX_BGPRoute = BuiltinDirective(
    id="__hyperglass_aruba_aoscx_bgp_route__",
    name="BGP Route",
    platforms=PLATFORMS,
    table_output="__hyperglass_aruba_aoscx_bgp_route_table__",
    field=Text(description="Exact prefix (addresses query /32 or /128)"),
    rules=[
        RuleWithIPv4(
            condition="0.0.0.0/0",
            command="show bgp ipv4 unicast {target}",
            vrf_command="show bgp vrf {vrf} ipv4 unicast {target}",
        ),
        RuleWithIPv6(
            condition="::/0",
            command="show bgp ipv6 unicast {target}",
            vrf_command="show bgp vrf {vrf} ipv6 unicast {target}",
        ),
    ],
)
AOSCX_BGPRouteTable = AOSCX_BGPRoute.model_copy(
    deep=True, update={"id": "__hyperglass_aruba_aoscx_bgp_route_table__", "table_output": None}
)
AOSCX_BGPCommunity = BuiltinDirective(
    id="__hyperglass_aruba_aoscx_bgp_community__",
    name="BGP Community",
    platforms=PLATFORMS,
    field=Text(description="Standard community (ASN:value)"),
    rules=[
        RuleWithPattern(
            condition=r"^\d+:\d+$",
            commands=[
                "show bgp ipv4 unicast community {target}",
                "show bgp ipv6 unicast community {target}",
            ],
        )
    ],
)
AOSCX_Ping = BuiltinDirective(
    id="__hyperglass_aruba_aoscx_ping__",
    name="Ping",
    platforms=PLATFORMS,
    field=Text(description="IP address or hostname"),
    rules=[
        RuleWithIPv4(
            condition="0.0.0.0/0",
            command="ping {target} repetitions 5 source {source4}",
            vrf_command="ping {target} repetitions 5 vrf {vrf} source {source4}",
        ),
        RuleWithIPv6(
            condition="::/0",
            command="ping6 {target} repetitions 5 source {source6}",
            vrf_command="ping6 {target} repetitions 5 vrf {vrf} source {source6}",
        ),
    ],
)
AOSCX_Traceroute = BuiltinDirective(
    id="__hyperglass_aruba_aoscx_traceroute__",
    name="Traceroute",
    platforms=PLATFORMS,
    field=Text(description="IP address or hostname"),
    rules=[
        RuleWithIPv4(
            condition="0.0.0.0/0",
            command="traceroute {target} probes 1 timeout 1 source {source4}",
            vrf_command="traceroute {target} probes 1 timeout 1 vrf {vrf} source {source4}",
        ),
        RuleWithIPv6(
            condition="::/0",
            command="traceroute6 {target} probes 1 timeout 1 source {source6}",
            vrf_command="traceroute6 {target} probes 1 timeout 1 vrf {vrf} source {source6}",
        ),
    ],
)
