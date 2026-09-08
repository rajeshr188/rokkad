"""Opt-in Chromium acceptance; run this class explicitly, never against live data."""

import json
import gc
import traceback
import os
from io import BytesIO
from pathlib import Path
from tempfile import gettempdir

from PIL import Image
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connection
from django.db.backends.signals import connection_created
from django.test import override_settings
from django.urls import reverse

from django_project.test_mvp_operator_journey import MVPOperatorJourneyTests


@override_settings(
    BILLING_ALLOW_TRIAL_START=True,
    ALLOWED_HOSTS=["testserver", "localhost"],
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)
class BrowserAcceptanceTests(StaticLiveServerTestCase):
    _drop_runtime_role = MVPOperatorJourneyTests._drop_runtime_role
    _get = MVPOperatorJourneyTests._get
    _post = MVPOperatorJourneyTests._post
    _workspace = MVPOperatorJourneyTests._workspace
    _loan_url = MVPOperatorJourneyTests._loan_url
    _setup_loans = MVPOperatorJourneyTests._setup_loans

    def setUp(self):
        MVPOperatorJourneyTests.setUp(self)
        self.addCleanup(gc.collect)
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_user")
            role = connection.ops.quote_name(cursor.fetchone()[0])

        def restrict_browser_connection(sender, connection, **kwargs):
            with connection.cursor() as cursor:
                cursor.execute(f"SET ROLE {role}")

        connection_created.connect(restrict_browser_connection, weak=False)
        self.addCleanup(connection_created.disconnect, restrict_browser_connection)
        self.workspace = self._workspace("Browser Counter")
        self._setup_loans()

    def test_administration_screens(self):
        from playwright.sync_api import sync_playwright, expect

        artifacts = Path(gettempdir()) / "rokkad-admin-ux"
        artifacts.mkdir(exist_ok=True)
        routes = [
            ("workspace_slug_settings", True),
            ("workspace_slug_settings_team", True),
            ("workspace_slug_settings_invite", True),
            ("workspace_slug_settings_invitations", True),
            ("workspace_slug_settings_setup", True),
            ("workspace_slug_settings_preferences", True),
            ("workspace_slug_settings_modules", True),
            ("workspace_slug_settings_security", True),
            ("workspace_subscriptions:dashboard", True),
            ("workspace_subscriptions:plan-list", True),
            ("profile", False), ("account_settings", False),
            ("app_workspaces", False),
        ]
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                for width in (1440, 390):
                    context = browser.new_context(viewport={"width": width, "height": 1000})
                    context.add_cookies([{"name": "sessionid", "value": self.client.cookies["sessionid"].value, "url": self.live_server_url}])
                    try:
                        page = context.new_page()
                        errors = []
                        page.on("pageerror", lambda error: errors.append(str(error)))
                        for route, scoped in routes:
                            path = reverse(route, kwargs={"workspace_slug": self.workspace.slug} if scoped else {})
                            if route == "app_workspaces":
                                path += "?show_all=1"
                            response = page.goto(self.live_server_url + path)
                            self.assertEqual(response.status, 200, route)
                            page.wait_for_load_state("networkidle")
                            page.screenshot(path=str(artifacts / f"{width}-{route.replace(':', '-')}.png"), full_page=True)
                            self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), width + 1, route)
                        if width == 390:
                            page.get_by_role("button", name="Navigation", exact=True).click()
                            expect(page.locator("#mgmtOffcanvas")).to_be_visible()
                            expect(page.locator("#mgmtOffcanvas").get_by_role("link", name="Account Settings")).to_be_visible()
                        for suffix in ("setup/", "setup/economics/", "setup/products/"):
                            path = reverse("workspace_slug_loans_dispatch", kwargs={"workspace_slug": self.workspace.slug, "loans_path": suffix})
                            response = page.goto(self.live_server_url + path)
                            self.assertEqual(response.status, 200, suffix)
                            page.wait_for_load_state("networkidle")
                            expect(page.get_by_role("navigation", name="PawnLoan setup", exact=True)).to_be_visible()
                            page.screenshot(path=str(artifacts / f"{width}-{suffix.replace('/', '-')}.png"), full_page=True)
                            self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), width + 1, suffix)
                        self.assertEqual(errors, [])
                    finally:
                        context.close()
            finally:
                browser.close()

    def test_party_rates_notify_screens(self):
        from playwright.sync_api import sync_playwright, expect
        from apps.tenancy.context import workspace_context
        from apps.tenant_apps.notify_v2.models import NotificationBatch, NotificationEventType

        with workspace_context(self.workspace.pk):
            event = NotificationEventType.objects.create(
                workspace=self.workspace, key="ux_demo", name="Acceptance reminder",
            )
            batch = NotificationBatch.objects.create(event_type=event, name="Acceptance batch")
        artifacts = Path(gettempdir()) / "rokkad-apps-ux"
        artifacts.mkdir(exist_ok=True)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                for width in (1440, 390):
                    context = browser.new_context(viewport={"width": width, "height": 1000})
                    context.add_cookies([{
                        "name": "sessionid", "value": self.client.cookies["sessionid"].value,
                        "url": self.live_server_url,
                    }])
                    try:
                        page = context.new_page()
                        errors = []
                        page.on("pageerror", lambda error: errors.append(str(error)))

                        def visit(name, **kwargs):
                            path = reverse(name, kwargs={"workspace_slug": self.workspace.slug, **kwargs})
                            response = page.goto(self.live_server_url + path)
                            self.assertEqual(response.status, 200, path)
                            page.wait_for_load_state("networkidle")

                        def capture(name):
                            page.screenshot(path=str(artifacts / f"{width}-{name}.png"), full_page=True)
                            self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), width + 1, name)

                        visit("workspace_slug_party_create")
                        page.locator('[name="display_name"]').fill(f"UX Borrower {width}")
                        expect(page.locator('[data-entry-field="display_name"]')).to_have_text(f"UX Borrower {width}")
                        capture("party-entry")
                        page.locator('button[type="submit"]').last.click()
                        expect(page.locator("h1")).to_contain_text(f"UX Borrower {width}")
                        expect(page.locator("#party-photo-editor")).not_to_have_attribute("open", "")
                        page.locator('[data-bs-target="#loans"]').click()
                        expect(page.locator("#loans")).to_be_visible()
                        expect(page.locator("#loans")).to_have_class("tab-pane fade active show")
                        expect(page.locator("#loans")).to_have_css("opacity", "1")
                        page.locator('[data-bs-target="#kyc"]').click()
                        expect(page.locator("#kyc")).to_be_visible()
                        expect(page.locator("#kyc")).to_have_class("tab-pane fade active show")
                        expect(page.locator("#kyc")).to_have_css("opacity", "1")
                        capture("party-kyc")
                        visit("workspace_rates:ratesource_create")
                        page.locator('[name="name"]').fill(f"UX Source {width}")
                        page.locator('[name="location"]').fill("Chennai")
                        page.get_by_role("button", name="Save Source", exact=True).click()
                        page.wait_for_load_state("networkidle")
                        visit("workspace_rates:rate_create")
                        page.locator('[name="rate_source"]').select_option(label=f"UX Source {width}")
                        page.locator('[name="buying_rate"]').fill("7000")
                        page.locator('[name="selling_rate"]').fill("7100")
                        expect(page.locator('[data-entry-field="buying_rate"]')).to_have_text("7000")
                        capture("rate-entry")
                        page.get_by_role("button", name="Save Rate", exact=True).click()
                        expect(page.locator("h1")).to_contain_text("Gold")
                        capture("rate-detail")
                        for route, label in (
                            ("workspace_rates:rate_list", "rates"),
                            ("workspace_rates:ratesource_list", "sources"),
                            ("workspace_notify:notify_v2_batch_list", "notify-batches"),
                            ("workspace_notify:notify_v2_settings", "notify-settings"),
                        ):
                            visit(route)
                            capture(label)
                        visit("workspace_notify:notify_v2_batch_detail", pk=batch.pk)
                        expect(page.locator("h1")).to_have_text("Acceptance batch")
                        capture("notify-detail")
                        self.assertEqual(errors, [])
                    finally:
                        context.close()
            finally:
                browser.close()

    def test_draft_validation_recovery(self):
        from playwright.sync_api import sync_playwright, expect

        MVPOperatorJourneyTests._party(self)
        photograph = BytesIO()
        Image.new("RGB", (20, 20), "gold").save(photograph, format="JPEG")
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                for width in (1440, 390):
                    context = browser.new_context(viewport={"width": width, "height": 1000})
                    context.add_cookies([{
                        "name": "sessionid", "value": self.client.cookies["sessionid"].value,
                        "url": self.live_server_url,
                    }])
                    try:
                        page = context.new_page()
                        errors = []
                        page.on("pageerror", lambda error: errors.append(str(error)))
                        page.goto(self.live_server_url + self._loan_url("pawn_loan_create"))
                        page.locator('#select2-id_borrower-container').click()
                        page.locator('.select2-search__field').last.fill('MVP Borrower')
                        page.get_by_role('option').filter(has_text='MVP Borrower').click()
                        page.locator('#select2-id_series-container').click()
                        page.get_by_role('option').filter(has_text='MVP-001/A').click()
                        borrower = page.locator('#id_borrower').input_value()
                        page.locator('[name="product_version"]').select_option(str(self.product.pk))
                        page.locator('#add-collateral').click()
                        page.locator('[data-remove-collateral]').last.click()
                        for name, value in {
                            'description': 'Recovery chain', 'gross_weight': '10',
                            'net_weight': '9', 'purity_percentage': '91.6',
                            'latest_appraised_value': '50000', 'allocated_principal': '10000',
                        }.items():
                            page.locator(f'[name="collateral-0-{name}"]').fill(value)
                        page.locator('[name="collateral-0-metal"]').select_option('GOLD')
                        page.get_by_role('button', name='Save draft', exact=True).click()
                        expect(page.locator('[data-pawn-draft-error-summary]')).to_be_visible()
                        expect(page.locator('#id_borrower')).to_have_value(borrower)
                        expect(page.locator('#id_series')).to_have_value(str(self.series.pk))
                        expect(page.locator('#select2-id_borrower-container')).to_contain_text('MVP Borrower')
                        expect(page.locator('#select2-id_series-container')).to_contain_text('MVP-001/A')
                        expect(page.locator('[data-collateral-form]').last).to_be_hidden()
                        page.locator('[name="collateral-0-photograph"]').set_input_files({
                            'name': 'chain.jpg', 'mimeType': 'image/jpeg', 'buffer': photograph.getvalue(),
                        })
                        expect(page.locator('[data-summary-count]')).to_have_text('1 collateral item')
                        expect(page.locator('[data-summary-principal]')).to_have_text('10,000.00')
                        page.get_by_role('button', name='Preview economics', exact=True).click()
                        expect(page.locator('[data-validated-summary]')).to_be_visible()
                        page.locator('[name="collateral-0-gross_weight"]').fill('10.1')
                        expect(page.locator('[data-validated-summary]')).to_be_hidden()
                        expect(page.locator('[data-economic-preview]')).to_be_hidden()
                        expect(page.locator('#economic-preview-stale')).to_be_visible()
                        page.locator('[name="collateral-0-photograph"]').set_input_files({
                            'name': 'chain.jpg', 'mimeType': 'image/jpeg', 'buffer': photograph.getvalue(),
                        })
                        page.get_by_role('button', name='Save draft', exact=True).click()
                        expect(page.locator('[data-pawn-draft-error-summary]')).to_have_count(0)
                        expect(page.get_by_role('button', name='Approve loan', exact=True)).to_be_visible()
                        page.wait_for_load_state('networkidle')
                        self.assertNotIn('/create/', page.url)
                        self.assertFalse(errors, errors)
                    finally:
                        context.close()
            finally:
                browser.close()

    def test_desktop_and_mobile_lending(self):
        from playwright.sync_api import sync_playwright, expect

        artifacts = Path(os.environ.get("ROKKAD_BROWSER_ARTIFACTS", Path(gettempdir()) / "rokkad-browser-acceptance"))
        artifacts.mkdir(parents=True, exist_ok=True)
        report = {"viewports": [], "page_errors": [], "failed_requests": [], "documents": [], "camera": []}
        photograph = BytesIO()
        Image.new("RGB", (640, 480), "gold").save(photograph, format="JPEG")
        downloaded_urls = set()
        slug = self.workspace.slug
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            report["browser"] = browser.version
            try:
                for width, height in ((1440, 1000), (390, 844)):
                    context = browser.new_context(viewport={"width": width, "height": height})
                    context.add_cookies([{
                        "name": "sessionid", "value": self.client.cookies["sessionid"].value,
                        "url": self.live_server_url,
                    }])
                    context.add_init_script("""if (navigator.mediaDevices) {
                        navigator.mediaDevices.getUserMedia = () => Promise.reject(
                            new DOMException('Acceptance permission denial', 'NotAllowedError'));
                    }""")
                    page = context.new_page()
                    page.on("pageerror", lambda error: report["page_errors"].append(str(error)))
                    page.on("requestfailed", lambda request: report["failed_requests"].append({"url": request.url, "error": request.failure}))
                    page.set_default_timeout(15000)

                    def visit(path):
                        response = page.goto(self.live_server_url + path)
                        self.assertEqual(response.status, 200, path)

                    def capture(name):
                        page.screenshot(path=str(artifacts / f"{width}-{name}.png"), full_page=True)
                        dimensions = page.evaluate("({width: innerWidth, scroll: document.documentElement.scrollWidth})")
                        report["viewports"].append({"width": width, "page": name, **dimensions})
                        self.assertLessEqual(dimensions["scroll"], width + 1, f"Overflow: {name} at {width}px")

                    try:
                        visit(reverse("workspace_slug_party_create", kwargs={"workspace_slug": slug}))
                        page.locator('[name="display_name"]').fill(f"Browser Borrower {width}")
                        page.locator('button[type="submit"]').last.click()
                        expect(page.locator("h1")).to_contain_text(f"Browser Borrower {width}")
                        capture("party")
                        visit(self._loan_url("pawn_loan_create"))
                        capture("draft-empty")
                        page.get_by_role("button", name="Save draft", exact=True).click()
                        expect(page.locator("[data-pawn-draft-error-summary]")).to_be_visible()
                        page.locator("#select2-id_borrower-container").click()
                        page.locator(".select2-search__field").last.fill(f"Browser Borrower {width}")
                        page.get_by_role("option").filter(has_text=f"Browser Borrower {width}").click()
                        page.locator("#select2-id_series-container").click()
                        page.get_by_role("option").filter(has_text="MVP-001/A").click()
                        page.locator('[name="product_version"]').select_option(str(self.product.pk))
                        page.locator('[name="loan_date"]').fill(self.today.isoformat())
                        page.locator('[name="tenure_months"]').fill("3")
                        initial_rows = page.locator("[data-collateral-form]").count()
                        page.locator("#add-collateral").click()
                        expect(page.locator("[data-collateral-form]")).to_have_count(initial_rows + 1)
                        page.locator("[data-remove-collateral]").last.click()
                        for name, value in {
                            "description": "Browser gold chain", "gross_weight": "10",
                            "net_weight": "9", "purity_percentage": "91.6",
                            "latest_appraised_value": "50000", "allocated_principal": "10000",
                        }.items():
                            page.locator(f'[name="collateral-0-{name}"]').fill(value)
                        page.locator('[name="collateral-0-metal"]').select_option("GOLD")
                        expect(page.locator('[data-summary-principal]')).to_have_text('10,000.00')
                        expect(page.locator('[data-summary-borrower]')).to_contain_text(f'Browser Borrower {width}')
                        expect(page.locator('[data-summary-items]')).to_contain_text('Net 9 g')
                        expect(page.locator('[data-summary-items]')).to_contain_text('Photo needed')
                        selected_borrower = page.locator('#id_borrower').input_value()
                        selected_series = page.locator('#id_series').input_value()
                        page.get_by_role("button", name="Save draft", exact=True).click()
                        expect(page.locator("[data-pawn-draft-error-summary]")).to_be_visible()
                        expect(page.locator('#id_borrower')).to_have_value(selected_borrower)
                        expect(page.locator('#id_series')).to_have_value(selected_series)
                        expect(page.locator('#select2-id_borrower-container')).to_contain_text(f"Browser Borrower {width}")
                        expect(page.locator('#select2-id_series-container')).to_contain_text('MVP-001/A')
                        expect(page.locator('[name="collateral-0-description"]')).to_have_value('Browser gold chain')
                        capture('draft-missing-photo')
                        with page.expect_file_chooser() as chooser:
                            page.locator(".js-collateral-camera").first.click()
                        chooser.value.set_files({
                            "name": "chain.jpg", "mimeType": "image/jpeg", "buffer": photograph.getvalue(),
                        })
                        report["camera"].append({"width": width, "simulated_denial_upload_fallback": True,
                            "physical_capture": "not exercised"})
                        capture("draft-filled")
                        expect(page.locator('[data-summary-items]')).to_contain_text('Photo selected')
                        page.get_by_role("button", name="Save draft", exact=True).click()
                        expect(page.locator("[data-pawn-draft-error-summary]")).to_have_count(0)
                        capture("draft-saved")
                        page.get_by_role("button", name="Approve loan", exact=True).click()
                        capture("approved")
                        page.get_by_role("link", name="Disburse loan", exact=True).click()
                        page.locator('button[type="submit"]').last.click()
                        capture("active")
                        page.get_by_role("link", name="Repayment", exact=True).click()
                        page.locator('[name="amount"]').fill("1000")
                        page.locator('button[type="submit"]').last.click()
                        page.get_by_role("link", name="Full release", exact=True).click()
                        capture("release")
                        page.locator('[name="confirm_collateral_handoff"]').check()
                        page.locator('button[type="submit"]').last.click()
                        expect(page.get_by_role("link", name="Full release", exact=True)).to_have_count(0)
                        expect(page.get_by_role("link", name="Review event history", exact=True)).to_be_visible()
                        capture("closed")
                        for label, name in (("Loan ticket PDF", "ticket"), ("Receipt PDF", "receipt"), ("Release memo PDF", "release-memo")):
                            copies = []
                            for copy in range(2):
                                with page.expect_download() as pending:
                                    page.get_by_role("link", name=label, exact=True).first.click()
                                destination = artifacts / f"{width}-{name}-{copy}.pdf"
                                pending.value.save_as(destination)
                                downloaded_urls.add(pending.value.url)
                                copies.append(destination.read_bytes())
                            self.assertTrue(copies[0].startswith(b"%PDF"))
                            self.assertEqual(copies[0], copies[1])
                            report["documents"].append({"width": width, "type": name, "bytes": len(copies[0]), "identical_reprint": True})
                    except Exception:
                        report["failure"] = traceback.format_exc()
                        try:
                            (artifacts / f"{width}-failure.html").write_text(page.content(), encoding="utf-8")
                            page.screenshot(path=str(artifacts / f"{width}-failure.png"), full_page=True, timeout=5000)
                        except Exception:
                            pass
                        raise
                    finally:
                        context.close()
            finally:
                browser.close()
                # Chromium reports navigation handed to a successful download as aborted.
                report["failed_requests"] = [failure for failure in report["failed_requests"]
                    if not (failure["error"] == "net::ERR_ABORTED" and failure["url"] in downloaded_urls)]
                (artifacts / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        self.assertEqual(report["page_errors"], [])
        self.assertEqual(report["failed_requests"], [])
