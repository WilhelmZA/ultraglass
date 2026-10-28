"""Default FRRouting Directives."""

# Project
from hyperglass.models.directive import (
    Text,
    RuleWithIPv4,
    RuleWithIPv6,
    RuleWithPattern,
    BuiltinDirective,
)

__all__ = (
    "OpenBGPD_BGPASPath",
    "OpenBGPD_BGPCommunity",
    "OpenBGPD_BGPRoute",
    "OpenBGPD_Ping",
    "OpenBGPD_Traceroute",
    "OpenBGPD_BGPRouteTable",
    "OpenBGPD_BGPASPathTable",
    "OpenBGPD_BGPCommunityTable",
)

NAME = "OpenBGPD"
PLATFORMS = ["openbgpd"]

OpenBGPD_BGPRoute = BuiltinDirective(
    id="__hyperglass_openbgpd_bgp_route__",
    name="BGP Route",
    rules=[
        RuleWithIPv4(
            condition="0.0.0.0/0",
            action="permit",
            command="bgpctl show rib inet {target}",
        ),
        RuleWithIPv6(
            condition="::/0",
            action="permit",
            command="bgpctl show rib inet6 {target}",
        ),
    ],
    field=Text(description="IP Address, Prefix, or Hostname"),
    table_output="__hyperglass_openbgpd_bgp_route_table__",
    platforms=PLATFORMS,
)

OpenBGPD_BGPASPath = BuiltinDirective(
    id="__hyperglass_openbgpd_bgp_aspath__",
    name="BGP AS Path",
    rules=[
        RuleWithPattern(
            condition=r"^_?[0-9]+\$$",
            action="permit",
            commands=[
                "bgpctl show rib inet source-as {target}",
                "bgpctl show rib inet6 source-as {target}",
            ],
        ),
        RuleWithPattern(
            condition=r"^\^[0-9]+_$",
            action="permit",
            commands=[
                "bgpctl show rib inet peer-as {target}",
                "bgpctl show rib inet6 peer-as {target}",
            ],
        ),
        RuleWithPattern(
            condition=r"^(?:[0-9]+|_[0-9]+_)$",
            action="permit",
            commands=[
                "bgpctl show rib inet as {target}",
                "bgpctl show rib inet6 as {target}",
            ],
        )
    ],
    field=Text(description="ASN, _ASN_, _ASN$, or ^ASN_"),
    table_output="__hyperglass_openbgpd_bgp_aspath_table__",
    platforms=PLATFORMS,
)

OpenBGPD_BGPCommunity = BuiltinDirective(
    id="__hyperglass_openbgpd_bgp_community__",
    name="BGP Community",
    rules=[
        RuleWithPattern(
            condition="*",
            action="permit",
            commands=[
                "bgpctl show rib inet community {target}",
                "bgpctl show rib inet6 community {target}",
            ],
        )
    ],
    field=Text(description="BGP Community String"),
    table_output="__hyperglass_openbgpd_bgp_community_table__",
    platforms=PLATFORMS,
)

OpenBGPD_Ping = BuiltinDirective(
    id="__hyperglass_openbgpd_ping__",
    name="Ping",
    rules=[
        RuleWithIPv4(
            condition="0.0.0.0/0",
            action="permit",
            command="ping -4 -c 5 -I {source4} {target}",
        ),
        RuleWithIPv6(
            condition="::/0",
            action="permit",
            command="ping -6 -c 5 -I {source6} {target}",
        ),
    ],
    field=Text(description="IP Address, Prefix, or Hostname"),
    platforms=PLATFORMS,
)

OpenBGPD_Traceroute = BuiltinDirective(
    id="__hyperglass_openbgpd_traceroute__",
    name="Traceroute",
    rules=[
        RuleWithIPv4(
            condition="0.0.0.0/0",
            action="permit",
            command="traceroute -4 -w 1 -q 1 -s {source4} {target}",
        ),
        RuleWithIPv6(
            condition="::/0",
            action="permit",
            command="traceroute -6 -w 1 -q 1 -s {source6} {target}",
        ),
    ],
    field=Text(description="IP Address, Prefix, or Hostname"),
    platforms=PLATFORMS,
)

# Table Output Directives
# `bgpctl -j show rib detail` returns JSON with communities for every path.

OpenBGPD_BGPRouteTable = BuiltinDirective(
    id="__hyperglass_openbgpd_bgp_route_table__",
    name="BGP Route",
    rules=[
        RuleWithIPv4(
            condition="0.0.0.0/0",
            action="permit",
            command="bgpctl -j show rib detail inet {target}",
        ),
        RuleWithIPv6(
            condition="::/0",
            action="permit",
            command="bgpctl -j show rib detail inet6 {target}",
        ),
    ],
    field=Text(description="IP Address, Prefix, or Hostname"),
    platforms=PLATFORMS,
)

OpenBGPD_BGPASPathTable = BuiltinDirective(
    id="__hyperglass_openbgpd_bgp_aspath_table__",
    name="BGP AS Path",
    rules=[
        RuleWithPattern(
            condition=r"^_?[0-9]+\$$",
            action="permit",
            commands=[
                "bgpctl -j show rib detail inet source-as {target}",
                "bgpctl -j show rib detail inet6 source-as {target}",
            ],
        ),
        RuleWithPattern(
            condition=r"^\^[0-9]+_$",
            action="permit",
            commands=[
                "bgpctl -j show rib detail inet peer-as {target}",
                "bgpctl -j show rib detail inet6 peer-as {target}",
            ],
        ),
        RuleWithPattern(
            condition=r"^(?:[0-9]+|_[0-9]+_)$",
            action="permit",
            commands=[
                "bgpctl -j show rib detail inet as {target}",
                "bgpctl -j show rib detail inet6 as {target}",
            ],
        )
    ],
    field=Text(description="ASN, _ASN_, _ASN$, or ^ASN_"),
    platforms=PLATFORMS,
)

OpenBGPD_BGPCommunityTable = BuiltinDirective(
    id="__hyperglass_openbgpd_bgp_community_table__",
    name="BGP Community",
    rules=[
        RuleWithPattern(
            condition="*",
            action="permit",
            commands=[
                "bgpctl -j show rib detail inet community {target}",
                "bgpctl -j show rib detail inet6 community {target}",
            ],
        )
    ],
    field=Text(description="BGP Community String"),
    platforms=PLATFORMS,
)
