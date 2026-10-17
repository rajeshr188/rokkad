"""Synthetic Django/browser checks; every browser request is intercepted offline.

Run OriginationLayouts.test_browser with django_project.settings.test.
"""

import json
from pathlib import Path
import re
from urllib.parse import urlparse

from django.contrib.staticfiles import finders
from django.urls import reverse
from playwright.sync_api import sync_playwright

from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.tests.test_draft_replacement import DraftReplacementTests
from scripts.browser_fixtures import bootstrap_assets


class OriginationLayouts(DraftReplacementTests):
    @classmethod
    def get_test_schema_name(cls):
        return "origination-simplification-layouts"

    def test_browser(self):
        loan, _, values = self.replacement()
        pages = {}

        def retain(name, response):
            self.assertEqual(response.status_code, 200)
            pages[name] = response.content.decode()
            return response

        review_path = reverse(
            "workspace_loans:pawn_loan_review_disburse",
            args=[self.tenant.slug, loan.pk],
        )
        review = retain("loan-review", self.client.get(review_path))
        setup_path = reverse(
            "workspace_loans:pawn_economics_setup", args=[self.tenant.slug]
        )
        form = self.client.get(setup_path).context["configuration_form"]
        payload = {"action": "configuration"}
        for name in form.fields:
            value = form[name].value()
            payload[form[name].html_name] = (
                ""
                if value is None or value is False
                else "on" if value is True else value
            )
        payload.update(
            {
                "configuration-license": self.license.pk,
                "configuration-effective_from": loan.loan_date.isoformat(),
                "configuration-valuation_method": "LATEST_APPRAISAL",
                "configuration-maximum_ltv_ratio": ".8",
                "configuration-partial_month_method": "STARTED_WEEKS",
                "configuration-gold_monthly_interest_rate": "2",
                "configuration-silver_monthly_interest_rate": "4",
            }
        )
        policy = retain("configuration-review", self.client.post(setup_path, payload))
        self.assertFalse(policy.context["configuration_form"].errors)
        self.assertIsNotNone(policy.context["configuration_review"])
        payload.update(
            economic_confirm="1",
            economic_acknowledged="on",
            economic_review_token=policy.context["configuration_review_token"],
        )
        self.assertEqual(self.client.post(setup_path, payload).status_code, 302)
        retain("changed-loan-review", self.confirm(review_path, review))

        path = reverse(
            "workspace_loans:pawn_loan_replace_draft", args=[self.tenant.slug, loan.pk]
        )
        retain("replacement-form", self.client.get(path))
        payload = dict(
            series=values["series_id"],
            product_version=values["product_version_id"],
            **{
                key: values[key]
                for key in ("loan_date", "tenure_months", "reason", "request_key")
            },
            action="preview",
        )
        proposed = retain("replacement-review", self.client.post(path, payload))
        self.assertContains(proposed, "How this agreement is calculated")
        payload.update(
            action="confirm",
            confirmed="on",
            review_token=proposed.context["form"]["review_token"].value(),
        )
        self.assertEqual(self.client.post(path, payload).status_code, 302)
        replacement = m.PawnLoan.objects.exclude(pk=loan.pk).get()
        for label, subject in (
            ("cancelled-draft", loan),
            ("replacement-draft", replacement),
        ):
            retain(
                label,
                self.client.get(
                    reverse(
                        "workspace_loans:pawn_loan_detail",
                        args=[self.tenant.slug, subject.pk],
                    )
                ),
            )
        hold = retain(
            "correction-guidance",
            self.client.get(
                reverse(
                    "workspace_loans:pawn_collateral_correct",
                    args=[
                        self.tenant.slug,
                        replacement.pk,
                        replacement.collateral_items.get().pk,
                    ],
                )
            ),
        )
        self.assertContains(hold, "Correct the preparation draft")
        self.assertNotContains(hold, "Review collateral correction</button>")
        borrower_hold = retain(
            "borrower-correction-hold",
            self.client.get(
                reverse(
                    "workspace_loans:pawn_loan_correct_borrower",
                    args=[self.tenant.slug, replacement.pk],
                )
            ),
        )
        self.assertContains(borrower_hold, "Correct the preparation draft")
        self.assertNotContains(borrower_hold, 'value="preview"')
        self.capture(pages)

    def capture(self, pages):
        assets = {}
        for html in pages.values():
            for asset in re.findall(r"""["'](/static/[^"']+)""", html):
                found = finders.find(asset.removeprefix("/static/"))
                if found:
                    assets[asset] = Path(found)
        bootstrap = bootstrap_assets()
        output = Path("outputs/origination-simplification-20261017")
        output.mkdir(parents=True, exist_ok=True)
        checks, errors = [], []
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))

            def respond(route):
                url = urlparse(route.request.url)
                name = url.path.rsplit("/", 1)[-1]
                if url.hostname == "origination-layout.test" and name in pages:
                    route.fulfill(body=pages[name], content_type="text/html")
                elif url.path in assets:
                    route.fulfill(path=str(assets[url.path]))
                elif name in bootstrap:
                    route.fulfill(
                        path=str(bootstrap[name]),
                        headers={"Access-Control-Allow-Origin": "*"},
                    )
                else:
                    route.abort()

            page.route("**/*", respond)
            for width, height in ((1440, 1000), (390, 844)):
                page.set_viewport_size({"width": width, "height": height})
                for name in pages:
                    page.goto("https://origination-layout.test/" + name)
                    page.locator(
                        "[data-economic-policy-review] details, [data-origination-agreement] details"
                    ).evaluate_all("rows => rows.forEach(row => row.open = true)")
                    self.assertLessEqual(
                        page.evaluate("document.documentElement.scrollWidth"),
                        width,
                        name,
                    )
                    page.screenshot(
                        path=str(output / f"{name}-{width}.png"), full_page=True
                    )
                    checks.append(dict(page=name, width=width, overflow=False))
            browser.close()
        (output / "checks.json").write_text(
            json.dumps(dict(checks=checks, errors=errors), indent=2), encoding="utf-8"
        )
        self.assertEqual(errors, [])
