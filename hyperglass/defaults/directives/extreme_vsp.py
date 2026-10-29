"""Default Extreme Networks VOSS (VSP and Fabric Engine) Directives.

VOSS has no BGP filter for an AS path or a community, so only route, ping and
traceroute are built in. BGP output stays as text: VOSS marks no best path.
"""

# Project
from hyperglass.models.directive import (
    Text,
    RuleWithIPv4,
    RuleWithIPv6,
    BuiltinDirective,
)

__all__ = (
    "ExtremeVSP_BGPRoute",
    "ExtremeVSP_Ping",
    "ExtremeVSP_Traceroute",
)

NAME = "Extreme VOSS"
PLATFORMS = ["extreme_vsp"]

ExtremeVSP_BGPRoute = BuiltinDirective(
    id="__hyperglass_extreme_vsp_bgp_route__",
    name="BGP Route",
    rules=[
        # VOSS matches a host address exactly, not by longest match, so it needs the prefix.
        RuleWithIPv4(
            condition="0.0.0.0/0",
            action="permit",
            le=31,
            command="show ip bgp route {target} community enable",
            vrf_command="show ip bgp route {target} community enable vrf {vrf}",
        ),
        RuleWithIPv6(
            condition="::/0",
            action="permit",
            le=127,
            command="show bgp ipv6 route {target} community enable",
            vrf_command="show bgp ipv6 route {target} community enable vrf {vrf}",
        ),
    ],
    field=Text(description="IP Prefix"),
    platforms=PLATFORMS,
)

ExtremeVSP_Ping = BuiltinDirective(
    id="__hyperglass_extreme_vsp_ping__",
    name="Ping",
    rules=[
        RuleWithIPv4(
            condition="0.0.0.0/0",
            action="permit",
            command="ping {target} count 5 source {source4}",
            vrf_command="ping {target} count 5 vrf {vrf} source {source4}",
        ),
        RuleWithIPv6(
            condition="::/0",
            action="permit",
            command="ping {target} count 5 source {source6}",
            vrf_command="ping {target} count 5 vrf {vrf} source {source6}",
        ),
    ],
    field=Text(description="IP Address, Prefix, or Hostname"),
    platforms=PLATFORMS,
)

ExtremeVSP_Traceroute = BuiltinDirective(
    id="__hyperglass_extreme_vsp_traceroute__",
    name="Traceroute",
    rules=[
        RuleWithIPv4(
            condition="0.0.0.0/0",
            action="permit",
            command="traceroute {target} source {source4}",
            vrf_command="traceroute {target} vrf {vrf} source {source4}",
        ),
        RuleWithIPv6(
            condition="::/0",
            action="permit",
            command="traceroute {target} source {source6}",
            vrf_command="traceroute {target} vrf {vrf} source {source6}",
        ),
    ],
    field=Text(description="IP Address, Prefix, or Hostname"),
    platforms=PLATFORMS,
)
