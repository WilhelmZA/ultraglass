"""Load onboarding configuration without changing the running application's state."""

# Standard Library
import typing as t
from copy import deepcopy
from functools import cached_property
from contextlib import contextmanager

# Project
from hyperglass.state import HyperglassState
from hyperglass.settings import Settings
from hyperglass.state.hooks import scoped_state
from hyperglass.defaults.directives import init_builtin_directives
from hyperglass.models.config.devices import Devices
from hyperglass.configuration.validate import init_params, init_devices, init_directives


class OnboardState:
    """Keep device credentials and plugin registration in this CLI process only."""

    def __init__(self) -> None:
        self.params = init_params()
        self.directives = deepcopy(init_builtin_directives()) + init_directives()
        self.devices = Devices()
        self._plugins: dict[str, list] = {}
        # A probe must not write session transcripts, query samples or credentials.
        self.params.logging.session_log = False
        self.params.logging.samples.enable = False

    @cached_property
    def cache(self):
        """Use the configured Redis only for external lookup caches."""
        return HyperglassState(settings=Settings).cache

    def plugins(self, kind: str) -> list:
        """Return the local plugin registry."""
        return self._plugins.get(kind, [])

    def add_plugin(self, kind: str, plugin: t.Any) -> None:
        """Register a plugin locally."""
        self._plugins[kind] = list({*self.plugins(kind), plugin})


@contextmanager
def runtime(*, devices: bool = True, plugins: bool = False) -> t.Iterator[OnboardState]:
    """Validate files afresh and isolate all configuration from the server."""
    state = OnboardState()
    with scoped_state(state):
        if devices:
            state.devices = init_devices()
        if plugins:
            # Project
            from hyperglass.plugins import register_all_plugins

            register_all_plugins()
        yield state
