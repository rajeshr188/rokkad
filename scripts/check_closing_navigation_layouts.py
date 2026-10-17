"""Offline fictional UI checks: run ClosingLayouts.test_browser with .test settings."""

import json
import mimetypes
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from django.contrib.staticfiles import finders
from django.urls import reverse
from playwright.sync_api import sync_playwright

from apps.tenant_apps.loans.tests.test_closing_workflow import ClosingWorkflowTests
from apps.tenant_apps.party.models import PartyRelationship
from scripts.browser_fixtures import bootstrap_assets


class ClosingLayouts(ClosingWorkflowTests):
    def test_browser(self):
        pages = {}

        def retain(name, response):
            self.assertEqual(response.status_code, 200)
            pages[name] = response.content
            return response

        ids = [loan.pk for loan in self.loans]
        retain("start", self.client.get(self.entry()))
        for name, purpose, selected in (
            ("current-one", "CURRENT", ids[:1]),
            ("current-many", "CURRENT", ids),
            ("completed-date", "PAPER", ids),
        ):
            retain(
                name,
                self.client.get(self.entry(), {"purpose": purpose, "loans": selected}),
            )
        for name, route in (
            ("releases", "pawn_release_list"),
            ("groups", "release_batch_list"),
            ("help", "paper_closure_guide"),
            ("collateral", "pawn_collateral_list"),
        ):
            retain(
                name,
                self.client.get(
                    reverse("workspace_loans:" + route, args=[self.tenant.slug])
                ),
            )
        detail = reverse(
            "workspace_party:party_detail",
            args=[self.tenant.slug, self.loans[0].borrower_id],
        )
        relationship = retain(
            "relationships", self.client.get(detail, {"tab": "relationships"})
        )
        field = relationship.context["relationship_form"].fields["to_party"]
        party_url, party_token = field.widget.get_url(), field.widget.field_id
        relation = PartyRelationship.objects.create(
            from_party=self.loans[0].borrower,
            to_party=self.loans[1].borrower,
            relationship_type="FAMILY",
        )
        retain(
            "relationships-edit",
            self.client.get(
                detail, {"tab": "relationships", "edit_relationship": relation.pk}
            ),
        )
        loan_url = reverse(
            "workspace_loans:release_batch_search", args=[self.tenant.slug]
        )
        loan_results = self.client.get(loan_url, {"q": "Borrower"}).json()
        party_results = self.client.get(
            party_url, {"field_id": party_token, "term": "Borrower"}
        ).json()
        bootstrap = bootstrap_assets()
        output = Path("outputs/closing-navigation-20261017")
        output.mkdir(parents=True, exist_ok=True)
        errors, requests, checks = [], [], []
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))

            def serve(route):
                url = urlsplit(route.request.url)
                name = url.path.rsplit("/", 1)[-1]
                if url.hostname == "closing-layout.test" and name in pages:
                    return route.fulfill(body=pages[name], content_type="text/html")
                if url.path in (loan_url, party_url):
                    query = parse_qs(url.query)
                    term = query.get("q" if url.path == loan_url else "term", [""])[0]
                    self.assertEqual(term, "Borrower")
                    if url.path == party_url:
                        self.assertEqual(query["field_id"], [party_token])
                    requests.append(url.path)
                    return route.fulfill(
                        json=loan_results if url.path == loan_url else party_results
                    )
                if url.path.startswith("/static/"):
                    found = finders.find(url.path.removeprefix("/static/"))
                    if found:
                        return route.fulfill(
                            path=found, content_type=mimetypes.guess_type(found)[0]
                        )
                if name in bootstrap:
                    return route.fulfill(
                        path=str(bootstrap[name]),
                        headers={"Access-Control-Allow-Origin": "*"},
                    )
                route.abort()

            page.route("**/*", serve)
            for width in (1440, 390):
                page.set_viewport_size({"width": width, "height": 960})
                for name in pages:
                    page.goto("https://closing-layout.test/" + name)
                    if name == "start":
                        page.locator("#closing-purpose").select_option("CURRENT")
                        search = page.locator(
                            "#closing-selection .select2-search__field"
                        )
                        search.fill("Borrower")
                        option = page.locator(
                            ".select2-results__option[aria-selected]"
                        ).filter(has_text=self.loans[0].loan_number)
                        option.wait_for(state="visible")
                        page.screenshot(
                            path=str(output / f"loan-search-{width}.png"),
                            full_page=True,
                        )
                        option.click()
                        self.assertEqual(
                            page.locator("#closing-loans").input_value(), str(ids[0])
                        )
                        search.fill("Borrower")
                        page.locator(".select2-results__option[aria-selected]").filter(
                            has_text=self.loans[1].loan_number
                        ).click()
                        self.assertEqual(
                            page.locator("#closing-loans option:checked").count(), 2
                        )
                        page.locator("#closing-purpose").select_option("PAPER")
                        self.assertEqual(
                            page.locator("#closing-loans option:checked").count(), 2
                        )
                        page.locator(
                            "#closing-selection .select2-selection__choice__remove"
                        ).first.click()
                        self.assertEqual(
                            page.locator("#closing-loans option:checked").count(), 1
                        )
                    elif name.startswith("current"):
                        page.locator("#closing-purpose").select_option("PAPER")
                        for button in page.locator(
                            'form[data-closing-review] button[type="submit"], form[data-closing-review] button:not([type])'
                        ).all():
                            self.assertTrue(button.is_disabled())
                    elif name == "relationships":
                        page.locator(
                            "#id_to_party + .select2 .select2-selection"
                        ).click()
                        page.locator(
                            ".select2-search--dropdown .select2-search__field"
                        ).fill("Borrower")
                        option = page.locator(
                            ".select2-results__option[aria-selected]"
                        ).filter(has_text="Borrower 1")
                        option.wait_for(state="visible")
                        page.screenshot(
                            path=str(output / f"party-search-{width}.png"),
                            full_page=True,
                        )
                        option.click()
                        self.assertEqual(
                            page.locator("#id_to_party").input_value(),
                            str(self.loans[1].borrower_id),
                        )
                    elif name == "relationships-edit":
                        self.assertEqual(
                            page.locator("#id_to_party").input_value(),
                            str(self.loans[1].borrower_id),
                        )
                    if name in ("releases", "groups", "help"):
                        links = page.locator(
                            'nav[aria-label="Workspace navigation"] a'
                        ).filter(has_text="Releases")
                        self.assertEqual(
                            links.count(), 2
                        )  # Shared desktop/mobile navigation.
                        self.assertTrue(
                            all(
                                "active" in (link.get_attribute("class") or "")
                                for link in links.all()
                            )
                        )
                    page.screenshot(
                        path=str(output / f"{name}-{width}.png"), full_page=True
                    )
                    self.assertLessEqual(
                        page.evaluate("document.documentElement.scrollWidth"),
                        width + 1,
                        name,
                    )
                    checks.append({"page": name, "width": width})
            browser.close()
        self.assertEqual(errors, [])
        self.assertGreaterEqual(requests.count(loan_url), 2)
        self.assertEqual(requests.count(party_url), 2)
        (output / "checks.json").write_text(
            json.dumps(
                {"checks": checks, "errors": errors, "search_requests": len(requests)},
                indent=2,
            ),
            encoding="utf-8",
        )
