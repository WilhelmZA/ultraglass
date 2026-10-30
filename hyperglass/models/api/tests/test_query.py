"""Tests for cross-vendor directive resolution."""

# Standard Library
import typing as t
from types import SimpleNamespace

# Third Party
import pytest

# Project
from hyperglass.state import use_state
from hyperglass.models.directive import Directive, Directives
from hyperglass.models.config.devices import Device
from hyperglass.models.api.query import resolve_directive_by_name


def directive(id: str, name: str, table_output: t.Optional[str] = None) -> Directive:
    """Create a directive with the minimum fields the model requires."""
    return Directive(
        id=id,
        name=name,
        table_output=table_output,
        field={"description": "test"},
        rules=[{"condition": "0.0.0.0/0", "action": "permit", "command": "show route {target}"}],
    )


def device(*directives: Directive, structured: bool = False) -> t.Any:
    """Stand in for a Device.

    `resolve_directive_by_name` reads only `directives` and `structured_output`, and a
    real Device requires a full validated configuration, so a namespace keeps the test
    isolated.
    """
    return SimpleNamespace(directives=Directives(*directives), structured_output=structured)


JUNIPER_PLAIN = directive(
    "__hyperglass_juniper_bgp_route__", "BGP Route", "__hyperglass_juniper_bgp_route_table__"
)
JUNIPER_TABLE = directive("__hyperglass_juniper_bgp_route_table__", "BGP Route")
HUAWEI_PLAIN = directive(
    "__hyperglass_huawei_bgp_route__", "BGP Route", "__hyperglass_huawei_bgp_route_table__"
)
HUAWEI_TABLE = directive("__hyperglass_huawei_bgp_route_table__", "BGP Route")
HUAWEI_PING = directive("__hyperglass_huawei_ping__", "Ping")


def test_resolves_across_vendors() -> None:
    """Resolve one vendor's directive id to another vendor's directive of the same name."""
    juniper = device(JUNIPER_TABLE, structured=True)
    huawei = device(HUAWEI_TABLE, structured=True)

    result = resolve_directive_by_name(
        devices=[juniper, huawei],
        device=huawei,
        directive_id=JUNIPER_TABLE.id,
    )

    assert result is not None
    assert result.id == HUAWEI_TABLE.id


@pytest.mark.parametrize("requested", (JUNIPER_TABLE, JUNIPER_PLAIN))
def test_unstructured_target_runs_plain_variant(requested: Directive) -> None:
    """Pick the plain builtin on an unstructured device whatever variant was requested.

    An unstructured device carries both the plain directive and its table-output
    variant under one name. Its output plugins never parse, so the table command
    would only dump machine-format text.
    """
    juniper = device(JUNIPER_PLAIN, JUNIPER_TABLE)
    huawei = device(HUAWEI_PLAIN, HUAWEI_TABLE)

    result = resolve_directive_by_name(
        devices=[juniper, huawei],
        device=huawei,
        directive_id=requested.id,
    )

    assert result is not None
    assert result.id == HUAWEI_PLAIN.id


@pytest.mark.parametrize("requested", (JUNIPER_TABLE, JUNIPER_PLAIN))
def test_structured_target_runs_table_variant(requested: Directive) -> None:
    """Pick the table variant on a structured device whatever variant was requested."""
    juniper = device(JUNIPER_PLAIN, JUNIPER_TABLE)
    huawei = device(HUAWEI_PLAIN, HUAWEI_TABLE, structured=True)

    result = resolve_directive_by_name(
        devices=[juniper, huawei],
        device=huawei,
        directive_id=requested.id,
    )

    assert result is not None
    assert result.id == HUAWEI_TABLE.id


def test_falls_back_when_target_has_only_the_other_variant() -> None:
    """Run the only same-name directive if the preferred variant is absent."""
    juniper = device(JUNIPER_PLAIN)
    huawei = device(HUAWEI_TABLE)

    result = resolve_directive_by_name(
        devices=[juniper, huawei],
        device=huawei,
        directive_id=JUNIPER_PLAIN.id,
    )

    assert result is not None
    assert result.id == HUAWEI_TABLE.id


def test_directive_without_table_form_resolves_on_unstructured_target() -> None:
    """Resolve a directive that has no table variant, such as ping."""
    juniper = device(directive("__hyperglass_juniper_ping__", "Ping"))
    huawei = device(HUAWEI_PING)

    result = resolve_directive_by_name(
        devices=[juniper, huawei],
        device=huawei,
        directive_id="__hyperglass_juniper_ping__",
    )

    assert result is not None
    assert result.id == HUAWEI_PING.id


def test_returns_none_for_unknown_directive_id() -> None:
    """Refuse to resolve an id no device defines."""
    huawei = device(HUAWEI_TABLE)

    assert (
        resolve_directive_by_name(
            devices=[huawei],
            device=huawei,
            directive_id="__hyperglass_nonexistent__",
        )
        is None
    )


def test_returns_none_when_target_device_lacks_the_name() -> None:
    """Refuse to resolve a name the target device does not offer."""
    juniper = device(JUNIPER_TABLE)
    huawei = device(HUAWEI_PING)

    assert (
        resolve_directive_by_name(
            devices=[juniper, huawei],
            device=huawei,
            directive_id=JUNIPER_TABLE.id,
        )
        is None
    )


BUILTIN_TRACEROUTE = "__hyperglass_cisco_ios_traceroute__"


def cisco_ios(name: str, *directives: t.Any) -> Device:
    """Build a real structured Cisco IOS device, so its directive list is validated."""
    return Device(
        name=name,
        address="192.0.2.10",
        credential={"username": "admin", "password": "admin"},
        platform="cisco_ios",
        structured_output=True,
        directives=list(directives),
        attrs={"source4": "192.0.2.1", "source6": "2001:db8::1"},
    )


@pytest.fixture
def custom_traceroute() -> Directive:
    """Register a custom directive that shares the builtin traceroute's name (#139)."""
    custom = directive("lab-iosv-traceroute", "Traceroute")
    state = use_state()
    directives = state.directives
    directives.add(custom)
    state.redis.set("directives", directives)
    return custom


def test_builtin_list_excludes_unlisted_builtins(custom_traceroute: Directive) -> None:
    """Keep the builtin traceroute off a device limited to `builtins: [bgp, ping]` (#139)."""
    iosv = cisco_ios("lab-iosv", {"builtins": ["bgp", "ping"]}, custom_traceroute.id)

    ids = {d.id for d in iosv.directives}

    assert BUILTIN_TRACEROUTE not in ids
    assert custom_traceroute.id in ids
    assert "__hyperglass_cisco_ios_ping__" in ids


def test_builtin_id_runs_the_devices_own_same_name_directive(
    custom_traceroute: Directive,
) -> None:
    """Run the device's custom Traceroute for a builtin traceroute id (#139).

    A multi-location selection groups directives by name, so the builtin id reaches a
    device that offers only its own Traceroute. That device runs its own directive.
    """
    iol = cisco_ios("lab-iol", {"builtins": True})
    iosv = cisco_ios("lab-iosv", {"builtins": ["bgp", "ping"]}, custom_traceroute.id)

    result = resolve_directive_by_name(
        devices=[iol, iosv], device=iosv, directive_id=BUILTIN_TRACEROUTE
    )

    assert result is not None
    assert result.id == custom_traceroute.id


def test_builtin_id_refused_without_a_same_name_directive() -> None:
    """Refuse a builtin traceroute id on a device that offers no Traceroute (#139)."""
    iol = cisco_ios("lab-iol", {"builtins": True})
    iosv = cisco_ios("lab-iosv", {"builtins": ["bgp", "ping"]})

    assert (
        resolve_directive_by_name(devices=[iol, iosv], device=iosv, directive_id=BUILTIN_TRACEROUTE)
        is None
    )
