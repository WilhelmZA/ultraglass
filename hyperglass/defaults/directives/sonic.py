"""Default SONiC Directives.

Community SONiC runs FRR for BGP behind a Linux shell, so it uses the FRRouting
commands under its own directive IDs.
"""

# Project
from hyperglass.models.directive import BuiltinDirective
from hyperglass.defaults.directives import frr

__all__ = (
    "SONiC_BGPASPath",
    "SONiC_BGPCommunity",
    "SONiC_BGPRoute",
    "SONiC_Ping",
    "SONiC_Traceroute",
    "SONiC_BGPRouteTable",
    "SONiC_BGPASPathTable",
    "SONiC_BGPCommunityTable",
)

NAME = "SONiC"
PLATFORMS = ["sonic"]


def _sonic(directive: BuiltinDirective) -> BuiltinDirective:
    """Copy an FRRouting directive, with its own rules, for SONiC."""
    update = {"id": directive.id.replace("_frr_", "_sonic_"), "platforms": PLATFORMS}
    if directive.table_output:
        update["table_output"] = directive.table_output.replace("_frr_", "_sonic_")
    return directive.model_copy(deep=True, update=update)


SONiC_BGPRoute = _sonic(frr.FRRouting_BGPRoute)
SONiC_BGPASPath = _sonic(frr.FRRouting_BGPASPath)
SONiC_BGPCommunity = _sonic(frr.FRRouting_BGPCommunity)
SONiC_Ping = _sonic(frr.FRRouting_Ping)
SONiC_Traceroute = _sonic(frr.FRRouting_Traceroute)

# Table Output Directives

SONiC_BGPRouteTable = _sonic(frr.FRRouting_BGPRouteTable)
SONiC_BGPASPathTable = _sonic(frr.FRRouting_BGPASPathTable)
SONiC_BGPCommunityTable = _sonic(frr.FRRouting_BGPCommunityTable)
