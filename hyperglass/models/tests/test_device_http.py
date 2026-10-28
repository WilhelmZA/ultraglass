"""Validate `platform: http` devices."""

# Third Party
import pytest

# Project
from hyperglass.exceptions.private import ConfigError
from hyperglass.models.config.devices import Device

CONFIG = {
    "name": "http-device",
    "address": "192.0.2.10",
    "credential": {"username": "lg", "password": "secret"},
}


def test_http_platform_requires_http_block():
    with pytest.raises(ConfigError, match="no http parameters are defined"):
        Device(**CONFIG, platform="http")


def test_http_platform_with_http_block():
    device = Device(**CONFIG, platform="http", http={"path": "/query"})

    assert device.platform == "http"
    assert device.http.path == "/query"


def test_ssh_platform_has_no_http_block():
    device = Device(
        **CONFIG, platform="frr", attrs={"source4": "192.0.2.1", "source6": "2001:db8::1"}
    )

    assert device.http is None
