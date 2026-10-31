"""Dell SmartFabric OS10 commands (not the Linux FRR shell)."""

# Project
from hyperglass.models.directive import (
    Text,
    RuleWithIPv4,
    RuleWithIPv6,
    RuleWithPattern,
    BuiltinDirective,
)

__all__ = (
    "OS10_BGPRoute",
    "OS10_BGPRouteTable",
    "OS10_BGPCommunity",
    "OS10_Ping",
    "OS10_Traceroute",
)
NAME = "Dell SmartFabric OS10"
PLATFORMS = ["dell_os10"]

OS10_BGPRoute = BuiltinDirective(
    id="__hyperglass_dell_os10_bgp_route__",
    name="BGP Route",
    platforms=PLATFORMS,
    table_output="__hyperglass_dell_os10_bgp_route_table__",
    field=Text(description="Exact prefix (addresses query /32 or /128)"),
    rules=[
        RuleWithIPv4(
            condition="0.0.0.0/0",
            command="show ip bgp {target}",
            vrf_command="show ip bgp vrf {vrf} {target}",
        ),
        RuleWithIPv6(
            condition="::/0",
            command="show ip bgp ipv6 unicast {target}",
            vrf_command="show ip bgp vrf {vrf} ipv6 unicast {target}",
        ),
    ],
)
OS10_BGPRouteTable = OS10_BGPRoute.model_copy(
    deep=True, update={"id": "__hyperglass_dell_os10_bgp_route_table__", "table_output": None}
)
OS10_BGPCommunity = BuiltinDirective(
    id="__hyperglass_dell_os10_bgp_community__",
    name="BGP Community",
    platforms=PLATFORMS,
    field=Text(description="Standard community (ASN:value), OS10 10.5.2.1+"),
    rules=[
        RuleWithPattern(
            condition=r"^\d+:\d+$",
            commands=[
                "show ip bgp ipv4 unicast community {target}",
                "show ip bgp ipv6 unicast community {target}",
            ],
            vrf_command=[
                "show ip bgp vrf {vrf} ipv4 unicast community {target}",
                "show ip bgp vrf {vrf} ipv6 unicast community {target}",
            ],
        )
    ],
)
OS10_Ping = BuiltinDirective(
    id="__hyperglass_dell_os10_ping__",
    name="Ping",
    platforms=PLATFORMS,
    field=Text(description="IP address or hostname"),
    rules=[
        RuleWithIPv4(
            condition="0.0.0.0/0",
            command="ping -4 -c 5 -I {source4} {target}",
            vrf_command="ping vrf {vrf} -4 -c 5 -I {source4} {target}",
        ),
        RuleWithIPv6(
            condition="::/0",
            command="ping6 -c 5 -I {source6} {target}",
            vrf_command="ping6 vrf {vrf} -c 5 -I {source6} {target}",
        ),
    ],
)
OS10_Traceroute = BuiltinDirective(
    id="__hyperglass_dell_os10_traceroute__",
    name="Traceroute",
    platforms=PLATFORMS,
    field=Text(description="IP address or hostname"),
    rules=[
        RuleWithIPv4(
            condition="0.0.0.0/0",
            command="traceroute {target} -4 -n -q 1 -w 1 -s {source4}",
            vrf_command="traceroute vrf {vrf} {target} -4 -n -q 1 -w 1 -s {source4}",
        ),
        RuleWithIPv6(
            condition="::/0",
            command="traceroute {target} -6 -n -q 1 -w 1 -s {source6}",
            vrf_command="traceroute vrf {vrf} {target} -6 -n -q 1 -w 1 -s {source6}",
        ),
    ],
)
