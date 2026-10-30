"""Exercise shared policies across vendor parsers for #22, without external services."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from hyperglass.models.config.params import Params
from hyperglass.models.data import bgp_route
from hyperglass.plugins._builtin.bgp_route_arista import parse_arista
from hyperglass.plugins._builtin.bgp_route_frr import parse_frr
from hyperglass.plugins._builtin.bgp_route_juniper import parse_juniper
from hyperglass.plugins._builtin.bgp_routestr_huawei import parse_huawei
from hyperglass.plugins._builtin.bgp_route_enrichment import ZBgpRouteEnrichment
from hyperglass.plugins.tests.test_bgp_route_huawei import SAMPLE as HUAWEI_SAMPLE

SAMPLES = Path(__file__).parents[3] / ".samples"
PARSERS = [
    (parse_arista, "arista_route.json"),
    (parse_frr, "frr_bgp_route.json"),
    (parse_juniper, "juniper_route_indirect.xml"),
    (parse_huawei, None),
    (parse_huawei, Path(__file__).parent / "fixtures/huawei-vrp/route4.txt"),
    (parse_huawei, Path(__file__).parent / "fixtures/huawei-vrp/community4.txt"),
]
PARSER_IDS = ["arista", "frr", "juniper", "huawei-synthetic", "huawei-detail", "huawei-brief"]


@pytest.mark.parametrize("parser,filename", PARSERS, ids=PARSER_IDS)
@pytest.mark.parametrize("mode", ["deny", "permit", "name"])
@pytest.mark.parametrize("backend", ["cloudflare", "routinator"])
def test_vendor_community_and_rpki_policy(monkeypatch, parser, filename, mode, backend):
    sample = (SAMPLES / filename).read_text() if filename else HUAWEI_SAMPLE
    params = Params()
    monkeypatch.setattr(bgp_route, "use_state", lambda _: params)
    baseline = parser((sample,))
    assert baseline.routes
    communities = [c for route in baseline.routes for c in route.communities]
    assert communities
    chosen = communities[0]
    params.structured.communities.mode = mode
    params.structured.communities.items = ["^" + chosen + "$"]
    params.structured.communities.names = {chosen: "test community"}
    params.structured.rpki.mode = "external"
    params.structured.rpki.rpki_server_url = "https://rpki.example.test"
    params.structured.rpki.backend = backend
    validate = Mock(side_effect=lambda pairs, **_: {(str(p), str(a)): 1 for p, a in pairs})
    monkeypatch.setattr(bgp_route, "rpki_states", validate)
    result = parser((sample,))
    assert len(result.routes) == len(baseline.routes)
    for original, route in zip(baseline.routes, result.routes):
        expected = [
            f"{c},test community" if mode == "name" and c == chosen else c
            for c in original.communities
            if mode == "name" or (c == chosen) == (mode == "permit")
        ]
        assert route.communities == expected
        assert route.filtered is False
        assert route.next_hop_org is None
    for call in validate.call_args_list:
        assert call.kwargs["backend"] == backend
        assert call.kwargs["rpki_server_url"] == "https://rpki.example.test"


@pytest.mark.parametrize("parser,filename", PARSERS, ids=PARSER_IDS)
@pytest.mark.parametrize("mode", ["inline", "async"])
def test_vendor_enrichment_dispatch(monkeypatch, parser, filename, mode):
    from hyperglass.state import use_state

    params = use_state("params")
    params.structured.ip_enrichment.mode = mode
    params.structured.ip_enrichment.enrich_bgproute = True
    sample = (SAMPLES / filename).read_text() if filename else HUAWEI_SAMPLE
    table = parser((sample,))
    asns, hops = AsyncMock(), AsyncMock()
    monkeypatch.setattr(bgp_route.BGPRouteTable, "enrich_as_path_organizations", asns)
    monkeypatch.setattr(bgp_route.BGPRouteTable, "enrich_with_ip_enrichment", hops)
    assert ZBgpRouteEnrichment().process(output=table, query=SimpleNamespace()) is table
    assert asns.await_count == (1 if mode == "inline" else 0)
    assert hops.await_count == (1 if mode == "inline" else 0)
    assert params.structured.is_async_enrichment_enabled(table) == (mode == "async")
