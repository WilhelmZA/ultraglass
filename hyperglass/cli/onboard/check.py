"""Report effective feature configuration and actionable settings."""

# Standard Library
from pathlib import Path

# Third Party
from redis import Redis

# Project
from hyperglass.settings import Settings
from hyperglass.constants import SUPPORTED_STRUCTURED_OUTPUT


def cache_available() -> bool:
    """Check the configured RPKI cache without writing anything."""
    try:
        with Redis.from_url(
            str(Settings.redis_dsn), socket_connect_timeout=2, socket_timeout=2
        ) as client:
            return bool(client.ping())
    except Exception:
        return False


def font_status(ui: Path) -> tuple[str, str]:
    """Inspect the served build rather than inferring font hosting from configuration."""
    index = ui / "index.html"
    if not index.exists():
        return "unknown", "No built UI found; run hyperglass build-ui"
    html = index.read_text(encoding="utf-8")
    if "fonts.googleapis.com" in html or "fonts.gstatic.com" in html:
        return "off", "Run hyperglass build-ui with access to Google Fonts"
    if all((ui / "fonts" / f"{kind}.css").is_file() for kind in ("body", "mono")):
        return "pass", "Fonts are served by this installation"
    return "unknown", "The built UI does not contain the expected font stylesheets"


def check_config(state) -> list[dict]:
    """Check model defaults, overrides and device capabilities without changing files."""
    rows = []

    def add(feature, enabled, current, suggestion):
        rows.append(
            {
                "feature": feature,
                "status": "pass" if enabled else "off",
                "current": current,
                "suggestion": "" if enabled else suggestion,
            }
        )

    params = state.params
    structured = params.structured
    for kind in ("bgp_route", "traceroute"):
        enabled = getattr(structured, f"enable_for_{kind}") is not False
        add(f"Structured {kind}", enabled, enabled, f"structured.enable_for_{kind}: true")
    rpki = structured.rpki
    add("External RPKI", rpki.mode == "external", rpki.mode, "structured.rpki.mode: external")
    add("RPKI backend", True, rpki.backend, "")
    available = cache_available()
    add(
        "RPKI cache",
        available,
        "reachable" if available else "unreachable",
        "Set HYPERGLASS_REDIS_DSN to a reachable Redis database",
    )
    for feature in ("enrich_traceroute", "enrich_bgproute"):
        enabled = getattr(structured.ip_enrichment, feature)
        add(feature, enabled, enabled, f"structured.ip_enrichment.{feature}: true")
    add(
        "Server DNS",
        params.web.dns_provider.name == "server",
        params.web.dns_provider.name,
        "web.dns_provider.name: server",
    )
    add("My IP", params.web.my_ip != "off", params.web.my_ip, "web.my_ip: server")
    status, detail = font_status(Settings.static_path / "ui")
    rows.append(
        {
            "feature": "Self-hosted fonts",
            "status": status,
            "current": detail,
            "suggestion": detail if status != "pass" else "",
        }
    )
    for device in state.devices:
        if device.platform in SUPPORTED_STRUCTURED_OUTPUT:
            add(
                f"{device.id}: structured output",
                bool(device.structured_output),
                bool(device.structured_output),
                f"devices[{device.id}].structured_output: true",
            )
        versioned = any(
            rule.fallback_os_version and not (device.vrf and rule.vrf_commands)
            for directive in device.directives
            for rule in directive.rules
        )
        if versioned:
            add(
                f"{device.id}: OS version",
                bool(device.os_version),
                device.os_version,
                f"devices[{device.id}].os_version: '<installed version>'",
            )
    return rows
