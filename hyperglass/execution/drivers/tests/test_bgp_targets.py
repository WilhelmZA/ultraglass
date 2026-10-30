"""Regression coverage for #28, #31 and #34."""

import shlex
from types import SimpleNamespace

import pytest

from hyperglass.defaults.directives import init_builtin_directives
from hyperglass.exceptions.private import InputValidationError
from hyperglass.exceptions.public import InputInvalid
from hyperglass.execution.drivers._construct import Construct


def construct(platform, kind, target, os_version=None, fallbacks=False):
    prefix = "mikrotik" if platform.startswith("mikrotik") else platform
    directive = next(
        d.model_copy(deep=True)
        for d in init_builtin_directives()
        if d.id == f"__hyperglass_{prefix}_{kind}__"
    )
    device = SimpleNamespace(platform=platform, name="test", attrs={}, os_version=os_version)
    query = SimpleNamespace(
        device=device, directive=directive, query_type=directive.id, query_target=target
    )
    directive.validate_target(target)
    built = Construct(device, query)
    queries = built.queries()
    return (queries, built.fallbacks) if fallbacks else queries


@pytest.mark.parametrize(
    "platform", ["bird", "frr", "openbgpd", "vyos", "mikrotik_routeros", "arista_eos"]
)
@pytest.mark.parametrize("kind", ["bgp_aspath", "bgp_community"])
@pytest.mark.parametrize(
    "target", ['13335"; id; #', "$(id)", "`id`", "13335\nid", "13335\r", "13335\\", "13335\x00"]
)
def test_reject_command_injection(platform, kind, target):
    with pytest.raises(InputValidationError):
        construct(platform, kind, target)


@pytest.mark.parametrize(
    "target", ["_13335$", "^13335_", "_13335_", "_13335(_.+_)65001$", "^(13335|65001)$"]
)
def test_frr_preserves_regex_as_one_shell_argument(target):
    commands = construct("frr", "bgp_aspath", target)
    assert shlex.split(commands[0]) == ["vtysh", "-c", f"show bgp ipv4 unicast regexp {target}"]


@pytest.mark.parametrize("target", ["_13335$", "^(13335|65001)$"])
def test_vyos_quotes_regex_as_one_shell_argument(target):
    assert shlex.split(construct("vyos", "bgp_aspath", target)[0]) == [
        "show",
        "bgp",
        "ipv4",
        "regexp",
        target,
    ]
    assert shlex.split(construct("vyos", "bgp_aspath_table", target)[0]) == [
        "vtysh",
        "-c",
        f"show bgp ipv4 unicast regexp {target} json",
    ]


@pytest.mark.parametrize(
    "target,mask",
    [
        ("_13335$", "[= * 13335 =]"),
        ("^13335_", "[= 13335 * =]"),
        ("_13335_", "[= * 13335 * =]"),
        ("13335", "[= * 13335 * =]"),
        ("^65000_13335$", "[= 65000 13335 =]"),
    ],
)
def test_bird_masks(target, mask):
    assert shlex.split(construct("bird", "bgp_aspath", target)[0]) == [
        "birdc",
        f"show route all where bgp_path ~ {mask}",
    ]


def test_bird_rejects_unsupported_regex():
    with pytest.raises(InputInvalid):
        construct("bird", "bgp_aspath", "^(13335|65001)$")


def test_bird_community():
    assert shlex.split(construct("bird", "bgp_community", "13335:100")[0]) == [
        "birdc",
        "show route all where (13335,100) ~ bgp_community",
    ]


@pytest.mark.parametrize("suffix", ["", "_table"])
@pytest.mark.parametrize(
    "kind,target,keyword",
    [
        ("bgp_aspath", "_13335$", "regular-expression"),
        ("bgp_community", "37195:302", "community"),
    ],
)
def test_huawei_targets_are_not_literal_quoted(suffix, kind, target, keyword):
    assert construct("huawei", kind + suffix, target) == [
        f"display bgp routing-table {keyword} {target}",
        f"display bgp ipv6 routing-table {keyword} {target}",
    ]


@pytest.mark.parametrize(
    "target,operator",
    [
        ("_13335$", "source-as"),
        ("^13335_", "peer-as"),
        ("_13335_", "as"),
        ("13335", "as"),
    ],
)
def test_openbgpd_as_selectors(target, operator):
    assert shlex.split(construct("openbgpd", "bgp_aspath", target)[0]) == [
        "bgpctl",
        "show",
        "rib",
        "inet",
        operator,
        "13335",
    ]


def test_mikrotik_both_variants_use_ros7_and_escape_anchors():
    for suffix in ("", "_table"):
        assert construct("mikrotik_routeros", f"bgp_aspath{suffix}", "_13335$") == [
            "routing route print detail without-paging where bgp "
            'and bgp.as-path~"(^|[ ,]|\\$)13335\\$"'
        ]
        assert construct("mikrotik_routeros", f"bgp_community{suffix}", "37195:302") == [
            "routing route print detail without-paging where bgp "
            'and bgp.communities~"(^|[,;])37195:302([,;]|\\$)"'
        ]


ROS6_ASPATH = 'route print detail without-paging where bgp and bgp-as-path~"(^|[ ,]|\\$)13335\\$"'
ROS6_COMMUNITY = (
    'route print detail without-paging where bgp and bgp-communities~"(^|[,;])37195:302([,;]|\\$)"'
)


@pytest.mark.parametrize("suffix", ["", "_table"])
@pytest.mark.parametrize(
    "kind,target,attr",
    [("bgp_aspath", "_13335$", ROS6_ASPATH), ("bgp_community", "37195:302", ROS6_COMMUNITY)],
)
def test_mikrotik_routeros6_pattern_commands(suffix, kind, target, attr):
    """RouterOS 6 reads both address families in one command (#117)."""
    both = f"ip {attr}; ipv6 {attr}"
    assert construct("mikrotik_routeros", f"{kind}{suffix}", target, os_version="6.49.19") == [both]
    queries, fallbacks = construct("mikrotik_routeros", f"{kind}{suffix}", target, fallbacks=True)
    assert queries[0].startswith("routing route ")
    assert fallbacks == [both]
    assert construct("mikrotik_routeros", f"{kind}{suffix}", target, os_version="7.16.2")[
        0
    ].startswith("routing route ")


@pytest.mark.parametrize("suffix", ["", "_table"])
@pytest.mark.parametrize(
    "target,menu,default",
    [("1.1.1.0/24", "ip", "0.0.0.0/0"), ("2606:4700::/44", "ipv6", "::/0")],
)
def test_mikrotik_routeros6_route_commands(suffix, target, menu, default):
    """RouterOS 6 has no `routing route` menu (#117)."""
    command = (
        f"{menu} route print detail without-paging where {target} in dst-address bgp "
        f"and dst-address !={default}"
    )
    assert construct("mikrotik_routeros", f"bgp_route{suffix}", target, os_version="6.49") == [
        command
    ]
    _, fallbacks = construct("mikrotik_routeros", f"bgp_route{suffix}", target, fallbacks=True)
    assert fallbacks == [command]
