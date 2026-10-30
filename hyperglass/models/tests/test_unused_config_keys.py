"""Unused config keys are wired up or deprecated, never removed (#179)."""

# Standard Library
from unittest.mock import Mock

# Third Party
import pytest
from litestar import Litestar, get
from litestar.openapi import OpenAPIConfig

# Project
from hyperglass.models.config import messages
from hyperglass.models.config.docs import Docs
from hyperglass.models.config.devices import Device
from hyperglass.models.config.params import Params
from hyperglass.models.config.messages import DEPRECATED_MESSAGES, Messages


def _warned_keys(monkeypatch, **config):
    log = Mock()
    monkeypatch.setattr(messages, "log", log)
    Params(messages=config)
    return [call.args[1] for call in log.bind.return_value.warning.call_args_list]


def test_default_messages_do_not_warn(monkeypatch):
    assert _warned_keys(monkeypatch) == []


def test_live_message_key_does_not_warn(monkeypatch):
    assert _warned_keys(monkeypatch, no_output="Nothing found.") == []


@pytest.mark.parametrize("key", DEPRECATED_MESSAGES)
def test_explicit_deprecated_message_warns(monkeypatch, key):
    assert _warned_keys(monkeypatch, **{key: "custom"}) == [key]


def test_deprecated_message_set_to_its_default_still_warns(monkeypatch):
    assert _warned_keys(monkeypatch, no_response="No response.") == ["no_response"]


def test_messages_rebuilt_from_a_full_dump_do_not_warn(monkeypatch):
    """`UIParameters` revalidates messages from a dump that sets every key."""
    log = Mock()
    monkeypatch.setattr(messages, "log", log)
    Messages(**Messages().model_dump())
    assert log.bind.return_value.warning.call_args_list == []


def test_base_url_unset_publishes_no_server():
    assert Docs().server_url is None


def test_base_url_set_is_the_server_url():
    assert Docs(base_url="https://lg.example.com/").server_url == "https://lg.example.com"


def test_endpoint_blocks_reach_the_openapi_schema():
    docs = Docs(
        query={"title": "Run", "description": "Run a query.", "summary": "Query it"},
    )

    @get("/api/query")
    async def handler() -> dict:
        return {}

    for attr, value in docs.endpoint_docs("query").items():
        setattr(handler, attr, value)

    app = Litestar([handler], openapi_config=OpenAPIConfig(title="t", version="1"))
    operation = app.openapi_schema.to_schema()["paths"]["/api/query"]["get"]
    assert operation["tags"] == ["Run"]
    assert operation["summary"] == "Query it"
    assert operation["description"] == "Run a query."


def test_endpoint_block_defaults():
    assert Docs().endpoint_docs("info") == {
        "tags": ["System Information"],
        "summary": "System Information",
        "description": "General information about this looking glass.",
    }


@pytest.mark.parametrize("extra", [{}, {"platform": None}])
def test_missing_or_null_platform_is_rejected_before_the_validator(extra):
    config = {
        "name": "JHB-1",
        "address": "192.0.2.10",
        "credential": {"username": "lg", "password": "secret"},
        **extra,
    }
    with pytest.raises(ValueError, match="'platform' is missing"):
        Device(**config)
