"""Tests for cross-vendor directive resolution."""

# Standard Library
import typing as t
from types import SimpleNamespace

# Third Party
import pytest

# Project
from hyperglass.models.directive import Directive, Directives
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
