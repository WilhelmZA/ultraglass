"""Arrcus ArcOS BGP commands over ConfD OpenConfig JSON."""

# Project
from hyperglass.models.directive import (
    Text,
    RuleWithIPv4,
    RuleWithIPv6,
    BuiltinDirective,
)

__all__ = ("ARCOS_BGPRoute", "ARCOS_BGPRouteTable")
NAME = "Arrcus ArcOS"
PLATFORMS = ["arrcus_arcos"]

# The documented ConfD show path returns the BGP protocol instance as OpenConfig JSON.
# Prefix filtering happens in the structured parser. The vendor default instance name is BGP.
_SHOW = "echo 'show network-instance default protocol BGP BGP | display json' | confd_cli -C"
_SHOW_VRF = "echo 'show network-instance {vrf} protocol BGP BGP | display json' | confd_cli -C"

ARCOS_BGPRoute = BuiltinDirective(
    id="__hyperglass_arrcus_arcos_bgp_route__",
    name="BGP Route",
    platforms=PLATFORMS,
    table_output="__hyperglass_arrcus_arcos_bgp_route_table__",
    field=Text(description="Exact prefix (addresses query /32 or /128)"),
    rules=[
        RuleWithIPv4(
            condition="0.0.0.0/0",
            command=_SHOW,
            vrf_command=_SHOW_VRF,
        ),
        RuleWithIPv6(
            condition="::/0",
            command=_SHOW,
            vrf_command=_SHOW_VRF,
        ),
    ],
)
ARCOS_BGPRouteTable = ARCOS_BGPRoute.model_copy(
    deep=True,
    update={"id": "__hyperglass_arrcus_arcos_bgp_route_table__", "table_output": None},
)
