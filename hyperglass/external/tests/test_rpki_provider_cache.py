"""RPKI backend selection must survive a warm cache (#22)."""

from unittest.mock import Mock

from hyperglass.external import rpki


def test_cache_separates_routinator_servers_and_cloudflare(monkeypatch):
    post = Mock(return_value={"data": {"validation": {"state": "valid"}}})
    monkeypatch.setattr(rpki.BaseExternal, "_post", post)
    responses = [
        Mock(json=lambda: {"validated_route": {"validity": {"state": "invalid"}}}),
        Mock(json=lambda: {"validated_route": {"validity": {"state": "not-found"}}}),
    ]
    get = Mock(side_effect=responses)
    monkeypatch.setattr(rpki.httpx, "get", get)
    assert rpki.rpki_state("1.1.1.0/24", 13335, "cloudflare") == 1
    assert rpki.rpki_state("1.1.1.0/24", 13335, "routinator", "https://one.test") == 0
    assert rpki.rpki_state("1.1.1.0/24", 13335, "routinator", "https://two.test") == 2
    assert rpki.rpki_state("1.1.1.0/24", 13335, "routinator", "https://one.test/") == 0
    assert rpki.rpki_state("1.1.1.0/24", 13335, "cloudflare") == 1
    assert post.call_count == 1
    assert get.call_count == 2
