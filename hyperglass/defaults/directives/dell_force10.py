"""Dell OS9 / Force10 commands."""

# Project
from hyperglass.models.directive import (
    Text,
    RuleWithIPv4,
    RuleWithIPv6,
    RuleWithPattern,
    BuiltinDirective,
)

__all__ = (
    "OS9_BGPRoute",
    "OS9_BGPRouteTable",
    "OS9_BGPASPath",
    "OS9_BGPCommunity",
    "OS9_Ping",
    "OS9_Traceroute",
)
NAME = "Dell OS9 / Force10"
PLATFORMS = ["dell_force10"]

OS9_BGPRoute = BuiltinDirective(
    id="__hyperglass_dell_force10_bgp_route__",
    name="BGP Route",
    platforms=PLATFORMS,
    table_output="__hyperglass_dell_force10_bgp_route_table__",
    field=Text(description="Exact prefix (addresses query /32 or /128)"),
    rules=[
        RuleWithIPv4(
            condition="0.0.0.0/0",
            command="show ip bgp ipv4 unicast {target}",
            vrf_command="show ip bgp vrf {vrf} ipv4 unicast {target}",
        ),
        RuleWithIPv6(
            condition="::/0",
            command="show ip bgp ipv6 unicast {target}",
            vrf_command="show ip bgp vrf {vrf} ipv6 unicast {target}",
        ),
    ],
)
OS9_BGPRouteTable = OS9_BGPRoute.model_copy(
    deep=True, update={"id": "__hyperglass_dell_force10_bgp_route_table__", "table_output": None}
)
OS9_BGPASPath = BuiltinDirective(
    id="__hyperglass_dell_force10_bgp_aspath__",
    name="BGP AS Path",
    platforms=PLATFORMS,
    field=Text(description="AS path regular expression"),
    rules=[
        RuleWithPattern(
            condition="*",
            commands=[
                "show ip bgp ipv4 unicast regexp {target}",
                "show ip bgp ipv6 unicast regexp {target}",
            ],
            vrf_command=[
                "show ip bgp vrf {vrf} ipv4 unicast regexp {target}",
                "show ip bgp vrf {vrf} ipv6 unicast regexp {target}",
            ],
        )
    ],
)
OS9_BGPCommunity = BuiltinDirective(
    id="__hyperglass_dell_force10_bgp_community__",
    name="BGP Community",
    platforms=PLATFORMS,
    field=Text(description="Standard community (ASN:value)"),
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
OS9_Ping = BuiltinDirective(
    id="__hyperglass_dell_force10_ping__",
    name="Ping",
    platforms=PLATFORMS,
    field=Text(description="IP address or hostname"),
    rules=[
        RuleWithIPv4(
            condition="0.0.0.0/0",
            command="ping {target} count 5",
            vrf_command="ping {target} count 5 vrf {vrf}",
        ),
        RuleWithIPv6(
            condition="::/0",
            command="ping {target} count 5",
            vrf_command="ping {target} count 5 vrf {vrf}",
        ),
    ],
)
OS9_Traceroute = BuiltinDirective(
    id="__hyperglass_dell_force10_traceroute__",
    name="Traceroute",
    platforms=PLATFORMS,
    field=Text(description="IP address or hostname"),
    # The command reference limits traceroute VRFs to E-Series hardware.
    rules=[
        RuleWithIPv4(condition="0.0.0.0/0", command="traceroute {target}"),
        RuleWithIPv6(condition="::/0", command="traceroute {target}"),
    ],
)
