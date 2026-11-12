"""Control characters in a target must not reach a device command (#243)."""

# Third Party
import pytest

# Project
from hyperglass.models.directive import RuleWithIP
from hyperglass.defaults.directives import init_builtin_directives
from hyperglass.exceptions.private import InputValidationError

IP_DIRECTIVES = [
    directive
    for directive in init_builtin_directives()
    if any(isinstance(rule, RuleWithIP) for rule in directive.rules)
]
IDS = [directive.id for directive in IP_DIRECTIVES]

HOSTILE = (
    "fe80::1%eth0\nshow running-config",
    "fe80::1%eth0\rshow running-config",
    "fe80::1%eth0\r\nshow running-config",
    "fe80::1%\nshow running-config",
    "2001:db8::1%x\x00",
    "2001:db8::1%x\x1b[A",
    "2001:db8::1%x show version",
    "2001:db8::1%eth0;id",
    "2001:db8::1%eth0 | include secret",
    "2001:db8::1%$(id)",
    "2001:db8::%a\nshow version/64",
)


def _is_control(char: str) -> bool:
    return ord(char) < 0x20 or 0x7F <= ord(char) < 0xA0 or char in "  "


def test_builtin_ping_and_traceroute_are_covered():
    assert sum(directive_id.endswith("_ping__") for directive_id in IDS) >= 20
    assert sum(directive_id.endswith("_traceroute__") for directive_id in IDS) >= 20


@pytest.mark.parametrize("directive", IP_DIRECTIVES, ids=IDS)
@pytest.mark.parametrize("target", HOSTILE)
def test_builtin_ip_directives_reject_hostile_zone(directive, target):
    directive = directive.model_copy(deep=True)

    with pytest.raises(InputValidationError):
        directive.validate_target(directive.normalize_target(target))


@pytest.mark.parametrize("directive", IP_DIRECTIVES, ids=IDS)
@pytest.mark.parametrize("target", ("2001:DB8:0:0::1", "2001:db8::1%eth0", "192.0.2.1", *HOSTILE))
def test_validated_target_has_no_control_character(directive, target):
    """Whatever passes validation is free of control characters."""
    directive = directive.model_copy(deep=True)
    normalized = directive.normalize_target(target)
    try:
        directive.validate_target(normalized)
    except InputValidationError:
        return

    assert not any(_is_control(char) for char in normalized)
    assert all(char.isalnum() or char in ".:%-/" for char in normalized)


def test_target_is_the_parsed_address():
    directive = next(d for d in IP_DIRECTIVES if d.id == "__hyperglass_frr_ping__")

    assert directive.normalize_target("2001:DB8:0:0::1") == "2001:db8::1"
    assert directive.normalize_target("192.0.2.1") == "192.0.2.1"
    assert directive.normalize_target("2001:DB8::1/64") == "2001:db8::/64"
    assert directive.normalize_target(["2001:DB8:0:0::1"]) == ["2001:db8::1"]
    assert directive.normalize_target("example.com") == "example.com"


def test_zone_of_letters_digits_and_hyphens_is_allowed():
    directive = next(d for d in IP_DIRECTIVES if d.id == "__hyperglass_frr_ping__")

    assert directive.model_copy(deep=True).validate_target("fe80::1%eth0") is True
    assert directive.model_copy(deep=True).validate_target("fe80::1%br-lan") is True


@pytest.mark.parametrize(
    "target",
    (
        "192.0.2.1\nshow version",
        "example.com\rshow version",
        "13335\x00",
        "13335\x7f",
        "13335 id",
        "13335​",
        ["192.0.2.1", "192.0.2.2\nid"],
    ),
)
def test_query_rejects_control_characters_in_any_target(target):
    # Project
    from hyperglass.models.api.query import Query

    with pytest.raises(ValueError, match="control characters"):
        Query.validate_query_target_characters(target)


@pytest.mark.parametrize("target", ("192.0.2.1", "2001:db8::1", "_13335$", "65000:100", ["a", "b"]))
def test_query_accepts_ordinary_targets(target):
    # Project
    from hyperglass.models.api.query import Query

    assert Query.validate_query_target_characters(target) == target
