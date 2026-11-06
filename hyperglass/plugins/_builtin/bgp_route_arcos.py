"""Read ArcOS OpenConfig BGP loc-rib JSON from ConfD `show | display json`."""

# Standard Library
import json
import typing as t
from ipaddress import ip_address, ip_network

# Third Party
from pydantic import PrivateAttr

# Project
from hyperglass.util import parse_asn
from hyperglass.models.data import BGPRouteTable

# Local
from .._output import OutputPlugin


def _json_payload(text: str) -> t.Any:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            start, end = text.find("["), text.rfind("]")
        if start < 0 or end <= start:
            raise ValueError("Not ArcOS OpenConfig JSON") from None
        return json.loads(text[start : end + 1])


def _walk(obj: t.Any) -> t.Iterator[dict]:
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from _walk(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _walk(value)


def _first_key(node: dict, *names: str) -> t.Any:
    lower = {str(key).lower(): value for key, value in node.items()}
    for name in names:
        if name in node:
            return node[name]
        if name.lower() in lower:
            return lower[name.lower()]
    return None


def _merged_state(node: dict) -> dict:
    state = node.get("state")
    if isinstance(state, dict):
        return {**state, **{key: value for key, value in node.items() if key != "state"}}
    return dict(node)


def _parse_asns(values: t.Sequence) -> t.List[int]:
    as_path = [parse_asn(item) for item in values]
    if None in as_path:
        raise ValueError("Invalid ASN")
    return as_path


def _as_members(node: dict) -> t.List[int]:
    raw = _first_key(node, "as-path", "as_path")
    if raw is None:
        raw = node
    segments = []
    for candidate in _walk(raw):
        kind = str(_first_key(candidate, "type", "as-path-type") or "")
        if "SET" in kind.upper() or "CONFED" in kind.upper():
            raise ValueError("Unsupported AS set or confederation")
        members = _first_key(candidate, "member", "members")
        if isinstance(members, (str, int)):
            members = [members]
        if isinstance(members, list) and members and not isinstance(members[0], dict):
            segments.append(members)
    if segments:
        return _parse_asns([item for group in segments for item in group])
    if isinstance(raw, list) and raw and not isinstance(raw[0], dict):
        return _parse_asns(raw)
    if isinstance(raw, str) and raw.strip():
        return _parse_asns(raw.split())
    return []


def _communities(node: dict) -> t.List[str]:
    found: t.List[str] = []
    for candidate in _walk(node):
        value = _first_key(candidate, "community", "communities")
        if isinstance(value, list):
            found.extend(str(item) for item in value if not isinstance(item, dict) and item)
        elif isinstance(value, str) and value.strip() and ":" in value:
            found.extend(item for item in value.replace(",", " ").split() if item)
    # Preserve order while dropping duplicates introduced by nested state copies.
    seen = set()
    unique = []
    for item in found:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def _next_hop(node: dict) -> str:
    value = _first_key(node, "next-hop", "nexthop", "next_hop")
    if value is None:
        raise ValueError("Missing next-hop")
    return str(ip_address(str(value).split("/")[0]))


def _int_field(node: dict, default: int, *names: str) -> int:
    value = _first_key(node, *names)
    if value in (None, ""):
        return default
    return int(value)


def _attr_sets(tree: t.Any) -> dict[int, dict]:
    sets: dict[int, dict] = {}
    for node in _walk(tree):
        index = _first_key(node, "index")
        if index is None:
            continue
        if _first_key(node, "next-hop", "nexthop", "as-path", "local-pref", "med") is None:
            state = node.get("state")
            if not isinstance(state, dict):
                continue
        try:
            idx = int(index)
        except (TypeError, ValueError):
            continue
        merged = _merged_state(node)
        current = sets.get(idx, {})
        for key, value in merged.items():
            if key not in current or current[key] in (None, "", [], {}):
                current[key] = value
        sets[idx] = current
    return sets


def _route_nodes(tree: t.Any) -> t.List[dict]:
    attributes = _attr_sets(tree)
    routes = []
    for node in _walk(tree):
        prefix = _first_key(node, "prefix")
        if not isinstance(prefix, str):
            continue
        try:
            ip_network(prefix)
        except ValueError:
            continue
        merged = _merged_state(node)
        index = _first_key(merged, "attr-index", "attr_index")
        if index is not None:
            extra = attributes.get(int(index), {})
            merged = {**extra, **merged}
        has_route = any(
            _first_key(merged, name) is not None
            for name in (
                "valid-route",
                "next-hop",
                "nexthop",
                "as-path",
                "local-pref",
                "med",
                "attr-index",
            )
        )
        if not has_route:
            continue
        routes.append(merged)
    return routes


def _path(node: dict) -> dict:
    prefix = str(ip_network(_first_key(node, "prefix")))
    as_path = _as_members(node)
    origin = _first_key(node, "origin")
    peer = ""
    if origin not in (None, "", "IGP", "EGP", "INCOMPLETE"):
        try:
            peer = str(ip_address(str(origin).split("/")[0]))
        except ValueError:
            peer = ""
    valid = _first_key(node, "valid-route", "valid_route")
    return {
        "prefix": prefix,
        "next_hop": _next_hop(node),
        "peer_rid": peer,
        "source_rid": peer,
        "source_as": as_path[-1] if as_path else 0,
        "as_path": as_path,
        "communities": _communities(node),
        "med": _int_field(node, 0, "med", "metric"),
        "local_preference": _int_field(node, 100, "local-pref", "local_pref", "local-preference"),
        "weight": 0,
        "active": valid is not False,
        "age": -1,
        "rpki_state": 3,
    }


def parse_arcos(text: str, target: str, vrf: str = "default") -> BGPRouteTable:
    """Keep incomplete or unfamiliar JSON as text by raising ValueError."""
    want = str(ip_network(target, strict=False))
    routes = []
    seen: set[tuple] = set()
    incomplete = False
    for node in _route_nodes(_json_payload(text)):
        prefix = _first_key(node, "prefix")
        try:
            if str(ip_network(str(prefix))) != want:
                continue
        except (TypeError, ValueError):
            continue
        try:
            path = _path(node)
        except (TypeError, ValueError, KeyError):
            incomplete = True
            continue
        key = (path["prefix"], path["next_hop"], tuple(path["as_path"]), path["active"])
        if key in seen:
            continue
        seen.add(key)
        routes.append(path)
    if not routes and incomplete:
        raise ValueError("Incomplete ArcOS path")
    return BGPRouteTable(vrf=vrf, count=len(routes), routes=routes, winning_weight="high")


class BGPRoutePluginArcOS(OutputPlugin):
    """Select the structured ArcOS prefix directive only."""

    _hyperglass_builtin: bool = PrivateAttr(True)
    platforms: t.Sequence[str] = ("arrcus_arcos",)
    directives: t.Sequence[str] = ("__hyperglass_arrcus_arcos_bgp_route_table__",)

    def process(self, *, output, query):
        """Keep unknown responses available as text."""
        if not query.device.structured_output:
            return output
        text = output if isinstance(output, str) else "\n".join(output)
        try:
            return parse_arcos(text, query.query_target, query.device.vrf or "default")
        except (ValueError, KeyError, json.JSONDecodeError, TypeError):
            return output
