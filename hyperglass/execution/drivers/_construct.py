"""Construct SSH command/API parameters from validated query data.

Accepts filtered & validated input from execute.py, constructs SSH
command for Netmiko library or API call parameters for supported
hyperglass API modules.
"""

# Standard Library
import re
import shlex
import json as _json
import typing as t
import ipaddress

# Project
from hyperglass.log import log
from hyperglass.util import get_fmt_keys
from hyperglass.constants import TRANSPORT_REST, TARGET_FORMAT_SPACE
from hyperglass.exceptions.public import InputInvalid
from hyperglass.exceptions.private import ConfigError

if t.TYPE_CHECKING:
    # Third Party
    from loguru import Logger

    # Project
    from hyperglass.models.api.query import Query
    from hyperglass.models.directive import Directive
    from hyperglass.models.config.devices import Device

FormatterCallback = t.Callable[[str], t.Union[t.List[str], str]]


class Construct:
    """Construct SSH commands/REST API parameters from validated query data."""

    directive: "Directive"
    device: "Device"
    query: "Query"
    transport: str
    target: str
    _log: "Logger"

    def __init__(self, device: "Device", query: "Query"):
        """Initialize command construction."""
        self._log = log.bind(type=query.query_type, target=query.query_target)
        self._log.debug("Constructing query")
        self.query = query
        self.device = device
        self.target = self.query.query_target
        self.directive = query.directive

        # Recheck built-ins at the execution boundary, including transformed input.
        if self.directive._hyperglass_builtin:
            self.directive.validate_target(self.query.query_target)

        # Set transport method based on NOS type
        self.transport = "scrape"
        if self.device.platform in TRANSPORT_REST:
            self.transport = "rest"

        # Remove slashes from target for required platforms
        if self.device.platform in TARGET_FORMAT_SPACE:
            self.target = re.sub(r"\/", r" ", str(self.query.query_target))

        with Formatter(self.query) as formatter:
            self.target = formatter(self.prepare_target())

    def prepare_target(self) -> t.Union[t.List[str], str]:
        """Format the query target based on directive parameters."""
        if isinstance(self.query.query_target, t.List):
            # Directive can accept multiple values in a single command.
            if self.directive.multiple:
                return self.directive.multiple_separator.join(self.query.query_target)
            # Target is an array of one, return single item.
            if len(self.query.query_target) == 1:
                return self.query.query_target[0]
            # Directive commands should be run once for each item in the target.

        return self.query.query_target

    def json(self, afi):
        """Return JSON version of validated query for REST devices."""
        self._log.debug("Building JSON query")
        return _json.dumps(
            {
                "query_type": self.query.query_type,
                "vrf": self.query.query_vrf.name,
                "afi": afi.protocol,
                "source": str(afi.source_address),
                "target": str(self.target),
            }
        )

    def format(self, command: str) -> str:
        """Return formatted command for 'Scrape' endpoints (SSH)."""
        keys = get_fmt_keys(command)
        attrs = {k: v for k, v in self.device.attrs.items() if k in keys}
        for key in [k for k in keys if k != "target" and k != "mask"]:
            if key not in attrs:
                raise ConfigError(
                    ("Command '{c}' has attribute '{k}', which is missing from device '{d}'"),
                    level="danger",
                    c=self.directive.name,
                    k=key,
                    d=self.device.name,
                )

        mask = ipaddress.ip_address("255.255.255.255")
        try:
            network = ipaddress.ip_network(self.target)
            if network.version == 4 and network.network_address != network.broadcast_address:
                # Network is an IPv4 network with more than one host.
                mask = network.netmask
        except ValueError:
            pass

        if self.directive._hyperglass_builtin and self.device.platform in (
            "bird",
            "frr",
            "openbgpd",
        ):
            # Split the trusted template first. Quote complete arguments after substitution.
            return shlex.join(
                arg.format(target=self.target, mask=mask, **attrs) for arg in shlex.split(command)
            )
        return command.format(target=self.target, mask=mask, **attrs)

    def queries(self):
        """Return queries for each enabled AFI."""
        query = []

        rules = [r for r in self.directive.rules if r._passed is True]
        if len(rules) < 1:
            raise InputInvalid(
                error="No validation rules matched target '{target}'",
                target=self.query.query_target,
            )

        for rule in [r for r in self.directive.rules if r._passed is True]:
            for command in rule.commands:
                query.append(self.format(command))
        self._log.bind(constructed_query=query).debug("Constructed query")
        return query


class Formatter:
    """Modify query target based on the device's NOS requirements and the query type."""

    def __init__(self, query: "Query") -> None:
        """Initialize target formatting."""
        self.query = query
        self.platform = query.device.platform
        self.query_type = getattr(query.directive, "query_kind", query.query_type)

    def __enter__(self):
        """Get the relevant formatter."""
        return self._get_formatter()

    def __exit__(self, exc_type, exc_value, exc_traceback):
        """Handle context exit."""
        if exc_type is not None:
            log.error(exc_traceback)
        pass

    def _get_formatter(self):
        if self.platform in ("juniper", "juniper_junos"):
            if self.query_type == "bgp_aspath":
                return self._with_formatter(self._juniper_bgp_aspath)
        if self.platform in ("bird", "bird_ssh"):
            if self.query_type == "bgp_aspath":
                return self._with_formatter(self._bird_bgp_aspath)
            if self.query_type == "bgp_community":
                return self._with_formatter(self._bird_bgp_community)
        if self.platform in ("mikrotik_routeros", "mikrotik_switchos"):
            if self.query_type in ("bgp_aspath", "bgp_community"):
                return self._with_formatter(self._mikrotik_bgp_pattern)
        if self.platform == "openbgpd" and self.query_type == "bgp_aspath":
            return self._with_formatter(self._openbgpd_bgp_aspath)
        return self._with_formatter(self._default)

    def _default(self, target: str) -> str:
        """Don't format targets by default."""
        return target

    def _with_formatter(self, formatter: t.Callable[[str], str]) -> FormatterCallback:
        result: FormatterCallback
        if isinstance(self.query.query_target, t.List):
            return lambda s: [formatter(i) for i in s] if isinstance(s, list) else formatter(s)
        result = lambda s: formatter(s)
        return result

    def _juniper_bgp_aspath(self, target: str) -> str:
        """Convert from Cisco AS_PATH format to Juniper format."""
        query = str(target)
        asns = re.findall(r"\d+", query)
        was_modified = False

        if bool(re.match(r"^\_", query)):
            # Replace `_65000` with `.* 65000`
            asns.insert(0, r".*")
            was_modified = True

        if bool(re.match(r".*(\_)$", query)):
            # Replace `65000_` with `65000 .*`
            asns.append(r".*")
            was_modified = True

        if was_modified:
            modified = " ".join(asns)
            log.bind(original=target, modified=modified).debug("Modified target")
            return modified

        return query

    def _bird_bgp_aspath(self, target: str) -> str:
        """Translate common Cisco ASN sequences without silently changing other regexes."""
        if not re.fullmatch(r"[\^_]?[0-9]+(?:_[0-9]+)*[_$]?", target):
            raise InputInvalid(target=target, error="BIRD supports ASN sequences with ^, $, and _")
        asns = re.findall(r"[0-9]+", target)
        if any(int(asn) > 0xFFFFFFFF for asn in asns):
            raise InputInvalid(target=target, error="ASN exceeds 32 bits")
        if not target.startswith("^"):
            asns.insert(0, "*")
        if not target.endswith("$"):
            asns.append("*")
        return "[= " + " ".join(asns) + " =]"

    def _bird_bgp_community(self, target: str) -> str:
        """Convert from standard community format to BIRD format."""
        if not re.fullmatch(r"[0-9]+:[0-9]+", target):
            raise InputInvalid(target=target, error="BIRD requires a standard ASN:value community")
        parts = target.split(":")
        return f"({','.join(parts)})"

    def _mikrotik_bgp_pattern(self, target: str) -> str:
        """Build a RouterOS ``where ~`` regex for an AS-path or community query.

        AS-path: translate the Cisco ``_`` boundary to a RouterOS element
        boundary and keep the user's ``^``/``$`` anchors, each escaped as ``\\$``
        so the console passes a literal ``$`` to the regex engine. A bare ``$``
        is read as console variable interpolation and a doubled ``\\\\$`` as an
        escaped backslash; both fail the command with a syntax error.

        Community: match as a substring with dots escaped. Anchoring the match
        with ``(^|,)...(,|$)`` is exact but makes RouterOS scan a full table far
        too slowly (>300s versus ~60s for the substring), so keep the
        long-standing substring behaviour. The target is already constrained to
        a safe charset by ``BuiltinDirective.validate_target``.
        """
        if self.query_type == "bgp_aspath":
            return target.replace("_", "(^|[ ,]|$)").replace("$", r"\$")
        return target.replace(".", r"\.")

    def _openbgpd_bgp_aspath(self, target: str) -> str:
        """Extract the ASN after a directive rule selects the matching AS operator."""
        asn = target.strip("_^$")
        if not asn.isdecimal() or int(asn) > 0xFFFFFFFF:
            raise InputInvalid(target=target, error="OpenBGPD requires a 32-bit ASN")
        return asn
