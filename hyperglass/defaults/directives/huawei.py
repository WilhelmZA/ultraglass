"""Default Huawei Directives."""

# Project
from hyperglass.models.directive import (
    Text,
    RuleWithIPv4,
    RuleWithIPv6,
    RuleWithPattern,
    BuiltinDirective,
)

__all__ = (
    "Huawei_BGPASPath",
    "Huawei_BGPCommunity",
    "Huawei_BGPRoute",
    "Huawei_Ping",
    "Huawei_Traceroute",
    "HuaweiBGPRouteTable",
    "HuaweiBGPASPathTable",
    "HuaweiBGPCommunityTable",
)

NAME = "Huawei VRP"
PLATFORMS = ["huawei", "huawei_vrpv8"]

Huawei_BGPRoute = BuiltinDirective(
    id="__hyperglass_huawei_bgp_route__",
    name="BGP Route",
    rules=[
        RuleWithIPv4(
            condition="0.0.0.0/0",
            action="permit",
            command="display bgp routing-table {target} | no-more",
            vrf_command="display bgp vpnv4 vpn-instance {vrf} routing-table {target} | no-more",
        ),
        RuleWithIPv6(
            condition="::/0",
            action="permit",
            command="display bgp ipv6 routing-table {target} | no-more",
            vrf_command="display bgp vpnv6 vpn-instance {vrf} routing-table {target} | no-more",
        ),
    ],
    field=Text(description="IP Address, Prefix, or Hostname"),
    plugins=["bgp_route_huawei", "bgp_routestr_huawei"],
    table_output="__hyperglass_huawei_bgp_route_table__",
    platforms=PLATFORMS,
)

Huawei_BGPASPath = BuiltinDirective(
    id="__hyperglass_huawei_bgp_aspath__",
    name="BGP AS Path",
    rules=[
        RuleWithPattern(
            condition="*",
            action="permit",
            commands=[
                "display bgp routing-table regular-expression {target}",
                "display bgp ipv6 routing-table regular-expression {target}",
            ],
            vrf_commands=[
                "display bgp vpnv4 vpn-instance {vrf} routing-table regular-expression {target}",
                "display bgp vpnv6 vpn-instance {vrf} routing-table regular-expression {target}",
            ],
        )
    ],
    field=Text(description="AS Path Regular Expression"),
    table_output="__hyperglass_huawei_bgp_aspath_table__",
    platforms=PLATFORMS,
)

Huawei_BGPCommunity = BuiltinDirective(
    id="__hyperglass_huawei_bgp_community__",
    name="BGP Community",
    rules=[
        RuleWithPattern(
            condition="*",
            action="permit",
            commands=[
                "display bgp routing-table community {target}",
                "display bgp ipv6 routing-table community {target}",
            ],
            vrf_commands=[
                "display bgp vpnv4 vpn-instance {vrf} routing-table community {target}",
                "display bgp vpnv6 vpn-instance {vrf} routing-table community {target}",
            ],
        )
    ],
    field=Text(description="BGP Community String"),
    table_output="__hyperglass_huawei_bgp_community_table__",
    platforms=PLATFORMS,
)

Huawei_Ping = BuiltinDirective(
    id="__hyperglass_huawei_ping__",
    name="Ping",
    rules=[
        RuleWithIPv4(
            condition="0.0.0.0/0",
            action="permit",
            command="ping -c 5 -a {source4} {target}",
            vrf_command="ping -c 5 -vpn-instance {vrf} {target}",
        ),
        RuleWithIPv6(
            condition="::/0",
            action="permit",
            command="ping ipv6 -c 5 -a {source6} {target}",
            # VRP 8 takes the IPv6 VPN instance keyword without a dash (#155).
            vrf_command="ping ipv6 -c 5 vpn-instance {vrf} {target}",
        ),
    ],
    field=Text(description="IP Address, Prefix, or Hostname"),
    platforms=PLATFORMS,
)

Huawei_Traceroute = BuiltinDirective(
    id="__hyperglass_huawei_traceroute__",
    name="Traceroute",
    rules=[
        RuleWithIPv4(
            condition="0.0.0.0/0",
            action="permit",
            command="tracert -w 500 -q 1 -f 1 -a {source4} {target}",
            vrf_command="tracert -w 500 -q 1 -f 1 -vpn-instance {vrf} {target}",
        ),
        RuleWithIPv6(
            condition="::/0",
            action="permit",
            command="tracert ipv6 -w 500 -q 1 -f 1 -a {source6} {target}",
            # The CE12800 (VRP 8.180) has no source option on `tracert ipv6` and rejects
            # `-a`, so it traces from its routed source address instead (#155).
            fallback_command="tracert ipv6 -w 500 -q 1 -f 1 {target}",
            vrf_command="tracert ipv6 -w 500 -q 1 -f 1 vpn-instance {vrf} {target}",
        ),
    ],
    field=Text(description="IP Address, Prefix, or Hostname"),
    platforms=PLATFORMS,
)

# Table Output Directives

HuaweiBGPRouteTable = BuiltinDirective(
    id="__hyperglass_huawei_bgp_route_table__",
    name="BGP Route",
    rules=[
        RuleWithIPv4(
            condition="0.0.0.0/0",
            action="permit",
            command="display bgp routing-table {target} | no-more",
            vrf_command="display bgp vpnv4 vpn-instance {vrf} routing-table {target} | no-more",
        ),
        RuleWithIPv6(
            condition="::/0",
            action="permit",
            command="display bgp ipv6 routing-table {target} | no-more",
            vrf_command="display bgp vpnv6 vpn-instance {vrf} routing-table {target} | no-more",
        ),
    ],
    field=Text(description="IP Address, Prefix, or Hostname"),
    platforms=PLATFORMS,
)

HuaweiBGPASPathTable = BuiltinDirective(
    id="__hyperglass_huawei_bgp_aspath_table__",
    name="BGP AS Path",
    rules=[
        RuleWithPattern(
            condition="*",
            action="permit",
            commands=[
                "display bgp routing-table regular-expression {target}",
                "display bgp ipv6 routing-table regular-expression {target}",
            ],
            vrf_commands=[
                "display bgp vpnv4 vpn-instance {vrf} routing-table regular-expression {target}",
                "display bgp vpnv6 vpn-instance {vrf} routing-table regular-expression {target}",
            ],
        )
    ],
    field=Text(description="AS Path Regular Expression"),
    platforms=PLATFORMS,
)

HuaweiBGPCommunityTable = BuiltinDirective(
    id="__hyperglass_huawei_bgp_community_table__",
    name="BGP Community",
    rules=[
        RuleWithPattern(
            condition="*",
            action="permit",
            commands=[
                "display bgp routing-table community {target}",
                "display bgp ipv6 routing-table community {target}",
            ],
            vrf_commands=[
                "display bgp vpnv4 vpn-instance {vrf} routing-table community {target}",
                "display bgp vpnv6 vpn-instance {vrf} routing-table community {target}",
            ],
        )
    ],
    field=Text(description="BGP Community String"),
    platforms=PLATFORMS,
)
