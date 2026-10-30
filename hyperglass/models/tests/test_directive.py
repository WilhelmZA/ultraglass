"""Tests for directive target handling."""

# Third Party
import pytest

# Project
from hyperglass.models.directive import Directive
from hyperglass.exceptions.private import InputValidationError


@pytest.mark.parametrize(
    ("condition", "target", "expected"),
    (
        ("0.0.0.0/0", "192.0.2.1/24", "192.0.2.0/24"),
        ("::/0", "2001:db8::1/64", "2001:db8::/64"),
        ("0.0.0.0/0", "192.0.2.1", "192.0.2.1"),
    ),
)
def test_normalize_target(condition: str, target: str, expected: str) -> None:
    """Canonicalize prefixed IP targets without changing host targets."""
    directive = Directive(
        id="test",
        name="Test",
        field={"description": "test"},
        rules=[{"condition": condition}],
    )

    assert directive.normalize_target(target) == expected


def _ip_directive(**keys: bool) -> Directive:
    return Directive(
        id="test",
        name="Test",
        field={"description": "test"},
        rules=[{"condition": "0.0.0.0/0", **keys}, {"condition": "::/0", **keys}],
    )


@pytest.mark.parametrize(
    ("target", "key", "kind"),
    (
        ("127.0.0.1", "allow_loopback", "Loopback"),
        ("127.0.0.0/8", "allow_loopback", "Loopback"),
        ("::1", "allow_loopback", "Loopback"),
        ("0.0.0.0", "allow_unspecified", "Unspecified"),  # noqa: S104
        ("::", "allow_unspecified", "Unspecified"),
        ("240.0.0.1", "allow_reserved", "Reserved"),
        ("255.255.255.255", "allow_reserved", "Reserved"),
        ("100::1", "allow_reserved", "Reserved"),
    ),
)
def test_address_class_refused_by_default(target: str, key: str, kind: str) -> None:
    """Refuse loopback, unspecified and reserved targets unless the rule allows them (#173)."""
    with pytest.raises(InputValidationError) as err:
        _ip_directive().validate_target(target)
    assert err.value.kwargs["kind"] == kind

    assert _ip_directive(**{key: True}).validate_target(target) is True


@pytest.mark.parametrize(
    "target",
    (
        "1.1.1.1",
        "1.0.0.0/24",
        "2606:4700::1111",
        "192.0.2.1",
        "198.51.100.0/24",
        "203.0.113.5",
        "2001:db8::1",
        "198.18.0.0/15",
        "0.0.0.0/0",
        "::/0",
    ),
)
def test_ordinary_targets_allowed_by_default(target: str) -> None:
    """Public, documentation and default-route targets pass with the default keys (#173)."""
    assert _ip_directive().validate_target(target) is True
