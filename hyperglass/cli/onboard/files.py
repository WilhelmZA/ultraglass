"""Read and update onboarding YAML files."""

# Standard Library
import os
import tempfile
from copy import deepcopy

# Third Party
import yaml

# Project
from hyperglass.settings import Settings
from hyperglass.configuration.load import find_path


class YamlFile:
    """Preserve unrelated configuration and reject concurrent edits."""

    def __init__(self, name: str) -> None:
        self.path = find_path(name, required=False) or Settings.app_path / f"{name}.yaml"
        if self.path.suffix not in (".yaml", ".yml"):
            raise ValueError(f"{self.path.name} is not YAML; convert it before using this editor")
        self.original = self.path.read_bytes() if self.path.exists() else None
        try:
            self.data = yaml.safe_load(self.original) if self.original is not None else {}
        except yaml.YAMLError as error:
            # YAML exceptions can contain plaintext credentials from the offending line.
            raise ValueError(f"Invalid YAML in {self.path.name}") from error
        if self.data is None:
            self.data = {}
        if not isinstance(self.data, dict):
            raise ValueError(f"{self.path.name} must contain a mapping")

    def device_entries(self) -> list[dict]:
        """Resolve the same top-level device keys as the application."""
        key = next((key for key in ("main", "devices", "routers") if key in self.data), "devices")
        entries = self.data.setdefault(key, [])
        if not isinstance(entries, list) or any(not isinstance(item, dict) for item in entries):
            raise ValueError(f"{key} must be a list of device mappings")
        return entries

    def write(self) -> None:
        """Atomically replace YAML, with restrictive permissions for new files."""
        content = yaml.safe_dump(self.data, sort_keys=False, allow_unicode=True)
        current = self.path.read_bytes() if self.path.exists() else None
        if current != self.original:
            raise ValueError(f"{self.path.name} changed during onboarding; retry")
        fd, temporary = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                if self.path.exists():
                    os.fchmod(handle.fileno(), self.path.stat().st_mode & 0o777)
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


def copy_entry(entries: list[dict], name: str) -> tuple[int | None, dict]:
    """Find an exact name or generated ID without modifying another YAML anchor user."""
    # Project
    from hyperglass.models.config.devices import Device

    for index, entry in enumerate(entries):
        if name in (entry.get("name"), Device._with_id(deepcopy(entry))["id"]):
            return index, deepcopy(entry)
    return None, {"name": name}
