"""Custom directives can use `{mask}` without a device attribute (#168)."""

# Third Party
import pytest

# Project
from hyperglass.models.api import Query
from hyperglass.models.directive import Directive
from hyperglass.models.config.devices import directive_attr_keys

# Local
from .._construct import Construct
from .test_construct import state, params  # noqa: F401


@pytest.fixture
def devices():
    return [
        {
            "name": "juniper",
            "address": "127.0.0.1",
            "credential": {"username": "", "password": ""},
            "platform": "juniper",
            "directives": ["route_mask"],
        }
    ]


@pytest.fixture
def directives():
    return [
        {
            "route_mask": {
                "name": "Route With Mask",
                "field": {"description": "IP prefix"},
                "rules": [
                    {"condition": "0.0.0.0/0", "command": "show route {target}/{mask}"},
                ],
            }
        }
    ]


def test_mask_is_not_a_device_attribute():
    directive = Directive(
        id="x",
        name="X",
        field={"description": "IP prefix"},
        rules=[{"condition": "0.0.0.0/0", "command": "show route {target} {mask} {extra}"}],
    )
    assert directive_attr_keys([directive], vrf=False) == {"extra"}


@pytest.mark.usefixtures("state")
@pytest.mark.parametrize(
    "target,expected",
    (
        ("198.18.0.0/15", "show route 198.18.0.0/15/255.254.0.0"),
        ("1.1.1.1", "show route 1.1.1.1/255.255.255.255"),
    ),
)
def test_custom_directive_mask(target, expected):
    query = Query(queryLocation="juniper", queryTarget=target, queryType="route_mask")
    assert Construct(device=query.device, query=query).queries() == [expected]
