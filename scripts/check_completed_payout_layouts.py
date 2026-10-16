"""Browser checks against fictional Django responses; all network calls intercepted.

Run only CompletedPayoutLayouts.test_browser with django_project.settings.test.
"""
import re
from pathlib import Path
from urllib.parse import urlparse

from django.contrib.staticfiles import finders
from playwright.sync_api import sync_playwright

from scripts.browser_fixtures import bootstrap_assets

from apps.tenant_apps.loans.tests.test_completed_payout_review import CompletedFactReviewTests
from apps.tenant_apps.rates.services import withdraw_quote


class CompletedPayoutLayouts(CompletedFactReviewTests):
    @classmethod
    def get_test_schema_name(cls):
        return "completed-payout-layout-ls02"

    def test_browser(self):
        self.approve()
        withdraw_quote(workspace=self.tenant, actor=self.actor, quote_id=self.quote.pk,
            reason="Fictional withdrawn reference for review layout")
        facts = self.start()
        review = self.preview()
        pages = {"facts": facts.content.decode(), "review": review.content.decode()}
        assets = {}
        for html in pages.values():
            for asset in re.findall(r'["\'](/static/[^"\']+)', html):
                found = finders.find(asset.removeprefix("/static/"))
                if found:
                    assets[asset] = Path(found)
        bootstrap = bootstrap_assets()
        output = Path("outputs/loan-boundary-ls02")
        output.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page()

            def respond(route):
                url = urlparse(route.request.url)
                name = url.path.rsplit("/", 1)[-1]
                if url.hostname == "completed-layout.test" and name in pages:
                    route.fulfill(body=pages[name], content_type="text/html")
                elif url.path in assets:
                    route.fulfill(path=str(assets[url.path]))
                elif name in bootstrap:
                    route.fulfill(path=str(bootstrap[name]), headers={"Access-Control-Allow-Origin": "*"})
                else:
                    route.abort()

            page.route("**/*", respond)
            for width, height in ((1365, 900), (390, 844)):
                page.set_viewport_size({"width": width, "height": height})
                for state in pages:
                    page.goto("https://completed-layout.test/" + state)
                    root = page.locator("[data-completed-payout]")
                    root.wait_for()
                    self.assertEqual(page.locator(".card").first.evaluate("e => getComputedStyle(e).display"), "flex")
                    self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), width)
                    self.assertTrue(root.get_by_text("Retained approval evidence", exact=True).is_visible())
                    self.assertEqual(root.locator('[aria-current="step"]').count(), 1)
                    self.assertEqual(root.locator('textarea[name="reason"]').count(), 0 if state == "review" else 1)
                    if state == "review":
                        self.assertTrue(root.locator('input[name="confirm_review"]').evaluate("e => e.required"))
                        self.assertTrue(root.get_by_role("button", name="Back to facts").is_visible())
                    page.screenshot(path=str(output / f"{state}-{width}.png"), full_page=True)
            browser.close()
