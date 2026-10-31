"""Run onboarding queries through the application drivers and parsers."""

# Standard Library
import typing as t

# Project
from hyperglass.models.api import Query
from hyperglass.execution.main import map_driver
from hyperglass.models.directive import version_matches
from hyperglass.execution.drivers._common import command_error


def cases(device, targets: dict[str, str]) -> t.Iterator[tuple[str, str]]:
    """Test every offered built-in; IP rules select IPv4 and IPv6 separately."""
    for directive in device.directives:
        if not directive._hyperglass_builtin:
            continue
        kind = directive.query_kind
        if kind in ("bgp_aspath", "bgp_community"):
            yield directive.id, targets[kind]
            continue
        families = {rule._type for rule in directive.rules if rule.action == "permit"}
        for family in ("ipv4", "ipv6"):
            if family in families:
                key = f"route_{family}" if kind == "bgp_route" else family
                yield directive.id, targets[key]


def field_coverage(output: t.Any) -> dict:
    """Count populated and empty fields after parsing and configured policy filtering."""
    if hasattr(output, "model_dump"):
        output = output.model_dump(mode="json")
    if not isinstance(output, dict):
        return {}
    rows = output.get("routes", output.get("hops", []))
    fields = ("communities", "rpki_state", "age", "next_hop")
    if "hops" in output:
        fields = ("ip_address", "rtt1", "rtt2", "rtt3", "asn", "org")
    result = {}
    for field in fields:
        values = [row.get(field) for row in rows]
        populated = sum(value is not None and value != "" and value != [] for value in values)
        result[field] = {"populated": populated, "empty": len(rows) - populated}
        if field == "rpki_state":
            result[field]["unverified"] = values.count(3)
    return {"rows": len(rows), "fields": result}


def ensure_output(output: t.Any) -> None:
    """Treat empty parser results consistently across platforms."""
    if (
        output is None
        or output is False
        or not output
        or (isinstance(output, (tuple, list)) and not any(str(item).strip() for item in output))
        or (isinstance(output, str) and not output.strip())
    ):
        raise ValueError("Device returned no output")
    if isinstance(output, dict) and any(
        key in output and not output[key] for key in ("routes", "hops")
    ):
        raise ValueError("No matching rows in the structured response")


async def probe(device, directive_id: str, target: str, *, include_output: bool = False) -> dict:
    """Return command attempts, fallback decisions, errors and parsed field coverage."""
    result = {
        "device": device.id,
        "directive": directive_id,
        "target": target,
        "status": "fail",
        "commands": [],
        "attempts": [],
        "fallback_used": False,
        "version_fallback": False,
        "structured": False,
        "coverage": {},
        "output": None,
        "error": None,
    }
    try:
        # Redis normally deserializes fresh rules per query. Local CLI state reuses them.
        for directive in device.directives:
            for rule in directive.rules:
                rule._passed = None
        query = Query(query_location=device.id, query_type=directive_id, query_target=target)
        driver = map_driver(device.driver)(query.device, query)
        driver.command_trace = result["attempts"]
        result["commands"] = driver.query
        result["version_fallback"] = any(
            rule._passed
            and rule.fallback_os_version
            and version_matches(device.os_version, rule.fallback_os_version)
            and not (device.vrf and rule.vrf_commands)
            for rule in query.directive.rules
        )
        if device.proxy:
            with driver.setup_proxy()() as tunnel:
                raw = await driver.collect(tunnel.local_bind_host, tunnel.local_bind_port)
        else:
            raw = await driver.collect()
        result["output"] = raw
        if command_error(raw):
            raise ValueError("Device rejected the command")
        output = await driver.response(raw)
        if hasattr(output, "model_dump"):
            output = output.model_dump(mode="json")
        result["structured"] = isinstance(output, dict)
        result["coverage"] = field_coverage(output)
        ensure_output(output)
        result["output"] = output if include_output else None
        result["status"] = "pass"
    except Exception as error:
        result["error"] = f"{type(error).__name__}: {error}"
    finally:
        result["fallback_used"] = result["version_fallback"] or any(
            attempt["fallback"] for attempt in result["attempts"]
        )
        for attempt in result["attempts"]:
            attempt["command_error"] = (
                command_error(attempt["output"]) if attempt["output"] is not None else None
            )
            attempt["completed"] = attempt["output"] is not None
            if not attempt["command_error"]:
                attempt["output"] = None
    return result
