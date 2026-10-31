"""Comware 7 unicast route lookup and network diagnostics."""

# Project
from hyperglass.models.directive import Text, RuleWithIPv4, RuleWithIPv6, BuiltinDirective

__all__ = ("Comware_BGPRoute", "Comware_BGPRouteTable", "Comware_Ping", "Comware_Traceroute")
NAME = "HPE Comware 7"
PLATFORMS = ["hp_comware"]

Comware_BGPRoute = BuiltinDirective(
    id="__hyperglass_hp_comware_bgp_route__",
    name="BGP Route",
    platforms=PLATFORMS,
    field=Text(description="Exact IP prefix (addresses query /32 or /128)"),
    table_output="__hyperglass_hp_comware_bgp_route_table__",
    rules=[
        RuleWithIPv4(
            condition="0.0.0.0/0",
            command="display bgp routing-table ipv4 unicast {target}",
            vrf_command="display bgp routing-table ipv4 unicast vpn-instance {vrf} {target}",
        ),
        RuleWithIPv6(
            condition="::/0",
            command="display bgp routing-table ipv6 unicast {target}",
            vrf_command="display bgp routing-table ipv6 unicast vpn-instance {vrf} {target}",
        ),
    ],
)
Comware_BGPRouteTable = Comware_BGPRoute.model_copy(
    deep=True, update={"id": "__hyperglass_hp_comware_bgp_route_table__", "table_output": None}
)
Comware_Ping = BuiltinDirective(
    id="__hyperglass_hp_comware_ping__",
    name="Ping",
    platforms=PLATFORMS,
    field=Text(description="IP address or hostname"),
    rules=[
        RuleWithIPv4(
            condition="0.0.0.0/0",
            command="ping -c 5 -a {source4} {target}",
            vrf_command="ping -c 5 -vpn-instance {vrf} -a {source4} {target}",
        ),
        RuleWithIPv6(
            condition="::/0",
            command="ping ipv6 -c 5 -a {source6} {target}",
            vrf_command="ping ipv6 -c 5 -vpn-instance {vrf} -a {source6} {target}",
        ),
    ],
)
Comware_Traceroute = BuiltinDirective(
    id="__hyperglass_hp_comware_traceroute__",
    name="Traceroute",
    platforms=PLATFORMS,
    field=Text(description="IP address or hostname"),
    rules=[
        RuleWithIPv4(
            condition="0.0.0.0/0",
            command="tracert -w 500 -q 1 -a {source4} {target}",
            vrf_command="tracert -w 500 -q 1 -vpn-instance {vrf} -a {source4} {target}",
        ),
        RuleWithIPv6(
            condition="::/0",
            # Some Comware 7 releases have no IPv6 source-address option.
            command="tracert ipv6 -w 500 -q 1 {target}",
            vrf_command="tracert ipv6 -w 500 -q 1 -vpn-instance {vrf} {target}",
        ),
    ],
)
