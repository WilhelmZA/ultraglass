"""Test web configuration models."""

# Third Party
import pytest
from pydantic import ValidationError

# Project
from hyperglass.constants import DNS_OVER_HTTPS

# Local
from ..config.web import Logo, DnsOverHttps


@pytest.mark.parametrize("value", (50, "50", "50%"))
def test_logo_width_normalised(value):
    """A bare width keeps validating and gains a `%` (#177)."""
    assert Logo(width=value).width == "50%"


def test_logo_width_default():
    assert Logo().width == "50%"


@pytest.mark.parametrize("value", (25, "25", "25%"))
def test_logo_height_accepted(value):
    """Height stays accepted and is normalised like width (#177)."""
    assert Logo(height=value).height == "25%"


def test_logo_height_default():
    assert Logo().height is None


@pytest.mark.parametrize("value", ("0", "101", "50px", "abc", True))
def test_logo_width_invalid(value):
    with pytest.raises(ValidationError):
        Logo(width=value)


@pytest.mark.parametrize(
    "data,expected",
    (
        ({}, ("cloudflare", DNS_OVER_HTTPS["cloudflare"])),
        ({"name": "google"}, ("google", DNS_OVER_HTTPS["google"])),
        ({"name": "server"}, ("server", DNS_OVER_HTTPS["server"])),
        ({"name": "custom", "url": "https://doh.example/q"}, ("custom", "https://doh.example/q")),
        ({"url": "https://doh.example/q"}, ("custom", "https://doh.example/q")),
    ),
)
def test_dns_provider_valid(data, expected):
    model = DnsOverHttps(**data)
    assert (model.name, model.url) == expected


@pytest.mark.parametrize("data", ({"name": "custom"}, {"name": "quad8"}))
def test_dns_provider_invalid(data):
    """An unknown name, or custom without url, names the key and the providers (#178)."""
    with pytest.raises(ValidationError) as err:
        DnsOverHttps(**data)
    message = str(err.value)
    assert "web.dns_provider" in message
    for name in DNS_OVER_HTTPS:
        assert name in message
