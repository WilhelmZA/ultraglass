"""Default Mikrotik Directives."""

# Project
from hyperglass.models.directive import (
    Text,
    RuleWithIPv4,
    RuleWithIPv6,
    RuleWithPattern,
    BuiltinDirective,
)

__all__ = (
    "Mikrotik_BGPASPath",
    "Mikrotik_BGPCommunity",
    "Mikrotik_BGPRoute",
    "Mikrotik_Ping",
    "Mikrotik_Traceroute",
    "MikrotikBGPRouteTable",
    "MikrotikBGPASPathTable",
    "MikrotikBGPCommunityTable",
)

NAME = "Mikrotik"
PLATFORMS = ["mikrotik_routeros", "mikrotik_switchos"]

Mikrotik_BGPRoute = BuiltinDirective(
    id="__hyperglass_mikrotik_bgp_route__",
    name="BGP Route",
    rules=[
        RuleWithIPv4(
            condition="0.0.0.0/0",
            action="permit",
            command="routing route print detail without-paging where {target} in dst-address bgp and dst-address !=0.0.0.0/0",
            vrf_command="routing route print detail without-paging where {target} in dst-address bgp and dst-address !=0.0.0.0/0 and routing-table={vrf}",
        ),
        RuleWithIPv6(
            condition="::/0",
            action="permit",
            command="routing route print detail without-paging where {target} in dst-address bgp and dst-address !=::/0",
            vrf_command="routing route print detail without-paging where {target} in dst-address bgp and dst-address !=::/0 and routing-table={vrf}",
        ),
    ],
    field=Text(description="IP Address, Prefix, or Hostname"),
    plugins=["mikrotik_garbage_output", "bgp_routestr_mikrotik"],
    table_output="__hyperglass_mikrotik_bgp_route_table__",
    platforms=PLATFORMS,
)

Mikrotik_BGPASPath = BuiltinDirective(
    id="__hyperglass_mikrotik_bgp_aspath__",
    name="BGP AS Path",
    rules=[
        RuleWithPattern(
            condition="*",
            action="permit",
            commands=[
                'routing route print detail without-paging where bgp and bgp.as-path~"{target}"',
            ],
            vrf_commands=[
                'routing route print detail without-paging where bgp and bgp.as-path~"{target}" and routing-table={vrf}',
            ],
        )
    ],
    field=Text(description="AS Path Regular Expression"),
    plugins=["mikrotik_garbage_output", "bgp_routestr_mikrotik"],
    table_output="__hyperglass_mikrotik_bgp_aspath_table__",
    platforms=PLATFORMS,
)

Mikrotik_BGPCommunity = BuiltinDirective(
    id="__hyperglass_mikrotik_bgp_community__",
    name="BGP Community",
    rules=[
        RuleWithPattern(
            condition="*",
            action="permit",
            commands=[
                'routing route print detail without-paging where bgp and bgp.communities~"{target}"',
            ],
            vrf_commands=[
                'routing route print detail without-paging where bgp and bgp.communities~"{target}" and routing-table={vrf}',
            ],
        )
    ],
    field=Text(description="BGP Community String"),
    plugins=["mikrotik_garbage_output", "bgp_routestr_mikrotik"],
    table_output="__hyperglass_mikrotik_bgp_community_table__",
    platforms=PLATFORMS,
)

Mikrotik_Ping = BuiltinDirective(
    id="__hyperglass_mikrotik_ping__",
    name="Ping",
    rules=[
        RuleWithIPv4(
            condition="0.0.0.0/0",
            action="permit",
            command="ping src-address={source4} count=5 {target}",
            vrf_command="ping vrf={vrf} count=5 {target}",
        ),
        RuleWithIPv6(
            condition="::/0",
            action="permit",
            command="ping src-address={source6} count=5 {target}",
            vrf_command="ping vrf={vrf} count=5 {target}",
        ),
    ],
    field=Text(description="IP Address, Prefix, or Hostname"),
    platforms=PLATFORMS,
)

Mikrotik_Traceroute = BuiltinDirective(
    id="__hyperglass_mikrotik_traceroute__",
    name="Traceroute",
    rules=[
        RuleWithIPv4(
            condition="0.0.0.0/0",
            action="permit",
            command="tool traceroute src-address={source4} timeout=1 duration=30 count=3 {target}",
            vrf_command="tool traceroute vrf={vrf} timeout=1 duration=30 count=3 {target}",
        ),
        RuleWithIPv6(
            condition="::/0",
            action="permit",
            command="tool traceroute src-address={source6} timeout=1 duration=30 count=3 {target}",
            vrf_command="tool traceroute vrf={vrf} timeout=1 duration=30 count=3 {target}",
        ),
    ],
    field=Text(description="IP Address, Prefix, or Hostname"),
    platforms=PLATFORMS,
)

# Table Output Directives

MikrotikBGPRouteTable = BuiltinDirective(
    id="__hyperglass_mikrotik_bgp_route_table__",
    name="BGP Route",
    rules=[
        RuleWithIPv4(
            condition="0.0.0.0/0",
            action="permit",
            command="routing route print detail without-paging where {target} in dst-address bgp and dst-address !=0.0.0.0/0",
            vrf_command="routing route print detail without-paging where {target} in dst-address bgp and dst-address !=0.0.0.0/0 and routing-table={vrf}",
        ),
        RuleWithIPv6(
            condition="::/0",
            action="permit",
            command="routing route print detail without-paging where {target} in dst-address bgp and dst-address !=::/0",
            vrf_command="routing route print detail without-paging where {target} in dst-address bgp and dst-address !=::/0 and routing-table={vrf}",
        ),
    ],
    field=Text(description="IP Address, Prefix, or Hostname"),
    platforms=PLATFORMS,
)

MikrotikBGPASPathTable = BuiltinDirective(
    id="__hyperglass_mikrotik_bgp_aspath_table__",
    name="BGP AS Path",
    rules=[
        RuleWithPattern(
            condition="*",
            action="permit",
            commands=[
                'routing route print detail without-paging where bgp and bgp.as-path~"{target}"',
            ],
            vrf_commands=[
                'routing route print detail without-paging where bgp and bgp.as-path~"{target}" and routing-table={vrf}',
            ],
        )
    ],
    field=Text(description="AS Path Regular Expression"),
    platforms=PLATFORMS,
)

MikrotikBGPCommunityTable = BuiltinDirective(
    id="__hyperglass_mikrotik_bgp_community_table__",
    name="BGP Community",
    rules=[
        RuleWithPattern(
            condition="*",
            action="permit",
            commands=[
                'routing route print detail without-paging where bgp and bgp.communities~"{target}"',
            ],
            vrf_commands=[
                'routing route print detail without-paging where bgp and bgp.communities~"{target}" and routing-table={vrf}',
            ],
        )
    ],
    field=Text(description="BGP Community String"),
    platforms=PLATFORMS,
)
