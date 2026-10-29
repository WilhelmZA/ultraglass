"""Unknown device keys are reported, not silently ignored (#107)."""

# Standard Library
from unittest.mock import Mock

# Project
from hyperglass.models.config import devices
from hyperglass.models.config.devices import Device

CONFIG = {
    "name": "JHB-1",
    "address": "192.0.2.10",
    "platform": "mikrotik_routeros",
    "attrs": {"source4": "192.0.2.10", "source6": "2001:db8::10"},
    "credential": {"username": "lg", "password": "secret"},
}


def _warnings(monkeypatch, **extra):
    log = Mock()
    monkeypatch.setattr(devices, "log", log)
    Device(**CONFIG, **extra)
    return [call.args for call in log.bind.return_value.warning.call_args_list]


def test_misspelt_key_names_device_and_nearest_key(monkeypatch):
    warnings = _warnings(monkeypatch, driver_args={"global_delay_factor": 3})
    assert warnings == [
        (
            "Device {!r} has unknown key {!r}, which is ignored{}",
            "JHB-1",
            "driver_args",
            "; did you mean 'driver_config' or 'driver'?",
        )
    ]


def test_unknown_key_without_a_close_match(monkeypatch):
    assert _warnings(monkeypatch, zzz=1) == [
        ("Device {!r} has unknown key {!r}, which is ignored{}", "JHB-1", "zzz", "")
    ]


def test_known_keys_and_aliases_do_not_warn(monkeypatch):
    assert _warnings(monkeypatch, driver_config={"global_delay_factor": 3}) == []
    assert _warnings(monkeypatch, driverConfig={"global_delay_factor": 3}) == []
