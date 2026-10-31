"""OcNOS 6.5+ command-reference forms for BGP and bounded diagnostics."""

# Project
from hyperglass.models.directive import (
    Text,
    RuleWithIPv4,
    RuleWithIPv6,
    RuleWithPattern,
    BuiltinDirective,
)

__all__ = (
    "OcNOS_BGPRoute",
    "OcNOS_BGPRouteTable",
    "OcNOS_BGPASPath",
    "OcNOS_BGPCommunity",
    "OcNOS_Ping",
    "OcNOS_Traceroute",
)
NAME = "IP Infusion OcNOS"
PLATFORMS = ["ipinfusion_ocnos"]

OcNOS_BGPRoute = BuiltinDirective(
    id="__hyperglass_ipinfusion_ocnos_bgp_route__",
    name="BGP Route",
    platforms=PLATFORMS,
    table_output="__hyperglass_ipinfusion_ocnos_bgp_route_table__",
    field=Text(description="IP address or prefix"),
    rules=[
        RuleWithIPv4(condition="0.0.0.0/0", command="show bgp ipv4 unicast {target}"),
        RuleWithIPv6(condition="::/0", command="show bgp ipv6 unicast {target}"),
    ],
)
OcNOS_BGPRouteTable = OcNOS_BGPRoute.model_copy(
    deep=True,
    update={"id": "__hyperglass_ipinfusion_ocnos_bgp_route_table__", "table_output": None},
)
OcNOS_BGPASPath = BuiltinDirective(
    id="__hyperglass_ipinfusion_ocnos_bgp_aspath__",
    name="BGP AS Path",
    platforms=PLATFORMS,
    field=Text(description="AS path regular expression"),
    rules=[
        RuleWithPattern(
            condition="*",
            commands=[
                "show bgp ipv4 unicast regexp {target}",
                "show bgp ipv6 unicast regexp {target}",
            ],
        )
    ],
)
OcNOS_BGPCommunity = BuiltinDirective(
    id="__hyperglass_ipinfusion_ocnos_bgp_community__",
    name="BGP Community (IPv4)",
    platforms=PLATFORMS,
    field=Text(description="IPv4 standard community (ASN:value)"),
    rules=[RuleWithPattern(condition=r"^\d+:\d+$", command="show ip bgp community {target}")],
)
OcNOS_Ping = BuiltinDirective(
    id="__hyperglass_ipinfusion_ocnos_ping__",
    name="Ping",
    platforms=PLATFORMS,
    field=Text(description="IP address or hostname"),
    rules=[
        RuleWithIPv4(
            condition="0.0.0.0/0",
            command="ping ip {target} count 5",
            vrf_command="ping ip {target} count 5 vrf {vrf}",
        ),
        RuleWithIPv6(
            condition="::/0",
            command="ping ipv6 {target} count 5",
            vrf_command="ping ipv6 {target} count 5 vrf {vrf}",
        ),
    ],
)
OcNOS_Traceroute = BuiltinDirective(
    id="__hyperglass_ipinfusion_ocnos_traceroute__",
    name="Traceroute",
    platforms=PLATFORMS,
    field=Text(description="IP address or hostname"),
    rules=[
        RuleWithIPv4(
            condition="0.0.0.0/0",
            command="traceroute {target}",
            vrf_command="traceroute {target} vrf {vrf}",
        ),
        RuleWithIPv6(
            condition="::/0",
            command="traceroute ipv6 {target}",
            vrf_command="traceroute ipv6 {target} vrf {vrf}",
        ),
    ],
)
