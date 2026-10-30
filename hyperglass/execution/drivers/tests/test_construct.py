# Standard Library
import typing as t

# Third Party
import pytest

# Project
from hyperglass.state import use_state
from hyperglass.state.hooks import _use_state
from hyperglass.models.api import Query
from hyperglass.configuration import init_ui_params
from hyperglass.models.directive import Directives
from hyperglass.models.config.params import Params
from hyperglass.models.config.devices import Devices
from hyperglass.exceptions.private import InputValidationError
from hyperglass.defaults.directives import init_builtin_directives
from hyperglass.plugins import InputPluginManager
from hyperglass.plugins._builtin import BGPRoutePluginHuawei

# Local
from .._construct import Construct

if t.TYPE_CHECKING:
    # Project
    from hyperglass.state import HyperglassState


@pytest.fixture
def params():
    return {}


@pytest.fixture
def devices():
    return [
        {
            "name": "test1",
            "address": "127.0.0.1",
            "credential": {"username": "", "password": ""},
            "platform": "juniper",
            "attrs": {"source4": "192.0.2.1", "source6": "2001:db8::1"},
            "directives": ["juniper_bgp_route"],
        }
    ]


@pytest.fixture
def directives():
    return [
        {
            "juniper_bgp_route": {
                "name": "BGP Route",
                "field": {"description": "test"},
                "rules": [{"condition": "0.0.0.0/0"}],
            }
        }
    ]


@pytest.fixture
def state(
    *,
    params: t.Dict[str, t.Any],
    directives: t.Sequence[t.Dict[str, t.Any]],
    devices: t.Sequence[t.Dict[str, t.Any]],
) -> t.Generator["HyperglassState", None, None]:
    """Test fixture to initialize Redis store."""
    _use_state.cache_clear()
    _state = use_state()
    _params = Params(**params)
    _directives = Directives.new(*directives)

    with _state.cache.pipeline() as pipeline:
        # Write params and directives to the cache first to avoid a race condition where ui_params
        # or devices try to access params or directives before they're available.
        pipeline.set("params", _params)
        pipeline.set("directives", _directives)

    _devices = Devices(*devices)
    ui_params = init_ui_params(params=_params, devices=_devices)

    with _state.cache.pipeline() as pipeline:
        pipeline.set("devices", _devices)
        pipeline.set("ui_params", ui_params)

    yield _state
    _state.clear()


def test_construct(state):
    query = Query(
        queryLocation="test1",
        queryTarget="192.0.2.0/24",
        queryType="juniper_bgp_route",
    )
    constructor = Construct(device=state.devices["test1"], query=query)
    assert constructor.target == "192.0.2.0/24"


def test_construct_normalizes_cidr_host_bits(state):
    query = Query(
        queryLocation="test1",
        queryTarget="192.0.2.1/24",
        queryType="juniper_bgp_route",
    )

    assert query.query_target == "192.0.2.0/24"
    constructor = Construct(device=state.devices["test1"], query=query)
    assert constructor.target == "192.0.2.0/24"


@pytest.fixture
def huawei_state():
    """Two Huawei devices with built-in directives, text and structured."""
    _use_state.cache_clear()
    _state = use_state()
    _params = Params()
    _state.cache.set("params", _params)
    _state.cache.set("directives", init_builtin_directives())
    InputPluginManager().register(BGPRoutePluginHuawei)
    _devices = Devices(
        *(
            {
                "name": name,
                "address": "127.0.0.1",
                "credential": {"username": "", "password": ""},
                "platform": "huawei",
                "structured_output": structured,
                "attrs": {"source4": "192.0.2.1", "source6": "2001:db8::1"},
            }
            for name, structured in (("text", False), ("structured", True))
        )
    )
    _state.cache.set("devices", _devices)
    _state.cache.set("ui_params", init_ui_params(params=_params, devices=_devices))
    yield _state
    _state.clear()


@pytest.mark.parametrize(
    "location,directive_id",
    [
        ("text", "__hyperglass_huawei_bgp_route__"),
        ("structured", "__hyperglass_huawei_bgp_route_table__"),
    ],
)
@pytest.mark.parametrize(
    "target,expected",
    [("1.1.1.0/24", "1.1.1.0 24"), ("2606:4700::/44", "2606:4700:: 44")],
)
def test_huawei_cidr_target_survives_execution_recheck(
    huawei_state, location, directive_id, target, expected
):
    """Regression for #132: the recheck must not reject the Huawei `a b` rewrite."""
    query = Query(queryLocation=location, queryTarget=target, queryType=directive_id)
    assert query.query_target == expected
    constructor = Construct(device=huawei_state.devices[location], query=query)
    assert constructor.target == expected
    assert any(expected in command for command in constructor.queries())


def test_execution_recheck_still_rejects_transformed_command_syntax(huawei_state):
    """The rewritten target still passes the built-in syntax check (#28)."""
    query = Query(
        queryLocation="text", queryTarget="_13335$", queryType="__hyperglass_huawei_bgp_aspath__"
    )
    query.query_target = "13335; display current-configuration"
    with pytest.raises(InputValidationError):
        Construct(device=huawei_state.devices["text"], query=query)
