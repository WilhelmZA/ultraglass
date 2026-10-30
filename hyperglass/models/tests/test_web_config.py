"""Test web configuration models."""

# Third Party
import pytest
from pydantic import ValidationError

# Local
from ..config.web import Logo


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
