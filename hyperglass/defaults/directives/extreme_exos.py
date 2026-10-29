"""Default Extreme Networks EXOS Directives."""

# Project
from hyperglass.models.directive import (
    Text,
    RuleWithIPv4,
    RuleWithIPv6,
    RuleWithPattern,
    BuiltinDirective,
)

__all__ = (
    "ExtremeEXOS_BGPASPath",
    "ExtremeEXOS_BGPCommunity",
    "ExtremeEXOS_BGPRoute",
    "ExtremeEXOS_Ping",
    "ExtremeEXOS_Traceroute",
    "ExtremeEXOS_BGPRouteTable",
    "ExtremeEXOS_BGPASPathTable",
    "ExtremeEXOS_BGPCommunityTable",
)

NAME = "Extreme EXOS"
PLATFORMS = ["extreme_exos"]

# EXOS has no longest-match BGP lookup for an address; `network` needs the prefix.
def _route_rules():
    return [
        RuleWithIPv4(
            condition="0.0.0.0/0",
            action="permit",
            le=31,
            command="show bgp routes detail ipv4-unicast network {target} exact",
            vrf_command="show bgp routes detail ipv4-unicast network {target} exact vr {vrf}",
        ),
        RuleWithIPv6(
            condition="::/0",
            action="permit",
            le=127,
            command="show bgp routes detail ipv6-unicast network {target} exact",
            vrf_command="show bgp routes detail ipv6-unicast network {target} exact vr {vrf}",
        ),
    ]

def _aspath_rules():
    return [
        RuleWithPattern(
            condition="*",
            action="permit",
            commands=[
                'show bgp routes detail ipv4-unicast as-path "{target}"',
                'show bgp routes detail ipv6-unicast as-path "{target}"',
            ],
            vrf_commands=[
                'show bgp routes detail ipv4-unicast as-path "{target}" vr {vrf}',
                'show bgp routes detail ipv6-unicast as-path "{target}" vr {vrf}',
            ],
        )
    ]

# The community target reaches the device as `AS : value`; see the EXOS formatter.
def _community_rules():
    return [
        RuleWithPattern(
            condition="*",
            action="permit",
            commands=[
                "show bgp routes detail ipv4-unicast community {target}",
                "show bgp routes detail ipv6-unicast community {target}",
            ],
            vrf_commands=[
                "show bgp routes detail ipv4-unicast community {target} vr {vrf}",
                "show bgp routes detail ipv6-unicast community {target} vr {vrf}",
            ],
        )
    ]

ExtremeEXOS_BGPRoute = BuiltinDirective(
    id="__hyperglass_extreme_exos_bgp_route__",
    table_output="__hyperglass_extreme_exos_bgp_route_table__",
    name="BGP Route",
    rules=_route_rules(),
    field=Text(description="IP Prefix"),
    platforms=PLATFORMS,
)

ExtremeEXOS_BGPASPath = BuiltinDirective(
    id="__hyperglass_extreme_exos_bgp_aspath__",
    table_output="__hyperglass_extreme_exos_bgp_aspath_table__",
    name="BGP AS Path",
    rules=_aspath_rules(),
    field=Text(description="AS Path Regular Expression"),
    platforms=PLATFORMS,
)

ExtremeEXOS_BGPCommunity = BuiltinDirective(
    id="__hyperglass_extreme_exos_bgp_community__",
    table_output="__hyperglass_extreme_exos_bgp_community_table__",
    name="BGP Community",
    rules=_community_rules(),
    field=Text(description="BGP Community String"),
    platforms=PLATFORMS,
)

ExtremeEXOS_Ping = BuiltinDirective(
    id="__hyperglass_extreme_exos_ping__",
    name="Ping",
    rules=[
        RuleWithIPv4(
            condition="0.0.0.0/0",
            action="permit",
            command="ping count 5 {target} from {source4}",
            vrf_command="ping vr {vrf} count 5 {target} from {source4}",
        ),
        RuleWithIPv6(
            condition="::/0",
            action="permit",
            command="ping count 5 ipv6 {target} from {source6}",
            vrf_command="ping vr {vrf} count 5 ipv6 {target} from {source6}",
        ),
    ],
    field=Text(description="IP Address, Prefix, or Hostname"),
    platforms=PLATFORMS,
)

ExtremeEXOS_Traceroute = BuiltinDirective(
    id="__hyperglass_extreme_exos_traceroute__",
    name="Traceroute",
    rules=[
        RuleWithIPv4(
            condition="0.0.0.0/0",
            action="permit",
            command="traceroute {target} from {source4}",
            vrf_command="traceroute vr {vrf} {target} from {source4}",
        ),
        RuleWithIPv6(
            condition="::/0",
            action="permit",
            command="traceroute ipv6 {target} from {source6}",
            vrf_command="traceroute vr {vrf} ipv6 {target} from {source6}",
        ),
    ],
    field=Text(description="IP Address, Prefix, or Hostname"),
    platforms=PLATFORMS,
)

# Table Output Directives

ExtremeEXOS_BGPRouteTable = BuiltinDirective(
    id="__hyperglass_extreme_exos_bgp_route_table__",
    name="BGP Route",
    rules=_route_rules(),
    field=Text(description="IP Prefix"),
    platforms=PLATFORMS,
)

ExtremeEXOS_BGPASPathTable = BuiltinDirective(
    id="__hyperglass_extreme_exos_bgp_aspath_table__",
    name="BGP AS Path",
    rules=_aspath_rules(),
    field=Text(description="AS Path Regular Expression"),
    platforms=PLATFORMS,
)

ExtremeEXOS_BGPCommunityTable = BuiltinDirective(
    id="__hyperglass_extreme_exos_bgp_community_table__",
    name="BGP Community",
    rules=_community_rules(),
    field=Text(description="BGP Community String"),
    platforms=PLATFORMS,
)
