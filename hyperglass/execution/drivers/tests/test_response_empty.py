"""Blank text responses report no matching results (#195)."""

# Standard Library
from types import SimpleNamespace

# Third Party
import pytest

# Project
from hyperglass.execution import main
from hyperglass.exceptions.public import ResponseEmpty


def _query():
    device = SimpleNamespace(id="lab-frr", name="lab-frr", driver="netmiko", proxy=None)
    return SimpleNamespace(
        device=device,
        query_type="__hyperglass_frr_bgp_aspath__",
        query_target="_65001$",
        summary=lambda: "query",
    )


@pytest.fixture
def respond(monkeypatch):
    def factory(output):
        class Driver:
            def __init__(self, *_):
                pass

            async def collect(self):
                return output

            async def response(self, response):
                return response

        monkeypatch.setattr(main, "map_driver", lambda _: Driver)
        monkeypatch.setattr(main.signal, "alarm", lambda _: None)

    return factory


@pytest.mark.asyncio
@pytest.mark.parametrize("output", [(), ("",), ("\n", "\n"), ("  \n", ""), "", "\n\n", " \n "])
async def test_blank_text_raises_response_empty(respond, output):
    respond(output)
    with pytest.raises(ResponseEmpty):
        await main.execute(_query())


@pytest.mark.asyncio
@pytest.mark.parametrize("output", [("route",), ("", "route"), "route"])
async def test_text_with_content_is_returned(respond, output):
    respond(output)
    result = await main.execute(_query())
    assert "route" in result
