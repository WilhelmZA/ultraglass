"""Default VyOS Directives."""

# Project
from hyperglass.models.directive import (
    Text,
    RuleWithIPv4,
    RuleWithIPv6,
    RuleWithPattern,
    BuiltinDirective,
)

__all__ = (
    "VyOS_BGPASPath",
    "VyOS_BGPCommunity",
    "VyOS_BGPRoute",
    "VyOS_Ping",
    "VyOS_Traceroute",
    "VyOS_BGPRouteTable",
    "VyOS_BGPASPathTable",
    "VyOS_BGPCommunityTable",
)

NAME = "VyOS"
PLATFORMS = ["vyos"]

VyOS_BGPRoute = BuiltinDirective(
    id="__hyperglass_vyos_bgp_route__",
    name="BGP Route",
    rules=[
        RuleWithIPv4(
            condition="0.0.0.0/0",
            action="permit",
            command="show bgp ipv4 {target}",
            vrf_command="show bgp vrf {vrf} ipv4 {target}",
        ),
        RuleWithIPv6(
            condition="::/0",
            action="permit",
            command="show bgp ipv6 {target}",
            vrf_command="show bgp vrf {vrf} ipv6 {target}",
        ),
    ],
    field=Text(description="IP Address, Prefix, or Hostname"),
    table_output="__hyperglass_vyos_bgp_route_table__",
    platforms=PLATFORMS,
)

VyOS_BGPASPath = BuiltinDirective(
    id="__hyperglass_vyos_bgp_aspath__",
    name="BGP AS Path",
    rules=[
        RuleWithPattern(
            condition="*",
            action="permit",
            commands=[
                'show bgp ipv4 regexp "{target}"',
                'show bgp ipv6 regexp "{target}"',
            ],
            vrf_commands=[
                'show bgp vrf {vrf} ipv4 regexp "{target}"',
                'show bgp vrf {vrf} ipv6 regexp "{target}"',
            ],
        )
    ],
    field=Text(description="AS Path Regular Expression"),
    table_output="__hyperglass_vyos_bgp_aspath_table__",
    platforms=PLATFORMS,
)

VyOS_BGPCommunity = BuiltinDirective(
    id="__hyperglass_vyos_bgp_community__",
    name="BGP Community",
    rules=[
        RuleWithPattern(
            condition="*",
            action="permit",
            commands=[
                "show bgp ipv4 community {target}",
                "show bgp ipv6 community {target}",
            ],
            vrf_commands=[
                "show bgp vrf {vrf} ipv4 community {target}",
                "show bgp vrf {vrf} ipv6 community {target}",
            ],
        )
    ],
    field=Text(description="BGP Community String"),
    table_output="__hyperglass_vyos_bgp_community_table__",
    platforms=PLATFORMS,
)

VyOS_Ping = BuiltinDirective(
    id="__hyperglass_vyos_ping__",
    name="Ping",
    rules=[
        RuleWithIPv4(
            condition="0.0.0.0/0",
            action="permit",
            command="ping {target} count 5 interface {source4}",
            vrf_command="ping {target} vrf {vrf} count 5",
        ),
        RuleWithIPv6(
            condition="::/0",
            action="permit",
            command="ping {target} count 5 interface {source6}",
            vrf_command="ping {target} vrf {vrf} count 5",
        ),
    ],
    field=Text(description="IP Address, Prefix, or Hostname"),
    platforms=PLATFORMS,
)

VyOS_Traceroute = BuiltinDirective(
    id="__hyperglass_vyos_traceroute__",
    name="Traceroute",
    rules=[
        RuleWithIPv4(
            condition="0.0.0.0/0",
            action="permit",
            command="traceroute {target} source-address {source4} icmp",
            vrf_command="traceroute {target} vrf {vrf} icmp",
        ),
        RuleWithIPv6(
            condition="::/0",
            action="permit",
            command="traceroute {target} source-address {source6} icmp",
            vrf_command="traceroute {target} vrf {vrf} icmp",
        ),
    ],
    field=Text(description="IP Address, Prefix, or Hostname"),
    platforms=PLATFORMS,
)

# Table Output Directives
# VyOS op mode has no JSON form, so these read FRR JSON from the vtysh shell.

VyOS_BGPRouteTable = BuiltinDirective(
    id="__hyperglass_vyos_bgp_route_table__",
    name="BGP Route",
    rules=[
        RuleWithIPv4(
            condition="0.0.0.0/0",
            action="permit",
            command='vtysh -c "show bgp ipv4 unicast {target} json"',
            vrf_command='vtysh -c "show bgp vrf {vrf} ipv4 unicast {target} json"',
        ),
        RuleWithIPv6(
            condition="::/0",
            action="permit",
            command='vtysh -c "show bgp ipv6 unicast {target} json"',
            vrf_command='vtysh -c "show bgp vrf {vrf} ipv6 unicast {target} json"',
        ),
    ],
    field=Text(description="IP Address, Prefix, or Hostname"),
    platforms=PLATFORMS,
)

VyOS_BGPASPathTable = BuiltinDirective(
    id="__hyperglass_vyos_bgp_aspath_table__",
    name="BGP AS Path",
    rules=[
        RuleWithPattern(
            condition="*",
            action="permit",
            commands=[
                'vtysh -c "show bgp ipv4 unicast regexp {target} json"',
                'vtysh -c "show bgp ipv6 unicast regexp {target} json"',
            ],
            vrf_commands=[
                'vtysh -c "show bgp vrf {vrf} ipv4 unicast regexp {target} json"',
                'vtysh -c "show bgp vrf {vrf} ipv6 unicast regexp {target} json"',
            ],
        )
    ],
    field=Text(description="AS Path Regular Expression"),
    platforms=PLATFORMS,
)

VyOS_BGPCommunityTable = BuiltinDirective(
    id="__hyperglass_vyos_bgp_community_table__",
    name="BGP Community",
    rules=[
        RuleWithPattern(
            condition="*",
            action="permit",
            commands=[
                'vtysh -c "show bgp ipv4 unicast community {target} json"',
                'vtysh -c "show bgp ipv6 unicast community {target} json"',
            ],
            vrf_commands=[
                'vtysh -c "show bgp vrf {vrf} ipv4 unicast community {target} json"',
                'vtysh -c "show bgp vrf {vrf} ipv6 unicast community {target} json"',
            ],
        )
    ],
    field=Text(description="BGP Community String"),
    platforms=PLATFORMS,
)
