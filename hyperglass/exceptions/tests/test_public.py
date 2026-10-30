"""Test formatting of public error messages."""

# Standard Library
from types import SimpleNamespace

# Third Party
import pytest

# Project
from hyperglass.state import use_state

# Local
from .. import public
from .._common import PublicHyperglassError

DEVICE = SimpleNamespace(name="lab-router", proxy=None)
QUERY = SimpleNamespace(query_type="bgp_route", query_target="192.0.2.0/24")

PUBLIC_ERRORS = (
    (public.ScrapeError, {"error": Exception("boom"), "device": DEVICE}),
    (public.AuthError, {"error": Exception("boom"), "device": DEVICE}),
    (public.RestError, {"error": Exception("boom"), "device": DEVICE}),
    (public.DeviceTimeout, {"error": Exception("boom"), "device": DEVICE}),
    (public.NotFound, {"type": "Device", "name": "missing"}),
    (public.QueryLocationNotFound, {"location": "missing"}),
    (public.QueryTypeNotFound, {"query_type": "missing"}),
    (public.InputInvalid, {"error": "boom", "target": "192.0.2.1"}),
    (public.InputNotAllowed, {"error": "boom", "query": QUERY}),
    (public.ResponseEmpty, {"error": "boom", "query": QUERY}),
    (public.DeviceCommandError, {"device_name": "lab-router"}),
)


@pytest.mark.parametrize(
    ("error_class", "kwargs"), PUBLIC_ERRORS, ids=[e[0].__name__ for e in PUBLIC_ERRORS]
)
def test_public_error_default_template(error_class, kwargs):
    """Every public error formats its default template without raising."""
    err = error_class(**kwargs)
    assert err.message
    assert "{" not in err.message


@pytest.mark.parametrize("error_class", (public.ScrapeError, public.RestError))
def test_connection_error_names_device(error_class):
    """The default connection error template shows the device name."""
    err = error_class(error=Exception("boom"), device=DEVICE)
    assert err.message.startswith("Error connecting to lab-router: boom")


@pytest.mark.parametrize("placeholder", ("{device}", "{device_name}"))
@pytest.mark.parametrize(
    "error_class", (public.ScrapeError, public.AuthError, public.RestError, public.DeviceTimeout)
)
def test_custom_template_device_placeholders(placeholder, error_class):
    """Custom templates written with `{device}` or `{device_name}` both work."""
    params = use_state("params")
    template_name = error_class._original_template_name
    params.messages = params.messages.model_copy(
        update={template_name: f"Failed on {placeholder}: {{error}}"}
    )
    use_state().redis.set("params", params)
    err = error_class(error=Exception("boom"), device=DEVICE)
    assert err.message.startswith("Failed on lab-router: boom")


@pytest.mark.parametrize(
    ("template", "expected"),
    (
        ("Error connecting to {device_name}: {error}", "Error connecting to : x"),
        ("{unknown} and {error}", " and x"),
        ("{0} positional", " positional"),
        ("{error.missing_attr} attr", " attr"),
        ("{error[3]} index", " index"),
        ("no placeholders", "no placeholders"),
    ),
)
def test_safe_format_blanks_unknown_placeholders(template, expected):
    """Unknown placeholders are blanked, not raised."""
    assert PublicHyperglassError._safe_format(template, error="x", device="lab") == expected


@pytest.mark.parametrize("template", ("unbalanced {brace", "stray } brace", "{error!z}"))
def test_safe_format_never_raises(template):
    """A template that cannot be parsed is returned unchanged."""
    assert PublicHyperglassError._safe_format(template, error="x") == template


def test_error_text_not_repeated_when_template_has_error():
    """A template that already shows `{error}` gets no ` (error)` suffix (#187)."""
    err = public.ScrapeError(error=Exception("boom"), device=DEVICE)
    assert err.message.count("boom") == 1


def test_error_text_appended_when_template_lacks_error():
    """A template without `{error}` still shows the error once, in parentheses (#187)."""
    err = public.AuthError(error=Exception("boom"), device=DEVICE)
    assert err.message.endswith(" (boom)")
    assert err.message.count("boom") == 1
