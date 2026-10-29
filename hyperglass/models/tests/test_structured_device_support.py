"""Structured output is opt-in on every platform."""

import pytest

from hyperglass.constants import SUPPORTED_STRUCTURED_OUTPUT
from hyperglass.models.config.devices import Device


# `tnsr` has a parser but is not a valid device platform.
@pytest.mark.parametrize("platform", [p for p in SUPPORTED_STRUCTURED_OUTPUT if p != "tnsr"])
def test_structured_output_opt_in(platform):
    config = {
        "name": "test",
        "address": "127.0.0.1",
        "platform": platform,
        "credential": {"username": "lg", "password": ""},
        "attrs": {"source4": "192.0.2.1", "source6": "2001:db8::1"},
    }
    assert Device(**config).structured_output is False
    assert Device(**config, structured_output=False).structured_output is False
    assert Device(**config, structured_output=True).structured_output is True
