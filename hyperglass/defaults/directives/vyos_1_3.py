"""Default VyOS 1.3 Directives.

VyOS 1.3 uses the older `show ip bgp` / `show ipv6 bgp` syntax, and its traceroute has
no source option. Syntax from the upstream report in thatmattlove/hyperglass#245.
"""

# Project
from hyperglass.models.directive import (
    Text,
    RuleWithIPv4,
    RuleWithIPv6,
    RuleWithPattern,
    BuiltinDirective,
)

__all__ = (
    "VyOS13_BGPASPath",
    "VyOS13_BGPCommunity",
    "VyOS13_BGPRoute",
    "VyOS13_Ping",
    "VyOS13_Traceroute",
)

NAME = "VyOS 1.3"
PLATFORMS = ["vyos_1_3"]

VyOS13_BGPRoute = BuiltinDirective(
    id="__hyperglass_vyos_1_3_bgp_route__",
    name="BGP Route",
    rules=[
        RuleWithIPv4(
            condition="0.0.0.0/0",
            action="permit",
            command="show ip bgp {target}",
        ),
        RuleWithIPv6(
            condition="::/0",
            action="permit",
            command="show ipv6 bgp {target}",
        ),
    ],
    field=Text(description="IP Address, Prefix, or Hostname"),
    platforms=PLATFORMS,
)

VyOS13_BGPASPath = BuiltinDirective(
    id="__hyperglass_vyos_1_3_bgp_aspath__",
    name="BGP AS Path",
    rules=[
        RuleWithPattern(
            condition="*",
            action="permit",
            commands=[
                "show ip bgp regexp {target}",
                "show ipv6 bgp regexp {target}",
            ],
        )
    ],
    field=Text(description="AS Path Regular Expression"),
    platforms=PLATFORMS,
)

VyOS13_BGPCommunity = BuiltinDirective(
    id="__hyperglass_vyos_1_3_bgp_community__",
    name="BGP Community",
    rules=[
        RuleWithPattern(
            condition="*",
            action="permit",
            commands=[
                "show ip bgp community {target}",
                "show ipv6 bgp community {target}",
            ],
        )
    ],
    field=Text(description="BGP Community String"),
    platforms=PLATFORMS,
)

VyOS13_Ping = BuiltinDirective(
    id="__hyperglass_vyos_1_3_ping__",
    name="Ping",
    rules=[
        RuleWithIPv4(
            condition="0.0.0.0/0",
            action="permit",
            command="ping {target} count 5 interface {source4}",
        ),
        RuleWithIPv6(
            condition="::/0",
            action="permit",
            command="ping {target} count 5 interface {source6}",
        ),
    ],
    field=Text(description="IP Address, Prefix, or Hostname"),
    platforms=PLATFORMS,
)

VyOS13_Traceroute = BuiltinDirective(
    id="__hyperglass_vyos_1_3_traceroute__",
    name="Traceroute",
    rules=[
        RuleWithIPv4(
            condition="0.0.0.0/0",
            action="permit",
            command="traceroute {target}",
        ),
        RuleWithIPv6(
            condition="::/0",
            action="permit",
            command="traceroute {target}",
        ),
    ],
    field=Text(description="IP Address, Prefix, or Hostname"),
    platforms=PLATFORMS,
)
