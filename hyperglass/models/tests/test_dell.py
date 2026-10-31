"""Dell platform command boundaries and Received-from detail parsing."""

# Standard Library
from types import SimpleNamespace
from pathlib import Path

# Third Party
import pytest

# Project
from hyperglass.plugins import OutputPluginManager
from hyperglass.models.config.devices import Device
from hyperglass.execution.drivers._construct import Construct
from hyperglass.plugins._builtin.bgp_route_dell import BGPRoutePluginDell, parse_dell
from hyperglass.plugins._builtin.trace_route_os9 import TraceroutePluginOS9
from hyperglass.plugins._builtin.trace_route_standard import TraceroutePluginStandard

FIXTURES = Path(__file__).parents[2] / "plugins/tests/fixtures/dell-reference"


def device(platform, **kwargs):
    return Device(
        name="dell",
        address="192.0.2.1",
        platform=platform,
        credential={"username": "reader", "password": "test"},
        attrs={"source4": "192.0.2.1", "source6": "2001:db8::1"},
        **kwargs,
    )


def query_for(router, kind, target):
    directive = next(d for d in router.directives if d.query_kind == kind)
    return SimpleNamespace(
        device=router, directive=directive, query_target=target, query_type=directive.id
    )


@pytest.mark.parametrize("platform", ["dell_os10", "dell_force10"])
@pytest.mark.parametrize("structured", [False, True])
@pytest.mark.parametrize("vrf", [None, "BLUE"])
@pytest.mark.parametrize(
    "target,expected,family",
    [
        ("1.1.1.1", "1.1.1.1/32", 4),
        ("1.1.1.0/24", "1.1.1.0/24", 4),
        ("2001:db8::1", "2001:db8::1/128", 6),
        ("2001:db8::/32", "2001:db8::/32", 6),
    ],
)
def test_route_commands(platform, structured, vrf, target, expected, family):
    router = device(platform, structured_output=structured, vrf=vrf)
    context = f"vrf {vrf} " if vrf else ""
    afi = "" if platform == "dell_os10" and family == 4 else f"ipv{family} unicast "
    assert Construct(router, query_for(router, "bgp_route", target)).queries() == [
        f"show ip bgp {context}{afi}{expected}"
    ]
    assert router.get_device_type() == platform


@pytest.mark.parametrize("platform", ["dell_os10", "dell_force10"])
@pytest.mark.parametrize("vrf", [None, "BLUE"])
def test_search_capabilities(platform, vrf):
    router = device(platform, vrf=vrf, structured_output=True)
    kinds = {d.query_kind for d in router.directives}
    assert ("bgp_aspath" in kinds) is (platform == "dell_force10")
    assert ("traceroute" in kinds) is (platform == "dell_os10" or vrf is None)
    for kind, verb, target in (
        ("bgp_community", "community", "65000:777"),
        ("bgp_aspath", "regexp", "_13335$"),
    ):
        if kind not in kinds:
            continue
        context = f"vrf {vrf} " if vrf else ""
        assert Construct(router, query_for(router, kind, target)).queries() == [
            f"show ip bgp {context}ipv4 unicast {verb} {target}",
            f"show ip bgp {context}ipv6 unicast {verb} {target}",
        ]


@pytest.mark.parametrize("vrf", [None, "BLUE"])
@pytest.mark.parametrize("family,target", [(4, "1.1.1.1"), (6, "2001:db8::1")])
def test_os10_diagnostics(vrf, family, target):
    router = device("dell_os10", vrf=vrf)
    context = f"vrf {vrf} " if vrf else ""
    ping = "ping" if family == 4 else "ping6"
    option = "-4 " if family == 4 else ""
    source = router.attrs[f"source{family}"]
    assert Construct(router, query_for(router, "ping", target)).queries() == [
        f"{ping} {context}{option}-c 5 -I {source} {target}"
    ]
    assert Construct(router, query_for(router, "traceroute", target)).queries() == [
        f"traceroute {context}{target} -{family} -n -q 1 -w 1 -s {source}"
    ]


@pytest.mark.parametrize("target", ["1.1.1.1", "2001:db8::1"])
def test_os9_diagnostics(target):
    router = device("dell_force10")
    assert Construct(router, query_for(router, "ping", target)).queries() == [
        f"ping {target} count 5"
    ]
    assert Construct(router, query_for(router, "traceroute", target)).queries() == [
        f"traceroute {target}"
    ]


@pytest.mark.parametrize(
    "file,path,prefix",
    [
        ("os9-route4.txt", [], "3.3.3.0/24"),
        ("os10-route4.txt", [100], "192.0.2.0/24"),
    ],
)
def test_vendor_reference_paths(file, path, prefix):
    table = parse_dell((FIXTURES / file).read_text(), "BLUE")
    assert table.vrf == "BLUE" and table.count == 1
    route = table.routes[0]
    assert route.active and route.as_path == path and route.prefix == prefix
    assert route.local_preference == 100 and route.med == 0 and route.weight == 0
    assert route.age == -1 and route.rpki_state == 3


def test_synthetic_ipv6_multipath():
    text = (FIXTURES / "os10-route4.txt").read_text()
    text = text.replace("192.0.2.0/24", "2001:db8::/32").replace("192.0.2.3(", "2001:db8::1(")
    text = text.replace("Next-Hop : 192.0.2.3", "Next-Hop : 2001:db8::1")
    second = (
        text[text.index("Received from") :]
        .replace(" Best", "")
        .replace("2001:db8::1", "2001:db8::2")
    )
    table = parse_dell(text.replace("1 available", "2 available") + second)
    assert [r.active for r in table.routes] == [True, False]
    assert table.routes[1].next_hop == "2001:db8::2"
    assert table.routes[1].source_rid == "192.0.2.33"


@pytest.mark.parametrize(
    "mutation",
    [
        lambda s: s.replace("1 available", "2 available"),
        lambda s: s.replace("AS_PATH : 100", "AS_PATH : {100,200}"),
        lambda s: s[: s.index("Origin INCOMPLETE")],
        lambda s: (FIXTURES / "os10-unnumbered.txt").read_text(),
    ],
)
def test_unsupported_or_truncated_response_stays_text(mutation):
    router = device("dell_os10", structured_output=True)
    output = (mutation((FIXTURES / "os10-route4.txt").read_text()),)
    assert (
        BGPRoutePluginDell().process(
            output=output, query=query_for(router, "bgp_route", "192.0.2.0/24")
        )
        == output
    )


@pytest.mark.parametrize("structured", [False, True])
@pytest.mark.parametrize(
    "platform,file,target",
    [
        ("dell_os10", "os10-trace6.txt", "20::1"),
        ("dell_force10", "os9-trace6.txt", "3ffe:501:ffff:100:201:e8ff:fe00:4c8b"),
    ],
)
def test_traceroute_dispatch_and_wrapped_ipv6(platform, file, target, structured):
    router = device(platform, structured_output=structured)
    manager = OutputPluginManager()
    manager.register(TraceroutePluginStandard)
    manager.register(TraceroutePluginOS9)
    output = ((FIXTURES / file).read_text(),)
    result = manager.execute(output=output, query=query_for(router, "traceroute", target))
    if structured:
        assert result.hops[0].ip_address == target
        assert result.hops[0].rtt1 == (0 if platform == "dell_force10" else 2.622)
        assert result.raw_output == output[0]
    else:
        assert result == output
