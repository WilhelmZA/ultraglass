"""Test docs helpers."""

# Standard Library
import json

# Third Party
from netmiko.ssh_dispatcher import CLASS_MAPPER  # type: ignore

# Local
from ..docs import PLATFORMS_JSON, create_platform_list


def _run_create_platform_list(tmp_path):
    """Write the platform list to a temporary file and return it with the committed file."""
    output = tmp_path / "platforms.json"
    create_platform_list(output)
    return json.loads(PLATFORMS_JSON.read_text()), json.loads(output.read_text())


def test_create_platform_list_matches_platforms_json(tmp_path):
    """The generator runs, and its native rows match docs/platforms.json exactly.

    The installed netmiko version decides the non-native key set, so those rows are
    checked against the installed netmiko instead of the committed file.
    """
    committed, generated = _run_create_platform_list(tmp_path)

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
