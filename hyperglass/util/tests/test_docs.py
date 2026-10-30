"""Test docs helpers."""

# Standard Library
import json
from pathlib import Path

# Third Party
from netmiko.ssh_dispatcher import CLASS_MAPPER  # type: ignore

# Local
from ..docs import create_platform_list

PLATFORMS_JSON = Path(__file__).parent.parent.parent.parent / "docs" / "platforms.json"


def _run_create_platform_list():
    """Run create_platform_list, return its output, and restore the committed file."""
    committed = PLATFORMS_JSON.read_bytes()
    try:
        create_platform_list()
        generated = json.loads(PLATFORMS_JSON.read_text())
    finally:
        PLATFORMS_JSON.write_bytes(committed)
    return json.loads(committed), generated


def test_create_platform_list_matches_platforms_json():
    """The generator runs, and its native rows match docs/platforms.json exactly.

    The installed netmiko version decides the non-native key set, so those rows are
    checked against the installed netmiko instead of the committed file.
    """
    committed, generated = _run_create_platform_list()

    committed_native = [p for p in committed if p["native"]]
    generated_native = [p for p in generated if p["native"]]
    assert generated_native == committed_native

    native_keys = {k for p in generated_native for k in p["keys"]}
    generated_other = [p for p in generated if not p["native"]]
    assert all(p["name"] == "" and len(p["keys"]) == 1 for p in generated_other)
    assert {p["keys"][0] for p in generated_other} == set(CLASS_MAPPER) - native_keys

    # Native rows come first, then each group is sorted by its first key.
    assert generated[: len(generated_native)] == generated_native
    other_keys = [p["keys"][0] for p in generated_other]
    assert other_keys == sorted(other_keys)
