"""The complete sample config sets every config key and validates."""

# Standard Library
import typing as t
import inspect
from pathlib import Path

# Third Party
import yaml
from pydantic import BaseModel

# Project
from hyperglass.models.config.params import Params

SAMPLE = Path(__file__).parents[3] / ".samples" / "sample_config.yaml"

# Keys documented only in a comment: deprecated, ignored, or kill switches whose
# only useful value turns a feature off.
COMMENTED = {
    "messages.feature_not_enabled",
    "messages.invalid_query",
    "messages.invalid_field",
    "messages.no_response",
    "web.logo.height",
    "structured.enable_for_traceroute",
    "structured.enable_for_bgp_route",
}


def _models(annotation: t.Any) -> t.List[t.Type[BaseModel]]:
    found = []
    if inspect.isclass(annotation) and issubclass(annotation, BaseModel):
        found.append(annotation)
    for arg in t.get_args(annotation):
        found.extend(_models(arg))
    return found


def _model_keys(model: t.Type[BaseModel], prefix: str = "") -> t.Set[str]:
    keys = set()
    for name, field in model.model_fields.items():
        if field.exclude:
            continue
        keys.add(prefix + name)
        for sub in _models(field.annotation):
            keys |= _model_keys(sub, f"{prefix}{name}.")
    return keys


def _yaml_keys(value: t.Any, prefix: str = "") -> t.Set[str]:
    keys = set()
    if isinstance(value, dict):
        for name, sub in value.items():
            keys.add(prefix + str(name))
            # Free-form mappings (community names, webhook headers) hold data, not keys.
            if prefix + str(name) not in {
                "structured.communities.names",
                "logging.http.headers",
                "logging.http.params",
            }:
                keys |= _yaml_keys(sub, f"{prefix}{name}.")
    elif isinstance(value, list):
        for item in value:
            keys |= _yaml_keys(item, prefix)
    return keys


def _load() -> t.Dict[str, t.Any]:
    return yaml.safe_load(SAMPLE.read_text())


def test_sample_config_sets_every_key():
    missing = _model_keys(Params) - _yaml_keys(_load()) - COMMENTED
    assert not missing, f"Add these keys to {SAMPLE.name}: {sorted(missing)}"


def test_commented_keys_are_documented():
    text = SAMPLE.read_text()
    assert COMMENTED <= _model_keys(Params)
    for key in COMMENTED:
        assert key.rsplit(".", 1)[-1] in text


def test_sample_config_validates(tmp_path):
    config = _load()
    files = {}
    for name in ("light.svg", "dark.svg", "icon.svg", "og.png", "greeting.md", "c.js", "c.html"):
        files[name] = tmp_path / name
        files[name].write_text("x")

    config["logging"]["directory"] = str(tmp_path)
    config["logging"]["samples"]["path"] = str(tmp_path / "samples.jsonl")
    web = config["web"]
    web["logo"].update(
        light=str(files["light.svg"]), dark=str(files["dark.svg"]), favicon=str(files["icon.svg"])
    )
    web["opengraph"]["image"] = str(files["og.png"])
    web["greeting"]["file"] = str(files["greeting.md"])
    web["custom_javascript"] = str(files["c.js"])
    web["custom_html"] = str(files["c.html"])

    params = Params(**config)

    assert params.structured.ip_enrichment.enrich_traceroute is True
    assert params.web.dns_provider.url == "https://doh.example.com/dns-query"
    assert params.logging.http.authentication.mode == "api_key"


def test_docs_embed_the_sample_config():
    docs = SAMPLE.parents[1] / "docs/content/configuration/config/complete-config.mdx"
    section = docs.read_text().split("## Complete Example Configuration", 1)[1]
    block = section.split('```yaml filename="config.yaml"\n', 1)[1].split("```\n", 1)[0]
    assert block == SAMPLE.read_text(), "Copy .samples/sample_config.yaml into complete-config.mdx"
