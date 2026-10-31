"""Cumulus Linux FRR commands and Linux network diagnostics."""

# Project
from hyperglass.models.directive import BuiltinDirective
from hyperglass.defaults.directives import frr

__all__ = (
    "Cumulus_BGPRoute",
    "Cumulus_BGPASPath",
    "Cumulus_BGPCommunity",
    "Cumulus_Ping",
    "Cumulus_Traceroute",
    "Cumulus_BGPRouteTable",
    "Cumulus_BGPASPathTable",
    "Cumulus_BGPCommunityTable",
)

NAME = "NVIDIA Cumulus Linux"
PLATFORMS = ["cumulus_linux"]


def _cumulus(directive: BuiltinDirective) -> BuiltinDirective:
    """Copy FRR rules, using non-interactive sudo and explicit diagnostic VRFs."""
    update = {"id": directive.id.replace("_frr_", "_cumulus_linux_"), "platforms": PLATFORMS}
    if directive.table_output:
        update["table_output"] = directive.table_output.replace("_frr_", "_cumulus_linux_")
    result = directive.model_copy(deep=True, update=update)
    for rule in result.rules:
        if result.query_kind in ("ping", "traceroute"):
            # SSH can enter the management VRF. Always select the queried routing context.
            rule.vrf_commands = ["sudo -n ip vrf exec {vrf} " + cmd for cmd in rule.commands]
            rule.commands = ["sudo -n ip vrf exec default " + cmd for cmd in rule.commands]
        else:
            rule.commands = ["sudo -n " + cmd for cmd in rule.commands]
            rule.vrf_commands = ["sudo -n " + cmd for cmd in rule.vrf_commands]
    return result


Cumulus_BGPRoute = _cumulus(frr.FRRouting_BGPRoute)
Cumulus_BGPASPath = _cumulus(frr.FRRouting_BGPASPath)
Cumulus_BGPCommunity = _cumulus(frr.FRRouting_BGPCommunity)
Cumulus_Ping = _cumulus(frr.FRRouting_Ping)
Cumulus_Traceroute = _cumulus(frr.FRRouting_Traceroute)
Cumulus_BGPRouteTable = _cumulus(frr.FRRouting_BGPRouteTable)
Cumulus_BGPASPathTable = _cumulus(frr.FRRouting_BGPASPathTable)
Cumulus_BGPCommunityTable = _cumulus(frr.FRRouting_BGPCommunityTable)
