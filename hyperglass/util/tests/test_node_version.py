"""Test the NodeJS minimum version check."""

# Third Party
import pytest

# Project
from hyperglass.main import check_node_version
from hyperglass.constants import MIN_NODE_VERSION


def test_min_node_version():
    """The minimum is NodeJS 22.13, which pnpm 11.23.0 needs (#175)."""
    assert MIN_NODE_VERSION == (22, 13)


@pytest.mark.parametrize("version", [(18, 20, 4), (22, 12, 0), (22, 12, 99)])
def test_node_version_too_old(version):
    """NodeJS 18.x and 22.12 are rejected."""
    with pytest.raises(RuntimeError, match=r"NodeJS 22\.13\+ is required"):
        check_node_version(version)


@pytest.mark.parametrize("version", [(22, 13, 0), (22, 13, 1), (24, 0, 0), (24, 15, 0)])
def test_node_version_accepted(version):
    """NodeJS 22.13 and 24.x are accepted."""
    check_node_version(version)


def test_node_not_installed():
    """A missing NodeJS is rejected."""
    with pytest.raises(RuntimeError, match="NodeJS is not installed"):
        check_node_version(None)
