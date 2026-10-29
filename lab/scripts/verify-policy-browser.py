#!/usr/bin/env python3
# ruff: noqa: S101 -- This script is an integration test.
"""Check how AS-path and community results render in the browser (#22).

Run against an instance configured with `structured.communities.mode: name` (mapping
65000:777 to "Lab community"), external RPKI and BGP route enrichment. The core must
advertise the lab test routes described in verify-policy-matrix.py.
"""

import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright, expect

PREFIX = "1.0.0.0/24"
QUERIES = (("BGP AS Path", "_64999_"), ("BGP Community", "65000:777"))
# Device output that carries communities for each query; see verify-policy-matrix.py.
NAMED = {
    "BGP AS Path": {"lab-bird", "lab-openbgpd", "lab-mikrotik", "lab-junos"},
    "BGP Community": {
        "lab-arista",
        "lab-frr",
        "lab-huawei",
        "lab-bird",
        "lab-openbgpd",
        "lab-vyos",
        "lab-mikrotik",
        "lab-junos",
    },
}
NO_PATH = {"BGP Community": {"lab-huawei"}}


def column(panel, name):
    """Return the index of a table column by its header text."""
    headers = panel.locator("thead th").all_inner_texts()
    return next(i for i, text in enumerate(headers) if text.strip() == name)


def check_panel(page, device, kind):
    """Open a device panel and check the test route row."""
    item = page.locator(".chakra-accordion__item").filter(has=page.get_by_text(device, exact=True))
    toggle = item.locator(".chakra-accordion__button")
    if toggle.get_attribute("aria-expanded") != "true":
        toggle.click()
    panel = item.locator(".chakra-accordion__panel")
    expect(panel).to_be_visible()
    expect(panel.locator("table")).to_be_visible(timeout=15000)
    row = panel.locator("tbody tr").filter(has_text=PREFIX).first
    expect(row).to_be_visible()
    cells = row.locator("td")
    result = {"device": device, "query": kind, "render": "table"}

    if device not in NO_PATH.get(kind, set()):
        row.get_by_role("link", name="13335", exact=True).hover()
        tooltip = page.get_by_role("tooltip").filter(has_text="13335 - ")
        # Async enrichment can still be pending; the open tooltip updates in place (#86).
        expect(tooltip).to_be_visible(timeout=60000)
        result["asn_tooltip"] = tooltip.inner_text()
        page.mouse.move(0, 0)
        expect(page.get_by_role("tooltip")).to_have_count(0, timeout=10000)
        cells.nth(column(panel, "RPKI State")).locator("div").first.hover()
        rpki = page.get_by_role("tooltip").filter(has_text="Valid")
        expect(rpki).to_be_visible(timeout=10000)
        result["rpki_tooltip"] = rpki.inner_text()
        page.mouse.move(0, 0)
        expect(page.get_by_role("tooltip")).to_have_count(0, timeout=10000)

    if device in NAMED[kind]:
        cells.nth(column(panel, "Communities")).locator("button").first.click()
        menu = panel.get_by_role("menu").filter(has_text="65000:777 - Lab community")
        expect(menu).to_be_visible(timeout=10000)
        result["communities"] = menu.inner_text().splitlines()
        page.keyboard.press("Escape")
    return result


def main():
    """Submit both queries to every device through the UI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8005")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("devices", nargs="+")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    results = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for kind, target in QUERIES:
            page = browser.new_page(viewport={"width": 1600, "height": 1000})
            errors = []
            page.on("pageerror", lambda error, errors=errors: errors.append(str(error)))
            page.goto(args.url, wait_until="networkidle")
            for name in args.devices:
                box = page.get_by_role("combobox").first
                box.fill(name)
                box.press("Enter")
            box = page.get_by_role("combobox").nth(1)
            box.fill(kind)
            box.press("Enter")
            page.locator('[name="queryTargetDisplay"]').fill(target)
            page.get_by_role("button", name="Submit Query", exact=True).click()
            expect(page.get_by_text("Loading...", exact=True)).to_have_count(0, timeout=330000)
            page.wait_for_load_state("networkidle")
            for device in args.devices:
                result = check_panel(page, device, kind)
                results.append(result)
                print(json.dumps(result), flush=True)
            assert not errors, errors
            page.screenshot(path=str(args.output / f"{kind.lower().replace(' ', '-')}.png"))
            page.close()
        browser.close()
    (args.output / "results.json").write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
