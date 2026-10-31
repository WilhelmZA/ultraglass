"""Firewall command boundaries, parser completeness, and diagnostic setup failures."""

# Standard Library
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import Mock

# Third Party
import pytest

# Project
from hyperglass.state import use_state
from hyperglass.plugins import OutputPluginManager
from hyperglass.exceptions.private import ConfigError
from hyperglass.models.config.devices import Device
from hyperglass.execution.drivers._common import command_error
from hyperglass.execution.drivers._construct import Construct
from hyperglass.execution.drivers.ssh_netmiko import collect_commands
from hyperglass.plugins._builtin.bgp_route_panos import BGPRoutePluginPANOS, parse_panos
from hyperglass.plugins._builtin.bgp_route_fortinet import BGPRoutePluginFortinet, parse_fortinet
from hyperglass.plugins._builtin.trace_route_standard import TraceroutePluginStandard

FIXTURES = Path(__file__).parents[2] / "plugins/tests/fixtures/firewall-reference"


def device(platform, **kwargs):
    return Device(
        name="firewall",
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


@pytest.mark.parametrize("structured", [False, True])
@pytest.mark.parametrize(
    "target,expected,afi",
    [
        ("192.0.2.9", "192.0.2.9/32", "ipv4"),
        ("192.0.2.0/24", "192.0.2.0/24", "ipv4"),
        ("2001:db8::9", "2001:db8::9/128", "ipv6"),
        ("2001:db8::/32", "2001:db8::/32", "ipv6"),
    ],
)
def test_firewall_route_commands(structured, target, expected, afi):
    fortinet = device("fortinet", structured_output=structured)
    info = "info" if afi == "ipv4" else "info6"
    assert Construct(fortinet, query_for(fortinet, "bgp_route", target)).queries() == [
        f"get router {info} bgp network {target}"
    ]
    for vrf in (None, "BLUE"):
        panos = device("paloalto_panos", vrf=vrf, structured_output=structured)
        assert Construct(panos, query_for(panos, "bgp_route", target)).queries() == [
            f"show routing protocol bgp loc-rib-detail prefix {expected} virtual-router {vrf or 'default'} afi {afi} safi unicast"
        ]


@pytest.mark.parametrize("platform", ["fortinet", "paloalto_panos"])
def test_advertised_queries(platform):
    router = device(platform)
    assert {d.query_kind for d in router.directives} == {"bgp_route", "ping", "traceroute"}
    assert router.get_device_type() == platform
    # No cross-context diagnostic or search syntax is guessed.
    if platform == "fortinet":
        with pytest.raises(ConfigError, match="no VRF-capable"):
            device(platform, vrf="BLUE")
    else:
        router = device(platform, vrf="BLUE")
        assert {d.query_kind for d in router.directives} == {"bgp_route"}


@pytest.mark.parametrize("family,target", [(4, "192.0.2.9"), (6, "2001:db8::9")])
def test_diagnostic_commands(family, target):
    router = device("fortinet")
    suffix = "" if family == 4 else "6"
    source_option = "source" if family == 4 else "source6"
    source = router.attrs[f"source{family}"]
    assert Construct(router, query_for(router, "ping", target)).queries() == [
        f"execute ping{suffix}-options reset",
        f"execute ping{suffix}-options repeat-count 5",
        f"execute ping{suffix}-options timeout 1",
        f"execute ping{suffix}-options {source_option} {source}",
        f"execute ping{suffix} {target}",
        f"execute ping{suffix}-options reset",
    ]
    commands = Construct(router, query_for(router, "traceroute", target)).queries()
    assert commands == (
        [f"execute tracert6 {target}"]
        if family == 6
        else [
            "execute traceroute-options reset",
            "execute traceroute-options queries 1",
            f"execute traceroute-options source {source}",
            f"execute traceroute {target}",
            "execute traceroute-options reset",
        ]
    )
    router = device("paloalto_panos")
    inet6 = "inet6 yes " if family == 6 else ""
    assert Construct(router, query_for(router, "ping", target)).queries() == [
        f"ping count 5 {inet6}source {source} host {target}"
    ]
    assert Construct(router, query_for(router, "traceroute", target)).queries() == [
        f"traceroute ipv{family} yes max-ttl 30 wait 1 no-resolve yes source {source} host {target}"
    ]


def test_fortinet_reference_paths():
    route = parse_fortinet((FIXTURES / "fortinet-route4.txt").read_text()).routes[0]
    assert route.prefix == "4.5.6.0/24" and route.as_path == []
    assert route.active and route.weight == 32768 and route.local_preference == 100
    table = parse_fortinet((FIXTURES / "fortinet-multipath4.txt").read_text())
    assert table.count == 2 and [r.active for r in table.routes] == [False, True]
    assert [r.as_path for r in table.routes] == [[222], [111]]
    assert [r.weight for r in table.routes] == [0, 10]
    assert table.routes[1].peer_rid == "12.12.12.12" and table.routes[1].source_rid == "1.1.1.1"


def test_panos_reference_paths():
    params = use_state("params")
    params.structured.communities.mode = "deny"
    params.structured.communities.items = []
    use_state().redis.set("params", params)
    table = parse_panos((FIXTURES / "panos-route4.txt").read_text())
    assert table.count == 2 and table.vrf == "default"
    assert [r.active for r in table.routes] == [True, False]
    assert [r.as_path for r in table.routes] == [[100], [200, 100]]
    assert table.routes[0].communities == ["65535:0"]
    assert table.routes[0].source_rid == table.routes[0].peer_rid == ""
    assert table.routes[0].age == -1 and table.routes[0].rpki_state == 3


def test_synthetic_ipv6_and_vrf():
    text = (FIXTURES / "panos-route4.txt").read_text()
    text = text.replace("default", "BLUE").replace("10.10.10.0/24", "2001:db8::/32")
    text = text.replace("192.168.122.168", "2001:db8::1").replace("192.168.122.103", "2001:db8::2")
    table = parse_panos(text, "BLUE")
    assert table.routes[1].next_hop == "2001:db8::2"
    with pytest.raises(ValueError):
        parse_panos(text)
    text = (FIXTURES / "fortinet-route4.txt").read_text().replace("4.5.6.0/24", "2001:db8::/32")
    text = text.replace("10.9.15.254", "2001:db8::1").replace("from 0.0.0.0", "from ::")
    assert parse_fortinet(text).routes[0].next_hop == "2001:db8::1"


@pytest.mark.parametrize(
    "platform,file,plugin",
    [
        ("fortinet", "fortinet-multipath4.txt", BGPRoutePluginFortinet),
        ("paloalto_panos", "panos-route4.txt", BGPRoutePluginPANOS),
    ],
)
@pytest.mark.parametrize("structured", [False, True])
def test_parser_dispatch(platform, file, plugin, structured):
    router = device(platform, structured_output=structured)
    manager = OutputPluginManager()
    manager.register(plugin)
    output = ((FIXTURES / file).read_text(),)
    result = manager.execute(output=output, query=query_for(router, "bgp_route", "192.0.2.0/24"))
    if structured:
        assert result.count == 2
    else:
        assert result == output


@pytest.mark.parametrize(
    "platform,file,parser",
    [
        ("fortinet", "fortinet-multipath4.txt", parse_fortinet),
        ("paloalto_panos", "panos-route4.txt", parse_panos),
    ],
)
def test_reject_partial_and_combined_contexts(platform, file, parser):
    text = (FIXTURES / file).read_text()
    for broken in (text[: text.rfind("\n", 0, len(text) - 1)], text + text, "Invalid syntax."):
        with pytest.raises(ValueError):
            parser(broken)
    if platform == "fortinet":
        broken = text.replace("  222\n", "  {222,333}\n")
    else:
        broken = text.replace("200,100", "{200,100}")
    with pytest.raises(ValueError):
        parser(broken)


@pytest.mark.parametrize("platform", ["fortinet", "paloalto_panos"])
@pytest.mark.parametrize("address", ["192.0.2.9", "2001:db8::9"])
def test_synthetic_traceroute_dispatch(platform, address):
    router = device(platform, structured_output=True)
    manager = OutputPluginManager()
    manager.register(TraceroutePluginStandard)
    text = f"traceroute to {address} ({address}), 30 hops max\n 1 {address} 1.25 ms\n 2 * * *\n"
    result = manager.execute(output=("", text, ""), query=query_for(router, "traceroute", address))
    assert result.hops[0].ip_address == address and result.hops[0].rtt1 == 1.25


@pytest.mark.parametrize("failure_index", [0, 1, 2, 3])
@pytest.mark.parametrize(
    "error", ["Command fail. Return code -61", "command parse error before 'source'"]
)
def test_fortinet_setup_failure_stops_probes(failure_index, error):
    router = device("fortinet")
    commands = Construct(router, query_for(router, "ping", "192.0.2.9")).queries()
    connection = Mock()
    connection.send_command.side_effect = [""] * failure_index + [error]
    trace = []
    output = collect_commands(connection, "fortinet", commands, 10, trace=trace)
    assert command_error(output)
    assert connection.send_command.call_count == failure_index + 1
    assert trace[-1]["command"] == commands[failure_index] and trace[-1]["output"] == error
    connection.disconnect.assert_called_once()


def test_fortinet_timeout_releases_session():
    connection = Mock()
    connection.send_command.side_effect = TimeoutError("probe timeout")
    with pytest.raises(TimeoutError):
        collect_commands(connection, "fortinet", ["execute ping-options reset"], 10)
    connection.disconnect.assert_called_once()


def test_panos_command_error():
    assert command_error(("Invalid syntax.",))
