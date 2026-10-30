"""A text device never offers table-output directives (#132-#142)."""

# Third Party
import pytest

# Project
from hyperglass.constants import SUPPORTED_STRUCTURED_OUTPUT
from hyperglass.models.config.devices import Device

# TNSR has no netmiko driver yet (#102).
PLATFORMS = tuple(p for p in SUPPORTED_STRUCTURED_OUTPUT if p != "tnsr")
ATTRS = {"source4": "192.0.2.1", "source6": "2001:db8::1"}


def _device(platform, structured):
    return Device(
        name="lab",
        address="192.0.2.10",
        credential={"username": "lg", "password": "lg"},
        platform=platform,
        attrs=ATTRS,
        structured_output=structured,
    )


def _table_ids(platform):
    return {
        d.table_output
        for d in _device(platform, False).directives.root
        if getattr(d, "table_output", None)
    }


@pytest.mark.parametrize("platform", PLATFORMS)
def test_text_device_offers_no_table_directives(platform):
    ids = {d.id for d in _device(platform, False).directives}
    assert not {i for i in ids if i.endswith("_table__")}


@pytest.mark.parametrize("platform", PLATFORMS)
def test_structured_device_offers_one_directive_per_name(platform):
    directives = list(_device(platform, True).directives)
    names = [d.name for d in directives]
    assert len(names) == len(set(names))
    for table_id in _table_ids(platform):
        assert table_id in {d.id for d in directives}
