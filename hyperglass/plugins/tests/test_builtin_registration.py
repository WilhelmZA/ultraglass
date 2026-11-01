"""Built-in plugins register only through the names exported from the package."""

# Standard Library
import pkgutil
import importlib
from inspect import isclass, getmembers
from pathlib import Path

# Project
from hyperglass.plugins import _builtin
from hyperglass.plugins._input import InputPlugin
from hyperglass.plugins._output import OutputPlugin

def test_every_builtin_plugin_is_exported():
    """`init_builtin_plugins` reads the classes imported into `_builtin/__init__.py`.

    A plugin module that is not imported there is never registered, so its parser never runs
    in the application even though tests that register it by hand pass.
    """
    missing = []
    for _, module_name, _ in pkgutil.iter_modules([str(Path(_builtin.__file__).parent)]):
        module = importlib.import_module(f"hyperglass.plugins._builtin.{module_name}")
        for class_name, obj in getmembers(module, isclass):
            if obj.__module__ != module.__name__:
                continue
            if not issubclass(obj, (OutputPlugin, InputPlugin)):
                continue
            exported = getattr(_builtin, class_name, None) is obj and class_name in _builtin.__all__
            if not exported:
                missing.append(f"{module_name}.{class_name}")
    assert not missing, f"Not exported from hyperglass.plugins._builtin: {missing}"
