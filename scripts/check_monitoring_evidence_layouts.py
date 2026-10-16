"""Fictional local Django responses; all browser network requests are intercepted.

Run only MonitoringEvidenceLayouts.test_browser with the test settings.
"""
import re
from pathlib import Path
from urllib.parse import urlparse

from django.contrib.staticfiles import finders
from django.template.loader import render_to_string
from django.test import RequestFactory
from playwright.sync_api import sync_playwright

from apps.tenant_apps.loans.tests.test_monitoring_presentation import MonitoringPresentationTests
from apps.tenant_apps.loans.selectors.dashboard_health import get_dashboard_health_summary
from apps.tenant_apps.loans.services.risk_snapshots import refresh_loan_risk_snapshot, RiskSnapshotRefreshError
from apps.tenant_apps.loans.web.operations import pawn_risk_portfolio
from apps.tenant_apps.loans.web.transaction_reviews import review_transactions


class MonitoringEvidenceLayouts(MonitoringPresentationTests):
    get_test_schema_name = classmethod(lambda cls: "monitoring-evidence-layouts")

    def test_browser(self):
        self.amend(valuation_basis="CALCULATED_METAL_VALUE")
        pages = {"live": self.detail().content.decode()}
        refresh_loan_risk_snapshot(self.loan.pk, as_of_date=self.today)
        legacy, _item = self.legacy_loan()
        pages["independent"] = self.detail(legacy).content.decode()
        try:
            refresh_loan_risk_snapshot(legacy.pk, as_of_date=self.today)
        except RiskSnapshotRefreshError:
            pass
        request = RequestFactory().get("/")
        request.user, request.workspace = self.actor, self.tenant
        pages["portfolio"] = pawn_risk_portfolio(request).content.decode()
        pages["review"] = review_transactions(request, self.loan.pk).content.decode()
        health = get_dashboard_health_summary(workspace=self.tenant)
        fragment = render_to_string("company/_financial_health.html", dict(workspace=self.tenant,
            business_overview={"health": health}, can_manage_health=True))
        pages["dashboard"] = ('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            '<link rel="stylesheet" href="https://layout.test/bootstrap.min.css"></head>'
            '<body><main class="container py-4">' + fragment + '</main></body></html>')
        assets = {}
        for html in pages.values():
            for asset in re.findall(r'["\'](/static/[^"\']+)', html):
                found = finders.find(asset.removeprefix("/static/"))
                if found:
                    assets[asset] = Path(found)
        cache = Path("outputs/loan-detail-mockups")
        bootstrap = {name: cache / name for name in ("bootstrap.min.css", "bootstrap.bundle.min.js")}
        self.assertTrue(all(path.is_file() for path in bootstrap.values()))
        output = Path("outputs/loan-boundary-ls05")
        output.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page()

            def respond(route):
                url = urlparse(route.request.url)
                name = url.path.rsplit("/", 1)[-1]
                if url.hostname == "layout.test" and name in pages:
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
                    page.goto("https://layout.test/" + state)
                    if state == "independent":
                        page.locator('[data-loan-tab="money"]').click()
                    if state == "live":
                        page.locator("[data-monitoring-evidence] > summary").click()
                    page.locator('details[data-loan-block="money"]').evaluate_all("rows => rows.forEach(e => e.open = true)")
                    self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), width)
                    expected = {"live": "Live calculation shown", "independent": "Independent current collateral observation",
                        "portfolio": "Loan health", "review": "Current recording practice", "dashboard": "Independent completeness checks"}
                    if state == "dashboard":
                        self.assertTrue(page.get_by_label(expected[state]).is_visible())
                        self.assertGreater(page.get_by_text("₹", exact=False).count(), 0)
                    else:
                        page.screenshot(path=str(output / f"{state}-{width}.png"), full_page=True)
                        self.assertTrue(page.get_by_text(expected[state], exact=False).first.is_visible(), f"{state} at {width}")
                    if state == "live":
                        self.assertTrue(page.locator("[data-monitoring-evidence]").get_by_text("UNASSESSED", exact=True).is_visible())
                    page.screenshot(path=str(output / f"{state}-{width}.png"), full_page=True)
            browser.close()
