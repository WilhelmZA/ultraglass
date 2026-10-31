"""Parse numbered traceroute output from Linux and network device CLIs."""

import re
import typing as t
from ipaddress import ip_address

from pydantic import PrivateAttr

from hyperglass.state import use_state
from hyperglass.models.data.traceroute import TracerouteHop, TracerouteResult
from hyperglass.plugins._output import OutputPlugin

PLATFORMS = (
    "arista_eos",
    "juniper",
    "cisco_ios",
    "cisco_xr",
    "cisco_nxos",
    "bird",
    "openbgpd",
    "vyos",
    "vyos_1_3",
    "tnsr",
    "nokia_sros",
    "extreme_exos",
    "extreme_vsp",
    "hp_comware",
    "ipinfusion_ocnos",
    "aruba_aoscx",
    "dell_os10",
)


def parse_standard_traceroute(text: str, target: str, source: str) -> TracerouteResult:
    """Preserve timeout probes, IPv6 hops and raw MPLS annotations."""
    hops = []
    for line in text.splitlines():
        match = re.match(r"^\s*(\d+)\s+(.+)$", line)
        if not match:
            continue
        number, body = match.groups()
        # MPLS labels are not RTT values or hop addresses.
        body = re.sub(r"<MPLS:[^>]*>|\[MPLS:[^\]]*\]", "", body)
        address = None
        hostname = None
        previous = None
        for token in body.split():
            try:
                address = str(ip_address(token.strip("()")))
                if token.startswith("(") and previous != address:
                    hostname = previous
                break
            except ValueError:
                previous = token
        probes = re.findall(r"\*|(?<![\w.:])<?\d+(?:\.\d+)?\s*(?:msec|ms)\b", body)
        if not probes:
            raise ValueError("Unrecognized traceroute hop")
        rtts = [
            None if probe == "*" else float(re.search(r"\d+(?:\.\d+)?", probe)[0])
            for probe in probes[:3]
        ]
        rtts += [None] * (3 - len(rtts))
        hops.append(
            TracerouteHop(
                hop_number=int(number),
                ip_address=address,
                hostname=hostname,
                rtt1=rtts[0],
                rtt2=rtts[1],
                rtt3=rtts[2],
                sent_count=min(len(probes), 3),
            )
        )
    if not hops:
        raise ValueError("No numbered traceroute hops")
    return TracerouteResult(target=target, source=source, hops=hops, raw_output=text)


class TraceroutePluginStandard(OutputPlugin):
    """Parse standard traceroute formats and retain unfamiliar output as text."""

    _hyperglass_builtin: bool = PrivateAttr(True)
    platforms: t.Sequence[str] = PLATFORMS
    directives: t.Sequence[str] = tuple(f"__hyperglass_{p}_traceroute__" for p in PLATFORMS)

    def process(self, *, output, query):
        """Apply the device and global structured-output settings."""
        if not query.device.structured_output:
            return output
        params = use_state("params")
        if params.structured.enable_for_traceroute is False:
            return output
        text = output if isinstance(output, str) else "\n".join(output)
        try:
            return parse_standard_traceroute(text, str(query.query_target), query.device.name)
        except ValueError:
            return output
