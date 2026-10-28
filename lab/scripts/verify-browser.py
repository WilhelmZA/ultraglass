#!/usr/bin/env python3
# ruff: noqa: S101 -- This script is an integration test.
"""Verify mixed-vendor selection through a real browser (#23).

Install Playwright and Chromium before running this optional lab check.
"""

import argparse
import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright, expect


def verify_response(page, response):
    """Check the API result and its rendered device panel."""
    body = response["body"]
    assert response["status"] in (200, 201) and body["level"] == "success", response
    output = body["output"]
    assert (
        (output.get("routes") or output.get("hops")) if isinstance(output, dict) else output.strip()
    )
    location = response["request"]["queryLocation"]
    item = page.locator(".chakra-accordion__item").filter(
        has=page.get_by_text(location, exact=True)
    )
    toggle = item.locator(".chakra-accordion__button")
    if toggle.get_attribute("aria-expanded") != "true":
        toggle.click()
    panel = item.locator(".chakra-accordion__panel")
    expect(panel).to_be_visible()
    if isinstance(output, dict):
        expect(panel.locator("table")).to_be_visible(timeout=15000)
        rows = output.get("routes", output.get("hops"))
        value = rows[0].get("prefix", rows[0].get("ip_address"))
        if value:
            expect(panel).to_contain_text(value)
    else:
        expect(panel).to_contain_text(output.strip().splitlines()[0])


def main():
    """Submit each shared query through the UI and retain response evidence."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8002")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("devices", nargs="+")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    results = []
    devices = list(dict.fromkeys(["lab-mikrotik", *args.devices]))
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for kind, target in [
            ("BGP Route", "1.1.1.1"),
            ("BGP AS Path", "_13335$"),
            ("BGP Community", "37195:302"),
            ("Ping", "1.1.1.1"),
            ("Traceroute", "1.1.1.1"),
        ]:
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            responses = []
            errors = []
            page.on("pageerror", lambda error, errors=errors: errors.append(str(error)))

            def record(response, responses=responses):
                if response.url.endswith("/api/query"):
                    responses.append(
                        {
                            "request": response.request.post_data_json,
                            "status": response.status,
                            "body": response.json(),
                        }
                    )

            page.on("response", record)
            page.goto(args.url, wait_until="networkidle")
            for name in devices:
                box = page.get_by_role("combobox").first
                box.fill(name)
                box.press("Enter")
            box = page.get_by_role("combobox").nth(1)
            box.fill(kind)
            box.press("Enter")
            page.locator('[name="queryTargetDisplay"]').fill(target)
            page.get_by_role("button", name="Submit Query", exact=True).click()
            deadline = time.monotonic() + 330
            while len(responses) < len(devices) and time.monotonic() < deadline:
                page.wait_for_timeout(250)
            expect(page.get_by_text("Loading...", exact=True)).to_have_count(0, timeout=330000)
            page.wait_for_load_state("networkidle")
            assert len(responses) == len(devices), (kind, responses)
            assert {r["request"]["queryLocation"] for r in responses} == set(devices)
            for response in responses:
                verify_response(page, response)
            assert not errors, errors
            text = page.locator("body").inner_text()
            name = kind.lower().replace(" ", "-")
            # Full-table text responses can exceed Chromium's image-height limit.
            page.screenshot(path=str(args.output / f"{name}.png"))
            results.append(
                {"devices": devices, "kind": kind, "responses": responses, "page_text": text}
            )
            (args.output / "results.json").write_text(json.dumps(results, indent=2))
            print(f"PASS {len(devices)} devices: {kind}", flush=True)
            page.close()
        browser.close()


if __name__ == "__main__":
    main()
