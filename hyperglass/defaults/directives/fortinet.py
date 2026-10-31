"""FortiOS queries in the account's current VDOM and routing context."""

# Project
from hyperglass.models.directive import Text, RuleWithIPv4, RuleWithIPv6, BuiltinDirective

__all__ = ("Fortinet_BGPRoute", "Fortinet_BGPRouteTable", "Fortinet_Ping", "Fortinet_Traceroute")
NAME = "Fortinet FortiGate"
PLATFORMS = ["fortinet"]

Fortinet_BGPRoute = BuiltinDirective(
    id="__hyperglass_fortinet_bgp_route__",
    name="BGP Route",
    platforms=PLATFORMS,
    table_output="__hyperglass_fortinet_bgp_route_table__",
    field=Text(description="IP address or prefix"),
    rules=[
        RuleWithIPv4(condition="0.0.0.0/0", command="get router info bgp network {target}"),
        RuleWithIPv6(condition="::/0", command="get router info6 bgp network {target}"),
    ],
)
Fortinet_BGPRouteTable = Fortinet_BGPRoute.model_copy(
    deep=True, update={"id": "__hyperglass_fortinet_bgp_route_table__", "table_output": None}
)
Fortinet_Ping = BuiltinDirective(
    id="__hyperglass_fortinet_ping__",
    name="Ping",
    platforms=PLATFORMS,
    field=Text(description="IP address or hostname"),
    rules=[
        RuleWithIPv4(
            condition="0.0.0.0/0",
            commands=[
                "execute ping-options reset",
                "execute ping-options repeat-count 5",
                "execute ping-options timeout 1",
                "execute ping-options source {source4}",
                "execute ping {target}",
                "execute ping-options reset",
            ],
        ),
        RuleWithIPv6(
            condition="::/0",
            commands=[
                "execute ping6-options reset",
                "execute ping6-options repeat-count 5",
                "execute ping6-options timeout 1",
                "execute ping6-options source6 {source6}",
                "execute ping6 {target}",
                "execute ping6-options reset",
            ],
        ),
    ],
)
Fortinet_Traceroute = BuiltinDirective(
    id="__hyperglass_fortinet_traceroute__",
    name="Traceroute",
    platforms=PLATFORMS,
    field=Text(description="IP address or hostname"),
    rules=[
        RuleWithIPv4(
            condition="0.0.0.0/0",
            commands=[
                "execute traceroute-options reset",
                "execute traceroute-options queries 1",
                "execute traceroute-options source {source4}",
                "execute traceroute {target}",
                "execute traceroute-options reset",
            ],
        ),
        RuleWithIPv6(condition="::/0", command="execute tracert6 {target}"),
    ],
)
