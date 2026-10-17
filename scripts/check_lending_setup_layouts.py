"""Fictional local lending setup pages, rendered in offline Chromium."""

import mimetypes
import json
from pathlib import Path
from urllib.parse import urlsplit

from django.contrib.staticfiles import finders
from django.urls import reverse
from playwright.sync_api import sync_playwright
from apps.tenant_apps.loans.tests.test_lending_setup import LendingSetupTests
from scripts.browser_fixtures import bootstrap_assets


class LendingSetupLayouts(LendingSetupTests):
    def test_browser(self):
        url = reverse("workspace_loans:pawn_economics_setup", args=[self.tenant.slug])
        pages = {
            "overview": self.client.get(url),
            "register": self.client.get(url, {"series": self.series.pk}),
        }
        for kind, values in (
            ("rates", {"gold_monthly_interest_rate": "1.1"}),
            ("terms", {"default_tenure_months": "6"}),
            ("entry", {"purpose": "DIRECT"}),
        ):
            data = {
                "action": kind,
                f"{kind}-series": self.series.pk,
                f"{kind}-effective_from": "2026-10-17",
            }
            data.update({f"{kind}-{name}": value for name, value in values.items()})
            response = self.client.post(url, data)
            self.assertContains(response, "data-economic-policy-review")
            pages[kind + "-review"] = response
        pages["invalid-change"] = self.client.post(
            url, {"action": "terms", "terms-effective_from": "2026-10-17"}
        )
        for response in pages.values():
            self.assertEqual(response.status_code, 200)
        output = Path("outputs/lending-setup-20261017")
        output.mkdir(parents=True, exist_ok=True)
        assets = bootstrap_assets()
        errors, checks = [], []
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page()
            page.on("pageerror", lambda exc: errors.append(str(exc)))

            def serve(route):
                target = urlsplit(route.request.url)
                name = target.path.rsplit("/", 1)[-1]
                if target.hostname == "lending-layout.test" and name in pages:
                    return route.fulfill(
                        body=pages[name].content, content_type="text/html"
                    )
                if target.path.startswith("/static/"):
                    found = finders.find(target.path.removeprefix("/static/"))
                    if found:
                        return route.fulfill(
                            path=found, content_type=mimetypes.guess_type(found)[0]
                        )
                if name in assets:
                    return route.fulfill(
                        path=str(assets[name]),
                        headers={"Access-Control-Allow-Origin": "*"},
                    )
                route.abort()

            page.route("**/*", serve)
            for width in (1440, 390):
                page.set_viewport_size({"width": width, "height": 960})
                for name in pages:
                    page.goto("https://lending-layout.test/" + name)
                    if name == "register":
                        page.locator("#change-rates > summary").click()
                        self.assertEqual(
                            page.locator('[name="rates-series"]').input_value(),
                            str(self.series.pk),
                        )
                        self.assertEqual(
                            page.locator('[name="rates-license"]').input_value(),
                            str(self.license.pk),
                        )
                    elif name.endswith("-review"):
                        self.assertTrue(
                            page.locator("[data-economic-policy-review]").is_visible()
                        )
                        self.assertFalse(
                            page.locator(
                                '[data-economic-policy-review] input[name="economic_acknowledged"]'
                            ).is_checked()
                        )
                    page.screenshot(
                        path=str(output / f"{name}-{width}.png"), full_page=True
                    )
                    self.assertLessEqual(
                        page.evaluate("document.documentElement.scrollWidth"),
                        width + 1,
                        name,
                    )
                    checks.append(dict(page=name, width=width))
            browser.close()
        self.assertEqual(errors, [])
        (output / "checks.json").write_text(
            json.dumps(dict(checks=checks, errors=errors), indent=2), encoding="utf-8"
        )
