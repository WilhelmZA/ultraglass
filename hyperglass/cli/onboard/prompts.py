"""Interactive device and directive setup."""

# Standard Library
import sys
import difflib
from copy import deepcopy
from contextlib import redirect_stdout

# Third Party
import typer
from click import IntRange

# Project
from hyperglass.constants import SCRAPE_HELPERS, SUPPORTED_STRUCTURED_OUTPUT
from hyperglass.models.config.devices import ALL_DEVICE_TYPES, Device, directive_attr_keys


def prompt(*args, **kwargs):
    """Keep prompts and terminal input echoes off JSON stdout."""
    with redirect_stdout(sys.stderr):
        return typer.prompt(*args, **kwargs)


def confirm(*args, **kwargs):
    """Keep confirmation input off JSON stdout."""
    with redirect_stdout(sys.stderr):
        return typer.confirm(*args, **kwargs)


def platform_prompt(default: str = "") -> str:
    """List supported platforms and offer the same fuzzy matches as unknown-key warnings."""
    platforms = sorted(ALL_DEVICE_TYPES - {"http"})
    while True:
        value = prompt("Platform (? lists platforms)", default=default, err=True)
        if value == "?":
            typer.echo("\n".join(platforms), err=True)
        elif value in platforms:
            return SCRAPE_HELPERS.get(value, value)
        else:
            matches = difflib.get_close_matches(value, platforms, n=2, cutoff=0.6)
            typer.echo(
                "Unknown platform" + (f"; did you mean {' or '.join(matches)}?" if matches else ""),
                err=True,
            )


def credential_prompt(existing: dict) -> dict:
    """Keep existing credentials unless the operator chooses to replace them."""
    if existing and not confirm("Replace existing credential?", default=False, err=True):
        return deepcopy(existing)
    username = prompt("Username", default=existing.get("username", ""), err=True)
    key = prompt("SSH private key path (blank for password)", default="", err=True)
    result = {"username": username}
    if key:
        result["key"] = key
        password = prompt(
            "Key passphrase (blank for none)",
            default="",
            hide_input=True,
            show_default=False,
            err=True,
        )
        if password:
            result["password"] = password
    else:
        result["password"] = prompt("Password", hide_input=True, err=True)
    return result


def device_prompt(entry: dict) -> dict:
    """Collect device fields and all attributes required by the selected built-ins."""
    entry = deepcopy(entry)
    entry["address"] = prompt("Address", default=entry.get("address", ""), err=True)
    entry["port"] = prompt("Port", default=entry.get("port", 22), type=IntRange(1, 65535), err=True)
    entry["platform"] = platform_prompt(entry.get("platform", ""))
    entry["credential"] = credential_prompt(entry.get("credential", {}))
    for field, label in (("os_version", "OS version"), ("vrf", "VRF")):
        value = prompt(f"{label} (- to unset)", default=entry.get(field) or "", err=True)
        entry.pop(field, None)
        if value and value != "-":
            entry[field] = value
    previous_structured = entry.get("structured_output", False)
    entry["structured_output"] = False
    if entry["platform"] in SUPPORTED_STRUCTURED_OUTPUT:
        entry["structured_output"] = confirm(
            "Enable structured output?", default=bool(previous_structured), err=True
        )

    # Device validates directive selection before checking attributes. Use the same selector
    # through a provisional model with the attribute check suppressed, then validate normally.
    class Candidate(Device):
        def _validate_directive_attrs(self) -> None:
            pass

    candidate = Candidate(**deepcopy(entry))
    attrs = entry.setdefault("attrs", {})
    for key in sorted(directive_attr_keys(candidate.directives, vrf=bool(candidate.vrf))):
        attrs[key] = prompt(f"Attribute {key}", default=attrs.get(key, ""), err=True)
    Device(**deepcopy(entry))
    return entry
