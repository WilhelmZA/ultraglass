"""Optional directive variables with fixed choices (#52)."""

# Standard Library
import typing as t
from types import SimpleNamespace

# Third Party
import pytest

# Project
from hyperglass.models.api import Query
from hyperglass.exceptions.public import InputInvalid
from hyperglass.exceptions.private import ConfigError, InputValidationError
from hyperglass.models.directive import Directive
from hyperglass.models.config.devices import Device

# Local
from .._construct import Construct
from .test_construct import state, params  # noqa: F401

VARIABLES = {
    "instance": {
        "name": "Routing Instance",
        "command": " instance ",
        "items": [{"name": "Internet", "value": "inet"}, {"name": "VPN", "value": "vpn 1"}],
    },
    "group": {"command": " group ", "items": [{"name": "party_x"}]},
}


@pytest.fixture
def devices():
    return [
        {
            "name": platform,
            "address": "127.0.0.1",
            "credential": {"username": "", "password": ""},
            "platform": platform,
            "directives": ["bgp_summary"],
        }
        for platform in ("juniper", "frr")
    ]


@pytest.fixture
def directives():
    return [
        {
            "bgp_summary": {
                "name": "BGP Summary",
                "field": None,
                "rules": [{"condition": None, "command": "show bgp summary{instance}{group}"}],
                "variables": VARIABLES,
            }
        }
    ]


def _commands(location: str, **variables: str) -> t.List[str]:
    query = Query(
        queryLocation=location,
        queryTarget="null",
        queryType="bgp_summary",
        queryVariables=variables,
    )
    return Construct(device=query.device, query=query).queries()


@pytest.mark.usefixtures("state")
def test_no_variables_selected():
    assert _commands("juniper") == ["show bgp summary"]


@pytest.mark.usefixtures("state")
def test_variables_selected():
    assert _commands("juniper", group="party_x", instance="inet") == [
        "show bgp summary instance inet group party_x"
    ]


@pytest.mark.usefixtures("state")
def test_shell_platform_quotes_values():
    assert _commands("frr", instance="vpn 1") == ["show bgp summary instance 'vpn 1'"]


@pytest.mark.usefixtures("state")
@pytest.mark.parametrize(
    "variables",
    ({"instance": "inet; id"}, {"unknown": "x"}, {"group": "party_y"}),
)
def test_rejects_values_outside_choices(variables):
    with pytest.raises(InputInvalid):
        _commands("juniper", **variables)


def test_required_variable():
    directive = Directive(
        id="x",
        name="X",
        field=None,
        variables={"group": {**VARIABLES["group"], "required": True}},
    )
    directive.validate_variables({"group": "party_x"})
    with pytest.raises(InputValidationError) as err:
        directive.validate_variables({})
    assert err.value.kwargs["error"] == "'{name}' is required"


@pytest.mark.usefixtures("state")
def test_cache_key_includes_variables():
    base = Query(queryLocation="juniper", queryTarget="null", queryType="bgp_summary")
    selected = Query(
        queryLocation="juniper",
        queryTarget="null",
        queryType="bgp_summary",
        queryVariables={"group": "party_x"},
    )
    assert base.digest() != selected.digest()


@pytest.mark.parametrize("name", ("target", "mask", "bad-name"))
def test_rejects_reserved_or_invalid_names(name):
    with pytest.raises(ValueError):
        Directive(id="x", name="X", field=None, variables={name: VARIABLES["group"]})


def test_frontend_exports_choices():
    directive = Directive(id="x", name="X", field=None, variables=VARIABLES)
    exported = directive.frontend()["variables"]
    assert exported[0]["id"] == "instance"
    assert exported[0]["name"] == "Routing Instance"
    assert exported[1]["options"] == [{"name": "party_x", "value": "party_x", "description": None}]


def test_device_attrs_skip_variables_only():
    directive = Directive(
        id="y",
        name="Y",
        field=None,
        rules=[{"condition": None, "command": "show {other}{group}"}],
        variables={"group": VARIABLES["group"]},
    )
    device = SimpleNamespace(name="z", directives=[directive], attrs={"other": "x"})
    Device._validate_directive_attrs(device)
    device.attrs = {}
    with pytest.raises(ConfigError, match="other"):
        Device._validate_directive_attrs(device)
