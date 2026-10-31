"""PAN-OS classic virtual-router BGP and source-selected diagnostics."""

# Project
from hyperglass.models.directive import Text, RuleWithIPv4, RuleWithIPv6, BuiltinDirective

__all__ = ("PANOS_BGPRoute", "PANOS_BGPRouteTable", "PANOS_Ping", "PANOS_Traceroute")
NAME = "Palo Alto PAN-OS"
PLATFORMS = ["paloalto_panos"]

PANOS_BGPRoute = BuiltinDirective(
    id="__hyperglass_paloalto_panos_bgp_route__",
    name="BGP Route",
    platforms=PLATFORMS,
    table_output="__hyperglass_paloalto_panos_bgp_route_table__",
    field=Text(description="Exact prefix (addresses query /32 or /128)"),
    rules=[
        RuleWithIPv4(
            condition="0.0.0.0/0",
            command="show routing protocol bgp loc-rib-detail prefix {target} virtual-router default afi ipv4 safi unicast",
            vrf_command="show routing protocol bgp loc-rib-detail prefix {target} virtual-router {vrf} afi ipv4 safi unicast",
        ),
        RuleWithIPv6(
            condition="::/0",
            command="show routing protocol bgp loc-rib-detail prefix {target} virtual-router default afi ipv6 safi unicast",
            vrf_command="show routing protocol bgp loc-rib-detail prefix {target} virtual-router {vrf} afi ipv6 safi unicast",
        ),
    ],
)
PANOS_BGPRouteTable = PANOS_BGPRoute.model_copy(
    deep=True, update={"id": "__hyperglass_paloalto_panos_bgp_route_table__", "table_output": None}
)
PANOS_Ping = BuiltinDirective(
    id="__hyperglass_paloalto_panos_ping__",
    name="Ping",
    platforms=PLATFORMS,
    field=Text(description="IP address or hostname"),
    rules=[
        RuleWithIPv4(condition="0.0.0.0/0", command="ping count 5 source {source4} host {target}"),
        RuleWithIPv6(
            condition="::/0", command="ping count 5 inet6 yes source {source6} host {target}"
        ),
    ],
)
PANOS_Traceroute = BuiltinDirective(
    id="__hyperglass_paloalto_panos_traceroute__",
    name="Traceroute",
    platforms=PLATFORMS,
    field=Text(description="IP address or hostname"),
    rules=[
        RuleWithIPv4(
            condition="0.0.0.0/0",
            command="traceroute ipv4 yes max-ttl 30 wait 1 no-resolve yes source {source4} host {target}",
        ),
        RuleWithIPv6(
            condition="::/0",
            command="traceroute ipv6 yes max-ttl 30 wait 1 no-resolve yes source {source6} host {target}",
        ),
    ],
)
