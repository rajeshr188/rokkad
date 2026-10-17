"""Fictional unnumbered/issued loan pages and approval print gates, rendered offline."""

import json
import mimetypes
from pathlib import Path
from urllib.parse import urlsplit

from django.contrib.staticfiles import finders
from django.urls import reverse
from playwright.sync_api import sync_playwright

from apps.tenant_apps.loans.tests.test_delayed_numbering import DelayedNumberingTests
from scripts.browser_fixtures import bootstrap_assets


class NumberingLayouts(DelayedNumberingTests):
    def test_browser(self):
        loan, review_path, _, review = self.start_review()
        detail = reverse(
            "workspace_loans:pawn_loan_detail", args=[self.tenant.slug, loan.pk]
        )
        pages = {
            "new": self.client.get(
                reverse("workspace_loans:pawn_loan_create", args=[self.tenant.slug])
            ),
            "draft": self.client.get(detail),
            "edit": self.client.get(
                reverse(
                    "workspace_loans:pawn_loan_update", args=[self.tenant.slug, loan.pk]
                )
            ),
            "review": review,
            "paper": self.client.get(
                reverse("workspace_loans:pawn_loan_create", args=[self.tenant.slug]),
                {"entry": "paper", "series": self.series.pk},
            ),
        }
        self.assertFalse(pages["edit"].context["form"].fields["series"].disabled)
        output = Path("outputs/approval-numbering-20261017")
        output.mkdir(parents=True, exist_ok=True)
        self.assertNotContains(pages["draft"], 'id="print-loan-ticket-title"')
        self.assertNotContains(pages["draft"], "Print draft preview")
        self.assertEqual(self.confirm(review_path, review).status_code, 302)
        loan.refresh_from_db()
        pages["issued"] = self.client.get(detail)
        self.assertContains(pages["issued"], loan.loan_number)
        self.assertContains(pages["issued"], 'id="print-loan-ticket-title"')
        self.assertNotContains(pages["issued"], "Print draft preview")
        for response in pages.values():
            self.assertEqual(response.status_code, 200)
        assets = bootstrap_assets()
        errors, checks = [], []
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page()
            page.on("pageerror", lambda exc: errors.append(str(exc)))

            def serve(route):
                target = urlsplit(route.request.url)
                name = target.path.rsplit("/", 1)[-1]
                if target.hostname == "numbering-layout.test" and name in pages:
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
                    page.goto("https://numbering-layout.test/" + name)
                    if name == "draft":
                        self.assertTrue(
                            page.locator("[data-draft-numbering]").is_visible()
                        )
                        self.assertIn(
                            f"Draft #{loan.pk}",
                            page.locator("h1:visible").first.inner_text(),
                        )
                    if name == "edit":
                        self.assertTrue(page.locator('[name="series"]').is_enabled())
                        self.assertTrue(
                            page.locator('[name="product_version"]').is_enabled()
                        )
                    self.assertLessEqual(
                        page.evaluate("document.documentElement.scrollWidth"),
                        width + 1,
                        name,
                    )
                    page.screenshot(
                        path=str(output / f"{name}-{width}.png"), full_page=True
                    )
                    checks.append(dict(page=name, width=width))
            browser.close()
        self.assertEqual(errors, [])
        (output / "checks.json").write_text(
            json.dumps(dict(checks=checks, errors=errors), indent=2), encoding="utf-8"
        )
