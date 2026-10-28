"""Test ASN parsing utilities."""

# Third Party
import pytest

# Local
from ..validation import parse_asn, parse_as_path


@pytest.mark.parametrize(
    "value,expected",
    (
        ("65000", 65000),
        (65000, 65000),
        ("4259840100", 4259840100),
        ("65000.100", 4259840100),
        ("1.0", 65536),
        ("0.65535", 65535),
        ("65535.65535", 4294967295),
        ("65536.0", None),
        ("1.65536", None),
        ("4294967296", None),
        ("I", None),
        ("{", None),
        ("(65527)", None),
        ("1.2.3", None),
    ),
)
def test_parse_asn(value, expected):
    assert parse_asn(value) == expected


def test_parse_as_path_mixed():
    assert parse_as_path("1299 65000.100 13335 I") == [1299, 4259840100, 13335]
    assert parse_as_path(["174", 13335, "1.10"]) == [174, 13335, 65546]
    assert parse_as_path("") == []
