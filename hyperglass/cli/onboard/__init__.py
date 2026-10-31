"""Build and verify device configuration from the command line."""

# Standard Library
import re
import sys
import json
import asyncio
from copy import deepcopy
from contextlib import contextmanager, redirect_stdout

# Third Party
import yaml
import typer
from pydantic import ValidationError

onboard = typer.Typer(help="Build and test device entries", no_args_is_help=True)


def report(data: dict, as_json: bool) -> None:
    """Print the complete report and a plain-text summary table."""
    if as_json:
        typer.echo(json.dumps(data, indent=2, default=str))
        return
    rows = data.get("results", [])
    for row in rows:
        if "feature" in row:
            typer.echo(f"{row['feature']}: {row['current']}")
            if row["suggestion"]:
                typer.echo(f"  Set: {row['suggestion']}")
        else:
            print_query(row)
    if "scaffold" in data:
        typer.echo(yaml.safe_dump(data["scaffold"], sort_keys=False))
    if rows:
        typer.echo("\nStatus\tFeature / query\tTarget")
        for row in rows:
            typer.echo(
                f"{row['status'].upper()}\t"
                f"{row.get('feature', row.get('directive', ''))}\t{row.get('target', '')}"
            )
    typer.echo(data.get("message", ""))
    if data.get("error"):
        typer.echo(data["error"])


def print_query(row: dict) -> None:
    """Show commands, device errors and populated/empty fields without terminal styling."""
    typer.echo(f"\n{row['device']} / {row['directive']} / {row['target']}")
    attempts = row["attempts"]
    for command in row["commands"]:
        typer.echo(f"  Planned command: {command}")
    for attempt in attempts:
        label = "Fallback" if attempt["fallback"] else "Sent"
        typer.echo(f"  {label}: {attempt['command']}")
        if attempt["command_error"]:
            typer.echo(f"  Device error: {attempt['output']}")
    typer.echo(f"  Fallback used: {row['fallback_used']} (version: {row['version_fallback']})")
    for field, counts in row["coverage"].get("fields", {}).items():
        detail = f"{counts['populated']} populated; {counts['empty']} empty"
        if "unverified" in counts:
            detail += f"; {counts['unverified']} unverified"
        typer.echo(f"  {field}: {detail}")
    if row["error"]:
        typer.echo(f"  Error: {row['error']}")
    if row["output"] is not None:
        typer.echo(json.dumps(row["output"], indent=2, default=str))


@contextmanager
def command_errors(as_json: bool):
    """Keep JSON stdout clean and avoid logging configuration or credentials."""
    # Project
    from hyperglass.log import log

    log.disable("hyperglass")
    try:
        yield
    except (typer.Exit, typer.Abort):
        raise
    except Exception as error:
        if isinstance(error, ValidationError):
            message = "; ".join(
                f"{'.'.join(map(str, e['loc']))}: {e['msg']}"
                for e in error.errors(include_input=False)
            )
        elif isinstance(error, yaml.YAMLError):
            message = "Invalid YAML configuration"
        else:
            message = str(error)
        report({"error": message}, as_json)
        raise typer.Exit(1) from error
    finally:
        log.enable("hyperglass")


@onboard.command("device")
def device_command(as_json: bool = typer.Option(False, "--json")) -> None:
    """Create or update a validated device in devices.yaml."""
    # Project
    from hyperglass.models.config.devices import Devices

    # Local
    from .files import YamlFile, copy_entry
    from .prompts import prompt, confirm, device_prompt
    from .runtime import runtime

    with command_errors(as_json), runtime(devices=False):
        document = YamlFile("devices")
        entries = document.device_entries()
        name = prompt("Device name or existing ID", err=True)
        index, entry = copy_entry(entries, name)
        entry = device_prompt(entry)
        if index is None:
            entries.append(entry)
        else:
            entries[index] = entry
        validated = Devices(*deepcopy(entries))
        if len(set(validated.ids)) != len(validated):
            raise ValueError("The device name generates an ID already used by another device")
        if not confirm(
            "Save devices YAML (comments and formatting are rewritten)?", default=False, err=True
        ):
            report({"message": "Cancelled; no file written"}, as_json)
            return
        document.write()
        report(
            {
                "message": f"Saved {entry['name']} to {document.path}. "
                "Restart Ultraglass to load it."
            },
            as_json,
        )


@onboard.command("check")
def check_command(as_json: bool = typer.Option(False, "--json")) -> None:
    """Report effective feature settings and the lines that enable them."""
    # Local
    from .check import check_config
    from .runtime import runtime

    with command_errors(as_json), runtime() as state:
        report({"results": check_config(state)}, as_json)


@onboard.command("test")
def test_command(
    device: str = typer.Argument(..., help="Exact device ID or name"),
    ipv4: str = typer.Option("1.1.1.1", help="IPv4 ping/traceroute target"),
    ipv6: str = typer.Option("2606:4700:4700::1111", help="IPv6 ping/traceroute target"),
    route_ipv4: str = typer.Option("1.1.1.0/24", help="IPv4 BGP route target"),
    route_ipv6: str = typer.Option("2606:4700::/44", help="IPv6 BGP route target"),
    as_path: str = typer.Option("13335$", help="AS path target"),
    community: str = typer.Option("37195:302", help="Community target"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Run every built-in directive offered by a device, including both IP families."""
    # Local
    from .probe import cases, probe
    from .runtime import runtime

    with command_errors(as_json), runtime(plugins=True) as state:
        selected = find_device(state, device)
        targets = {
            "ipv4": ipv4,
            "ipv6": ipv6,
            "route_ipv4": route_ipv4,
            "route_ipv6": route_ipv6,
            "bgp_aspath": as_path,
            "bgp_community": community,
        }

        async def run():
            return [
                await probe(selected, directive, target)
                for directive, target in cases(selected, targets)
            ]

        results = asyncio.run(run())
        if not results:
            raise ValueError("This device offers no built-in directives")
        failed = sum(row["status"] == "fail" for row in results)
        report(
            {"results": results, "message": f"{len(results) - failed} passed; {failed} failed"},
            as_json,
        )
        if failed:
            raise typer.Exit(1)


def find_device(state, name: str):
    """Resolve an exact configured device name or ID."""
    for device in state.devices:
        if name in (device.name, device.id):
            return device
    raise ValueError(f"Unknown device: {name}")


@onboard.command("directive")
def directive_command(
    device: str = typer.Argument(..., help="Device on the intended platform"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Scaffold and test a custom directive before optionally saving it."""
    # Project
    from hyperglass.models.directive import Directive
    from hyperglass.models.config.devices import directive_attr_keys

    # Local
    from .files import YamlFile
    from .probe import probe
    from .prompts import prompt, confirm
    from .runtime import runtime

    with command_errors(as_json), runtime(plugins=True) as state:
        selected = find_device(state, device)
        document = YamlFile("directives")
        name = prompt("New directive ID", err=True)
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", name):
            raise ValueError("Use a letter followed by letters, digits, hyphens or underscores")
        if any(name.lower() in item.id.lower() for item in state.directives):
            raise ValueError("Choose a directive ID that does not match an existing directive")
        command = prompt(f"Command template for {selected.platform} (use {{target}})", err=True)
        condition = prompt(
            "Target rule (IP prefix or regular expression)", default="0.0.0.0/0", err=True
        )
        entry = {
            "name": name,
            "field": {"description": "Target"},
            "rules": [{"condition": condition, "command": command}],
        }
        if selected.vrf and "{vrf}" in command:
            entry["rules"][0]["vrf_command"] = command
        directive = Directive(id=name, **entry)
        missing = directive_attr_keys([directive], vrf=bool(selected.vrf)) - selected.attrs.keys()
        if missing:
            raise ValueError(f"Device is missing attributes: {', '.join(sorted(missing))}")
        target = prompt("Test target", err=True)
        selected.directives.add(directive)
        result = asyncio.run(probe(selected, name, target, include_output=True))
        with redirect_stdout(sys.stderr):
            print_query(result)
        saved = False
        if result["status"] == "pass" and confirm("Save directives YAML?", default=False, err=True):
            document.data[name] = entry
            document.write()
            saved = True
        report(
            {
                "results": [result],
                "scaffold": {name: entry},
                "message": (
                    f"Saved {name}. Add it to devices[{selected.id}].directives and restart."
                    if saved
                    else "Directive not saved"
                ),
            },
            as_json,
        )
        if result["status"] == "fail":
            raise typer.Exit(1)
