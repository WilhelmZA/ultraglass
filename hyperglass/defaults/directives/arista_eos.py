"""Default Arista Directives."""

# Project
from hyperglass.models.directive import (
    Text,
    RuleWithIPv4,
    RuleWithIPv6,
    RuleWithPattern,
    BuiltinDirective,
)

__all__ = (
    "AristaBGPRoute",
    "AristaBGPASPath",
    "AristaBGPCommunity",
    "AristaPing",
    "AristaTraceroute",
    "AristaBGPRouteTable",
    "AristaBGPASPathTable",
    "AristaBGPCommunityTable",
)

NAME = "Arista EOS"
PLATFORMS = ["arista_eos"]

AristaBGPRoute = BuiltinDirective(
    id="__hyperglass_arista_eos_bgp_route__",
    name="BGP Route",
    rules=[
        RuleWithIPv4(
            condition="0.0.0.0/0",
            action="permit",
            command="show ip bgp {target}",
            vrf_command="show ip bgp {target} vrf {vrf}",
        ),
        RuleWithIPv6(
            condition="::/0",
            action="permit",
            command="show ipv6 bgp {target}",
            vrf_command="show ipv6 bgp {target} vrf {vrf}",
        ),
    ],
    field=Text(description="IP Address, Prefix, or Hostname"),
    table_output="__hyperglass_arista_eos_bgp_route_table__",
    platforms=PLATFORMS,
)

AristaBGPASPath = BuiltinDirective(
    id="__hyperglass_arista_eos_bgp_aspath__",
    name="BGP AS Path",
    rules=[
        RuleWithPattern(
            condition="*",
            action="permit",
            commands=[
                "show ip bgp regexp {target}",
                "show ipv6 bgp regexp {target}",
            ],
            vrf_commands=[
                "show ip bgp regexp {target} vrf {vrf}",
                "show ipv6 bgp regexp {target} vrf {vrf}",
            ],
        )
    ],
    field=Text(description="AS Path Regular Expression"),
    table_output="__hyperglass_arista_eos_bgp_aspath_table__",
    platforms=PLATFORMS,
)

AristaBGPCommunity = BuiltinDirective(
    id="__hyperglass_arista_eos_bgp_community__",
    name="BGP Community",
    rules=[
        RuleWithPattern(
            condition="*",
            action="permit",
            commands=[
                "show ip bgp community {target}",
                "show bgp ipv6 unicast community {target}",
            ],
            vrf_commands=[
                "show ip bgp community {target} vrf {vrf}",
                "show bgp ipv6 unicast community {target} vrf {vrf}",
            ],
        )
    ],
    field=Text(description="BGP Community String"),
    table_output="__hyperglass_arista_eos_bgp_community_table__",
    platforms=PLATFORMS,
)


AristaPing = BuiltinDirective(
    id="__hyperglass_arista_eos_ping__",
    name="Ping",
    rules=[
        RuleWithIPv4(
            condition="0.0.0.0/0",
            action="permit",
            command="ping ip {target} source {source4}",
            vrf_command="ping vrf {vrf} ip {target}",
        ),
        RuleWithIPv6(
            condition="::/0",
            action="permit",
            command="ping ipv6 {target} source {source6}",
            vrf_command="ping vrf {vrf} ipv6 {target}",
        ),
    ],
    field=Text(description="IP Address, Prefix, or Hostname"),
    platforms=PLATFORMS,
)

AristaTraceroute = BuiltinDirective(
    id="__hyperglass_arista_eos_traceroute__",
    name="Traceroute",
    rules=[
        RuleWithIPv4(
            condition="0.0.0.0/0",
            action="permit",
            command="traceroute ip {target} source {source4}",
            vrf_command="traceroute vrf {vrf} ip {target}",
        ),
        RuleWithIPv6(
            condition="::/0",
            action="permit",
            command="traceroute ipv6 {target} source {source6}",
            vrf_command="traceroute vrf {vrf} ipv6 {target}",
        ),
    ],
    field=Text(description="IP Address, Prefix, or Hostname"),
    platforms=PLATFORMS,
)

# Table Output Directives

AristaBGPRouteTable = BuiltinDirective(
    id="__hyperglass_arista_eos_bgp_route_table__",
    name="BGP Route",
    rules=[
        RuleWithIPv4(
            condition="0.0.0.0/0",
            action="permit",
            command="show ip bgp {target} | json",
            vrf_command="show ip bgp {target} vrf {vrf} | json",
        ),
        RuleWithIPv6(
            condition="::/0",
            action="permit",
            command="show ipv6 bgp {target} | json",
            vrf_command="show ipv6 bgp {target} vrf {vrf} | json",
        ),
    ],
    field=Text(description="IP Address, Prefix, or Hostname"),
    platforms=PLATFORMS,
)

AristaBGPASPathTable = BuiltinDirective(
    id="__hyperglass_arista_eos_bgp_aspath_table__",
    name="BGP AS Path",
    rules=[
        RuleWithPattern(
            condition="*",
            action="permit",
            commands=[
                "show ip bgp regexp {target} | json",
                "show ipv6 bgp regexp {target} | json",
            ],
            vrf_commands=[
                "show ip bgp regexp {target} vrf {vrf} | json",
                "show ipv6 bgp regexp {target} vrf {vrf} | json",
            ],
        )
    ],
    field=Text(description="AS Path Regular Expression"),
    platforms=PLATFORMS,
)

AristaBGPCommunityTable = BuiltinDirective(
    id="__hyperglass_arista_eos_bgp_community_table__",
    name="BGP Community",
    rules=[
        RuleWithPattern(
            condition="*",
            action="permit",
            commands=[
                # Only the address-family detail form carries communities, and
                # `show ipv6 bgp community` matches no IPv6 routes (#66).
                "show bgp ipv4 unicast community {target} detail | json",
                "show bgp ipv6 unicast community {target} detail | json",
            ],
            vrf_commands=[
                "show bgp ipv4 unicast community {target} detail vrf {vrf} | json",
                "show bgp ipv6 unicast community {target} detail vrf {vrf} | json",
            ],
        )
    ],
    field=Text(description="BGP Community String"),
    platforms=PLATFORMS,
)
