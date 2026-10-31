"""Exercise the onboarding prompts, configuration isolation and device reports."""

# Standard Library
import json
from copy import deepcopy
from pathlib import Path

# Third Party
import yaml
import pytest
from typer.testing import CliRunner

# Project
from hyperglass.cli import cli
from hyperglass.state import use_state
from hyperglass.settings import Settings
from hyperglass.cli.onboard.files import YamlFile
from hyperglass.cli.onboard.probe import cases, probe, field_coverage
from hyperglass.cli.onboard.runtime import runtime
from hyperglass.models.config.devices import Device
from hyperglass.execution.drivers.ssh_netmiko import NetmikoConnection, collect_commands

runner = CliRunner(mix_stderr=False)

ENTRY = {
    "name": "Test FRR",
    "address": "127.0.0.1",
    "platform": "frr",
    "credential": {"username": "test", "password": "private-test-password"},
    "structured_output": True,
    "attrs": {"source4": "1.1.1.1", "source6": "2606:4700::1111"},
}
TARGETS = {
    "ipv4": "1.1.1.1",
    "ipv6": "2606:4700::1111",
    "route_ipv4": "1.1.1.0/24",
    "route_ipv6": "2606:4700::/44",
    "bgp_aspath": "13335$",
    "bgp_community": "37195:302",
}


@pytest.fixture
def config(tmp_path, monkeypatch):
    monkeypatch.setattr(Settings, "app_path", tmp_path)
    (tmp_path / "devices.yaml").write_text(yaml.safe_dump({"devices": [ENTRY]}))
    return tmp_path


def test_device_prompts_validate_and_do_not_publish_credentials(config):
    state = use_state()
    before = state.redis.instance.keys("*")
    result = runner.invoke(
        cli,
        ["onboard", "device", "--json"],
        input="\n".join(
            [
                "New FRR",
                "127.0.0.2",
                "",
                "frrr",
                "frr",
                "reader",
                "",
                "secret-new-device",
                "",
                "",
                "y",
                "1.1.1.2",
                "2606:4700::2",
                "y",
                "",
            ]
        ),
    )
    assert result.exit_code == 0, (result.stdout, result.stderr, result.exception)
    assert "did you mean" in result.stderr
    assert "secret-new-device" not in result.stdout + result.stderr
    assert json.loads(result.stdout)["message"].startswith("Saved New FRR")
    data = yaml.safe_load((config / "devices.yaml").read_text())
    assert data["devices"][0] == ENTRY
    with runtime():
        device = Device(**data["devices"][1])
        assert device.model_extra == {}
        assert device.structured_output is True
    assert state.redis.instance.keys("*") == before


def test_update_preserves_credentials_and_unrelated_fields(config):
    data = {"routers": [dict(ENTRY, group="Existing group"), dict(ENTRY, name="Other")]}
    (config / "devices.yaml").write_text(yaml.safe_dump(data))
    result = runner.invoke(
        cli,
        ["onboard", "device", "--json"],
        input="\n".join(
            [
                "test_frr",
                "127.0.0.3",
                "",
                "",
                "n",
                "",
                "",
                "y",
                "",
                "",
                "y",
                "",
            ]
        ),
    )
    assert result.exit_code == 0, (result.stdout, result.stderr, result.exception)
    after = yaml.safe_load((config / "devices.yaml").read_text())
    assert after["routers"][0]["address"] == "127.0.0.3"
    assert after["routers"][0]["credential"] == ENTRY["credential"]
    assert after["routers"][0]["group"] == "Existing group"
    assert after["routers"][1] == data["routers"][1]


def test_declining_save_leaves_bytes_unchanged(config):
    before = (config / "devices.yaml").read_bytes()
    result = runner.invoke(
        cli,
        ["onboard", "device", "--json"],
        input="\n".join(
            [
                "test_frr",
                "",
                "",
                "",
                "n",
                "",
                "",
                "",
                "",
                "",
                "n",
                "",
            ]
        ),
    )
    assert result.exit_code == 0, result.exception
    assert (config / "devices.yaml").read_bytes() == before


def test_writer_rejects_concurrent_edit_and_non_yaml(config):
    document = YamlFile("devices")
    (config / "devices.yaml").write_text("devices: []\n")
    with pytest.raises(ValueError, match="changed"):
        document.write()
    (config / "devices.yaml").unlink()
    (config / "devices.json").write_text('{"devices": []}')
    with pytest.raises(ValueError, match="not YAML"):
        YamlFile("devices")


def test_new_yaml_file_has_restricted_permissions(config):
    document = YamlFile("directives")
    document.data = {"example": {"name": "Example"}}
    document.write()
    assert document.path.stat().st_mode & 0o777 == 0o600
    assert not list(config.glob(".directives.yaml.*"))


def test_runtime_does_not_replace_server_configuration(config):
    original = use_state("params")
    with runtime(plugins=True) as local:
        assert use_state() is local
        assert use_state("devices")[0].id == "test_frr"
        assert local.params.logging.session_log is False
        assert local.params.logging.samples.enable is False
    assert use_state("params") is original


def test_cases_cover_offered_builtins_and_families(config):
    with runtime() as state:
        queries = list(cases(state.devices[0], TARGETS))
        assert len(queries) == 8
        assert {target for _, target in queries} == set(TARGETS.values())
        entry = deepcopy(ENTRY)
        entry["vrf"] = "BLUE"
        vrf_device = Device(**entry)
        queries = list(cases(vrf_device, TARGETS))
        assert len(queries) == 4
        assert all("bgp" in directive for directive, _ in queries)


def test_check_uses_effective_defaults_and_actual_font_build(config, monkeypatch):
    # Project
    from hyperglass.cli.onboard import check

    monkeypatch.setattr(check, "cache_available", lambda: True)
    (config / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "structured": {
                    "rpki": {"mode": "external"},
                    "ip_enrichment": {"enrich_traceroute": True, "enrich_bgproute": True},
                },
                "web": {"dns_provider": {"name": "server"}},
            }
        )
    )
    ui = config / "static" / "ui"
    (ui / "fonts").mkdir(parents=True)
    (ui / "index.html").write_text('<link href="/fonts/body.css">')
    for kind in ("body", "mono"):
        (ui / "fonts" / f"{kind}.css").write_text("@font-face {}")
    result = runner.invoke(cli, ["onboard", "check", "--json"])
    assert result.exit_code == 0, (result.stdout, result.exception)
    rows = json.loads(result.stdout)["results"]
    assert all(row["status"] == "pass" for row in rows)
    assert all(not row["suggestion"] for row in rows)


def test_check_flags_only_disabled_features(config, monkeypatch):
    # Project
    from hyperglass.cli.onboard import check

    monkeypatch.setattr(check, "cache_available", lambda: False)
    (config / "config.yaml").write_text('web:\n  my_ip: "off"\n')
    result = runner.invoke(cli, ["onboard", "check", "--json"])
    assert result.exit_code == 0, result.exception
    rows = {row["feature"]: row for row in json.loads(result.stdout)["results"]}
    assert rows["Structured bgp_route"]["status"] == "pass"
    assert rows["My IP"]["suggestion"] == "web.my_ip: server"
    assert rows["RPKI cache"]["status"] == "off"
    assert rows["Self-hosted fonts"]["status"] == "unknown"


def test_fields_keep_zero_values_and_report_unverified():
    coverage = field_coverage(
        {
            "routes": [
                {"age": 0, "rpki_state": 0, "next_hop": "1.1.1.1", "communities": []},
                {"age": 3, "rpki_state": 3, "next_hop": "", "communities": ["1:2"]},
            ]
        }
    )
    assert coverage["fields"]["age"] == {"populated": 2, "empty": 0}
    assert coverage["fields"]["communities"] == {"populated": 1, "empty": 1}
    assert coverage["fields"]["rpki_state"]["unverified"] == 1


def test_check_does_not_request_version_for_vrf_commands(config, monkeypatch):
    from hyperglass.cli.onboard import check

    monkeypatch.setattr(check, "cache_available", lambda: True)
    entry = deepcopy(ENTRY)
    entry.update(vrf="BLUE", directives=["versioned-route"])
    (config / "directives.yaml").write_text(
        yaml.safe_dump(
            {
                "versioned-route": {
                    "name": "Versioned route",
                    "field": {"description": "Target"},
                    "rules": [
                        {
                            "condition": "0.0.0.0/0",
                            "command": "show {target}",
                            "fallback_command": "show old {target}",
                            "fallback_os_version": "<2",
                            "vrf_command": "show vrf {vrf} {target}",
                        }
                    ],
                },
            }
        )
    )
    (config / "devices.yaml").write_text(yaml.safe_dump({"devices": [entry]}))
    with runtime() as state:
        rows = check.check_config(state)
    assert not any(row["feature"].endswith("OS version") for row in rows)


@pytest.mark.asyncio
async def test_probe_uses_parser_and_does_not_reuse_ipv4_rule(config, monkeypatch):
    sent = []

    async def collect(self):
        sent.append(self.query)
        fixture = Path(__file__).parents[2] / "plugins/tests/fixtures/frr-live/route4.txt"
        return (fixture.read_text(),)

    monkeypatch.setattr(NetmikoConnection, "collect", collect)
    with runtime(plugins=True) as state:
        device = state.devices[0]
        directive = next(d.id for d in device.directives if d.query_kind == "bgp_route")
        first = await probe(device, directive, "1.1.1.0/24")
        second = await probe(device, directive, "2606:4700::/44")
    assert first["status"] == second["status"] == "pass", (first["error"], second["error"])
    assert first["structured"] is True
    assert first["coverage"]["rows"] > 0
    assert len(sent[0]) == len(sent[1]) == 1
    assert "ipv6" in sent[1][0]


def test_report_continues_after_failure_and_returns_nonzero(config, monkeypatch):
    async def collect(self):
        return ("% Invalid input detected at '^' marker",)

    monkeypatch.setattr(NetmikoConnection, "collect", collect)
    result = runner.invoke(cli, ["onboard", "test", "test_frr", "--json"])
    assert result.exit_code == 1
    data = json.loads(result.stdout)
    assert len(data["results"]) == 8
    assert all(row["status"] == "fail" for row in data["results"])
    assert all("Invalid input" in row["output"][0] for row in data["results"])
    assert "private-test-password" not in result.stdout + result.stderr


@pytest.mark.asyncio
async def test_empty_structured_table_reports_no_matches(config, monkeypatch):
    async def collect(self):
        return ("empty router table",)

    async def response(self, raw):
        return {"routes": []}

    monkeypatch.setattr(NetmikoConnection, "collect", collect)
    monkeypatch.setattr(NetmikoConnection, "response", response)
    with runtime() as state:
        device = state.devices[0]
        directive = next(d.id for d in device.directives if d.query_kind == "bgp_route")
        result = await probe(device, directive, "1.1.1.0/24")
    assert result["status"] == "fail"
    assert result["structured"] is True
    assert result["coverage"]["rows"] == 0
    assert "No matching rows" in result["error"]


def test_command_trace_captures_rejection_and_fallback():
    class Session:
        disconnected = False

        def send_command(self, command, **kwargs):
            return "% Invalid input" if command == "primary" else "success"

        def disconnect(self):
            self.disconnected = True

    session = Session()
    trace = []
    assert collect_commands(
        session, "cisco_ios", ["primary"], 10, fallbacks=["fallback"], trace=trace
    ) == ("success",)
    assert session.disconnected
    assert trace == [
        {"command": "primary", "fallback": False, "output": "% Invalid input"},
        {"command": "fallback", "fallback": True, "output": "success"},
    ]


def test_directive_scaffolds_runs_and_saves_without_attaching(config, monkeypatch):
    async def collect(self):
        return ("example output",)

    monkeypatch.setattr(NetmikoConnection, "collect", collect)
    before = (config / "devices.yaml").read_bytes()
    result = runner.invoke(
        cli,
        ["onboard", "directive", "test_frr", "--json"],
        input="\n".join(
            [
                "custom-route",
                'vtysh -c "show bgp {target}"',
                "",
                "1.1.1.0/24",
                "y",
                "",
            ]
        ),
    )
    assert result.exit_code == 0, (result.stdout, result.stderr, result.exception)
    data = json.loads(result.stdout)
    assert data["results"][0]["status"] == "pass"
    assert data["results"][0]["output"] == ["example output"]
    assert "custom-route" in yaml.safe_load((config / "directives.yaml").read_text())
    assert (config / "devices.yaml").read_bytes() == before


def test_invalid_credentials_do_not_appear_in_validation_error(config):
    entry = deepcopy(ENTRY)
    entry["credential"]["key"] = "/no/such/key"
    (config / "devices.yaml").write_text(yaml.safe_dump({"devices": [entry]}))
    result = runner.invoke(cli, ["onboard", "check", "--json"])
    assert result.exit_code == 1
    assert "error" in json.loads(result.stdout)
    assert "private-test-password" not in result.stdout + result.stderr


@pytest.mark.parametrize("version", [None, "15.9(3)M6"])
@pytest.mark.asyncio
async def test_probe_reports_reactive_and_version_fallback(config, monkeypatch, version):
    entry = deepcopy(ENTRY)
    entry.update(platform="cisco_ios", os_version=version, structured_output=False)
    (config / "devices.yaml").write_text(yaml.safe_dump({"devices": [entry]}))

    class Session:
        def send_command(self, command, **kwargs):
            return "% Invalid input" if "source" in command else "Trace complete"

        def disconnect(self):
            pass

    async def collect(self):
        return collect_commands(
            Session(),
            self.device.platform,
            self.query,
            10,
            fallbacks=self.fallbacks,
            trace=self.command_trace,
        )

    monkeypatch.setattr(NetmikoConnection, "collect", collect)
    with runtime() as state:
        device = state.devices[0]
        directive = next(d.id for d in device.directives if d.query_kind == "traceroute")
        result = await probe(device, directive, "2606:4700::1111")
    assert result["status"] == "pass", result["error"]
    assert result["fallback_used"] is True
    assert result["version_fallback"] is bool(version)
    assert len(result["attempts"]) == (1 if version else 2)
    assert result["attempts"][-1]["output"] is None
    if not version:
        assert result["attempts"][0]["command_error"] is True
        assert result["attempts"][0]["output"] == "% Invalid input"


def test_query_report_keeps_failed_attempt_when_connection_drops():
    class Session:
        disconnected = False

        def send_command(self, command, **kwargs):
            raise ConnectionError("dropped")

        def disconnect(self):
            self.disconnected = True

    session = Session()
    trace = []
    with pytest.raises(ConnectionError):
        collect_commands(session, "cisco_ios", ["command"], 10, trace=trace)
    assert session.disconnected
    assert trace == [{"command": "command", "fallback": False, "output": None}]


def test_invalid_yaml_does_not_leak_credential_lines(config):
    (config / "devices.yaml").write_text('credential: {password: "secret-invalid-yaml\n')
    result = runner.invoke(cli, ["onboard", "check", "--json"])
    assert result.exit_code == 1
    assert json.loads(result.stdout)["error"] == "Invalid YAML configuration"
    assert "secret-invalid-yaml" not in result.stdout + result.stderr
