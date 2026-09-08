"""Full HTTP acceptance of a new Workspace's first lending workflow."""

from datetime import timedelta
from decimal import Decimal
from io import BytesIO
import re
from tempfile import TemporaryDirectory
from uuid import uuid4

from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection, transaction
from django.test import Client, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils.html import strip_tags
from django.utils import timezone

from apps.orgs.models import Company, Membership, Role
from apps.subscriptions.models import Plan, Subscription
from apps.tenancy.context import current_workspace_id, workspace_context
from apps.tenant_apps.loans.models import (
    LoanDocumentIssue, LoanLicense, LoanProductVersion, LoanSeries, PawnLoan, PawnLoanRelease,
)
from apps.tenant_apps.loans.selectors import get_pawn_loan_balance
from apps.tenant_apps.party.models import Party, PartyContactMethod


@override_settings(
    BILLING_ALLOW_TRIAL_START=True,
    ALLOWED_HOSTS=["testserver"],
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)
class MVPOperatorJourneyTests(TransactionTestCase):
    def setUp(self):
        media = TemporaryDirectory()
        self.addCleanup(media.cleanup)
        self.enterContext(override_settings(MEDIA_ROOT=media.name))
        self.owner = get_user_model().objects.create_user(username="mvp-owner")
        Role.objects.get_or_create(name="Owner")
        self.member_role, _ = Role.objects.get_or_create(name="Member")
        self.plan = Plan.objects.create(
            name="MVP trial", tier=Plan.PlanTierChoices.STARTER,
            price=0, description="Acceptance catalog", trial_days=30,
        )
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.owner)
        self.today = timezone.localdate()
        role = connection.ops.quote_name(f"mvp_runtime_{uuid4().hex}")
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            self.addCleanup(self._drop_runtime_role, role)
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}")
            cursor.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}")
            cursor.execute(f"SET ROLE {role}")

    def _drop_runtime_role(self, role):
        with connection.cursor() as cursor:
            cursor.execute("RESET ROLE")
            cursor.execute(f"DROP OWNED BY {role}")
            cursor.execute(f"DROP ROLE {role}")

    def _get(self, url):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, msg=f"GET {url}: {response.status_code}")
        return response

    def _post(self, url, data=None, *, expected_url=None):
        response = self.client.post(
            url, data or {},
            HTTP_X_CSRFTOKEN=self.client.cookies["csrftoken"].value,
        )
        errors = ""
        if response.context:
            for key in ("form", "collateral_formset"):
                form = response.context.get(key)
                if form is not None:
                    errors += str(form.errors)
        self.assertEqual(response.status_code, 302, msg=f"POST {url}: {errors}")
        if expected_url:
            self.assertEqual(response.url, expected_url)
        return response

    def _workspace(self, name):
        url = reverse("app_workspace_create")
        self._get(url)
        response = self._post(url, {"name": name, "theme": "#123456"})
        workspace = Company.objects.get(name=name)
        self.assertTrue(Membership.objects.filter(user=self.owner, company=workspace).exists())
        self.assertFalse(Subscription.objects.filter(company=workspace).exists())
        destination = self.client.get(response.url, follow=True)
        self.assertEqual(destination.status_code, 200)
        self.assertEqual(
            destination.request["PATH_INFO"],
            reverse("workspace_subscriptions:plan-list", kwargs={"workspace_slug": workspace.slug}),
        )
        self._post(reverse("workspace_subscriptions:start-trial", kwargs={
            "workspace_slug": workspace.slug, "plan_id": self.plan.pk,
        }), expected_url=reverse("workspace_slug_dashboard", kwargs={"workspace_slug": workspace.slug}))
        self.assertEqual(Subscription.objects.get(company=workspace).status, "trial")
        self._get(reverse("workspace_slug_dashboard", kwargs={"workspace_slug": workspace.slug}))
        return workspace

    def _loan_url(self, name, *args, workspace=None):
        workspace = workspace or self.workspace
        return f"/w/{workspace.slug}" + reverse(f"loans:{name}", args=args)

    def _setup_loans(self):
        setup = self._get(reverse("workspace_slug_settings_setup", kwargs={"workspace_slug": self.workspace.slug}))
        checklist_url = reverse("workspace_slug_settings_numbering", kwargs={"workspace_slug": self.workspace.slug})
        self.assertContains(setup, checklist_url)
        setup = self._get(checklist_url)
        for name in ("license_list", "pawn_economics_setup", "loan_product_list"):
            self.assertContains(setup, self._loan_url(name))
        self._get(self._loan_url("license_list"))
        self._post(self._loan_url("license_create"), {
            "name": "Counter licence", "license_number": "MVP-001",
            "issuing_authority": "Acceptance authority",
            "issued_on": (self.today - timedelta(days=30)).isoformat(),
            "expires_on": (self.today + timedelta(days=365)).isoformat(),
            "supporting_document": SimpleUploadedFile("licence.pdf", b"%PDF-1.4\n%%EOF", content_type="application/pdf"),
        })
        with workspace_context(self.workspace.pk):
            license = LoanLicense.objects.get()
        self._post(self._loan_url("series_create", license.pk), {
            "name": "Counter A", "code": "A", "is_active": "on",
            "pawn_loan_prefix": "PL-A-", "release_prefix": "RL-A-",
            "number_width": "5", "maximum_number": "10000",
        })
        self._post(self._loan_url("pawn_economics_setup"), {
            "action": "configuration", "configuration-license": "",
            "configuration-valuation_method": "LATEST_APPRAISAL",
            "configuration-maximum_ltv_ratio": "0.80",
            "configuration-advance_interest_periods": "1",
            "configuration-interest_method": "SIMPLE",
            "configuration-partial_month_method": "FULL_MONTH",
            "configuration-partial_month_cutoff_days": "15",
            "configuration-partial_month_lower_fraction": "0.5",
            "configuration-capitalization_interval_periods": "12",
            "configuration-rounding_method": "PER_ACCRUAL_PERIOD",
            "configuration-currency_quantum": "0.01",
            "configuration-gold_monthly_interest_rate": "2",
            "configuration-silver_monthly_interest_rate": "4",
            "configuration-effective_from": (self.today - timedelta(days=1)).isoformat(),
        })
        self._post(self._loan_url("loan_product_seed_defaults"))
        with workspace_context(self.workspace.pk):
            self.product = LoanProductVersion.objects.get(product__code="GOLD-BULLET")
            self.series = LoanSeries.objects.get()
        self._post(self._loan_url("loan_product_version_activate", self.product.pk))

    def _party(self):
        url = reverse("workspace_slug_party_create", kwargs={"workspace_slug": self.workspace.slug})
        self._get(url)
        response = self._post(url, {
            "display_name": "MVP Borrower", "party_type": "INDIVIDUAL", "status": "ACTIVE",
        })
        with workspace_context(self.workspace.pk):
            party = Party.objects.get(display_name="MVP Borrower")
        detail_url = reverse("workspace_slug_party_detail", kwargs={"workspace_slug": self.workspace.slug, "pk": party.pk})
        self.assertEqual(response.url, detail_url)
        self.assertContains(self._get(detail_url), "MVP Borrower")
        edit_url = reverse("workspace_slug_party_update", kwargs={"workspace_slug": self.workspace.slug, "pk": party.pk})
        self._get(edit_url)
        self._post(edit_url, {
            "display_name": "MVP Borrower", "party_type": "INDIVIDUAL",
            "status": "ACTIVE", "legal_name": "MVP Borrower Updated",
        }, expected_url=detail_url)
        self.assertContains(self._get(detail_url), "MVP Borrower Updated")
        return party

    def test_first_loan_from_workspace_creation_to_release_and_reprint(self):
        self._complete_first_loan()

    def test_first_loan_inside_an_outer_transaction(self):
        with transaction.atomic():
            self._complete_first_loan()
            self.assertIsNone(current_workspace_id())

    def _complete_first_loan(self):
        self.workspace = self._workspace("MVP Counter")
        self._setup_loans()
        party = self._party()
        photograph = BytesIO()
        Image.new("RGB", (12, 12), "gold").save(photograph, format="JPEG")
        self._get(self._loan_url("pawn_loan_create"))
        response = self._post(self._loan_url("pawn_loan_create"), {
            "borrower": party.pk, "series": self.series.pk,
            "product_version": self.product.pk, "loan_date": self.today.isoformat(),
            "tenure_months": "3", "collateral-TOTAL_FORMS": "1",
            "collateral-INITIAL_FORMS": "0", "collateral-MIN_NUM_FORMS": "1",
            "collateral-MAX_NUM_FORMS": "1000", "collateral-0-description": "Gold chain",
            "collateral-0-metal": "GOLD", "collateral-0-gross_weight": "10",
            "collateral-0-net_weight": "9", "collateral-0-purity_percentage": "91.6",
            "collateral-0-latest_appraised_value": "50000",
            "collateral-0-allocated_principal": "10000",
            "collateral-0-photograph": SimpleUploadedFile("chain.jpg", photograph.getvalue(), content_type="image/jpeg"),
        })
        with workspace_context(self.workspace.pk):
            loan = PawnLoan.objects.get()
            self.assertEqual(loan.state, "DRAFT")
        detail_url = self._loan_url("pawn_loan_detail", loan.pk)
        self.assertEqual(response.url, detail_url)
        self._get(detail_url)
        self._post(self._loan_url("pawn_loan_approve", loan.pk), expected_url=detail_url)
        self._post(self._loan_url("pawn_loan_disburse", loan.pk), {"effective_date": self.today.isoformat()}, expected_url=detail_url)
        with workspace_context(self.workspace.pk):
            loan.refresh_from_db()
            self.assertEqual(loan.state, "ACTIVE")
            self.assertEqual(get_pawn_loan_balance(loan.pk, as_of_date=self.today).principal_outstanding, Decimal("10000"))
        ticket_url = self._loan_url("pawn_loan_ticket_pdf", loan.pk)
        dashboard = self._get(reverse("workspace_slug_dashboard", kwargs={
            "workspace_slug": self.workspace.slug,
        }))
        self.assertEqual(dashboard.context["loan_count"], 1)
        self.assertEqual(dashboard.context["total_loan_amount"], Decimal("10000"))
        breadcrumb = re.search(
            r'<nav aria-label="breadcrumb"[^>]*>(.*?)</nav>',
            dashboard.content.decode(), re.S,
        )
        self.assertIsNotNone(breadcrumb)
        labels = [
            strip_tags(item).strip()
            for item in re.findall(r"<li\b[^>]*>(.*?)</li>", breadcrumb.group(1), re.S)
        ]
        self.assertEqual(labels, ["Home", self.workspace.name, "Dashboard"])
        ticket = self._get(ticket_url)
        ticket_bytes = self._pdf_bytes(ticket)
        self.assertIn("X-Rokkad-Document-Issue", ticket)
        repayment_url = self._loan_url("pawn_loan_repay", loan.pk)
        self._get(repayment_url)
        payment = {"amount": "1000", "request_key": "mvp-repayment"}
        self._post(repayment_url, payment, expected_url=detail_url)
        with workspace_context(self.workspace.pk):
            event_count = loan.loan_events.count()
            self.assertEqual(get_pawn_loan_balance(loan.pk, as_of_date=self.today).principal_outstanding, Decimal("9000"))
        self._post(repayment_url, payment, expected_url=detail_url)
        with workspace_context(self.workspace.pk):
            self.assertEqual(loan.loan_events.count(), event_count)
            event = loan.loan_events.get(event_kind="REPAYMENT")
        receipt_url = self._loan_url("pawn_repayment_receipt_pdf", loan.pk, event.pk)
        receipt = self._pdf_bytes(self._get(receipt_url))
        self.assertEqual(self._pdf_bytes(self._get(receipt_url)), receipt)
        release_url = self._loan_url("pawn_loan_release_full", loan.pk)
        release_page = self._get(release_url)
        quote = release_page.context["quote"]
        self.assertFalse(quote.blockers)
        settlement_input = release_page.context["form"]["settlement_amount"].value()
        self.assertEqual(Decimal(settlement_input), quote.minimum_settlement)
        self._post(release_url, {
            "settlement_amount": str(settlement_input),
            "request_key": "mvp-release", "confirm_collateral_handoff": "on",
        }, expected_url=detail_url)
        with workspace_context(self.workspace.pk):
            loan.refresh_from_db()
            self.assertEqual(loan.state, "CLOSED")
            self.assertEqual(get_pawn_loan_balance(loan.pk, as_of_date=self.today).total_due, Decimal("0"))
            release = PawnLoanRelease.objects.get(loan=loan)
            self.assertEqual(release.items.count(), 1)
        self._get(detail_url)
        memo_url = self._loan_url("pawn_release_memo_pdf", release.pk)
        memo = self._pdf_bytes(self._get(memo_url))
        self.assertEqual(self._pdf_bytes(self._get(memo_url)), memo)
        self.assertEqual(self._pdf_bytes(self._get(ticket_url)), ticket_bytes)
        with workspace_context(self.workspace.pk):
            self.assertEqual(LoanDocumentIssue.objects.filter(document_type="loan_ticket").count(), 1)
            self.assertEqual(LoanDocumentIssue.objects.filter(document_type="repayment_receipt").count(), 1)
            self.assertEqual(LoanDocumentIssue.objects.filter(document_type="release_memo").count(), 1)

    def _pdf_bytes(self, response):
        content = b"".join(response.streaming_content) if response.streaming else response.content
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(content.startswith(b"%PDF"))
        return content

    def test_workspace_list_and_account_do_not_change_selected_workspace(self):
        first = self._workspace("Navigation First")
        second = self._workspace("Navigation Second")
        first_page = self._get(reverse("workspace_slug_dashboard", kwargs={"workspace_slug": first.slug}))
        self.assertContains(first_page, first.name)
        self.owner.profile.refresh_from_db()
        self.assertEqual(self.owner.profile.workspace_id, first.pk)
        for route in ("app_workspaces", "workspace_selector", "account_settings"):
            response = self._get(reverse(route))
            self.assertIsNone(getattr(response.wsgi_request, "workspace", None))
        self.owner.profile.refresh_from_db()
        self.assertEqual(self.owner.profile.workspace_id, first.pk)
        self.assertRedirects(self.client.get(reverse("workspace_management")), reverse("workspace_selector"))
        landing = self.client.get(reverse("dashboard"))
        self.assertRedirects(landing, reverse("workspace_slug_dashboard", kwargs={"workspace_slug": first.slug}))

    def test_two_workspaces_and_member_permissions_remain_independent(self):
        self.workspace = self._workspace("MVP First")
        party = self._party()
        second = self._workspace("MVP Second")
        detail = reverse("workspace_slug_party_detail", kwargs={"workspace_slug": self.workspace.slug, "pk": party.pk})
        self.assertContains(self._get(detail), "MVP Borrower")
        wrong = reverse("workspace_slug_party_detail", kwargs={"workspace_slug": second.slug, "pk": party.pk})
        self.assertEqual(self.client.get(wrong).status_code, 404)
        self.assertEqual(self.client.post(self._loan_url("loan_product_seed_defaults")).status_code, 403)
        member = get_user_model().objects.create_user(username="mvp-member")
        Membership.objects.create(user=member, company=self.workspace, role=self.member_role)
        self.client.force_login(member)
        self._get(self._loan_url("pawn_loan_list"))
        self.assertEqual(self.client.get(self._loan_url("license_list")).status_code, 403)
        billing = reverse("workspace_subscriptions:dashboard", kwargs={"workspace_slug": self.workspace.slug})
        self.assertEqual(self.client.get(billing).status_code, 403)
        self.assertEqual(self.client.get(self._loan_url("pawn_loan_list", workspace=second)).status_code, 302)
        Membership.objects.filter(user=member, company=self.workspace).delete()
        self.assertEqual(self.client.get(self._loan_url("pawn_loan_list")).status_code, 302)

    def test_party_actions_keep_workspace_identity(self):
        self.workspace = self._workspace("Party Actions")
        party = self._party()
        second = self._workspace("Party Other")
        detail = reverse("workspace_slug_party_detail", kwargs={
            "workspace_slug": self.workspace.slug, "pk": party.pk,
        })
        from apps.tenant_apps.party.urls import urlpatterns
        from django.urls import resolve
        for pattern in urlpatterns:
            kwargs = {key: party.pk for key in pattern.pattern.converters}
            kwargs["workspace_slug"] = self.workspace.slug
            url = reverse(f"workspace_party:{pattern.name}", kwargs=kwargs)
            self.assertTrue(url.startswith(f"/w/{self.workspace.slug}/parties/"))
            self.assertEqual(resolve(url).kwargs["workspace_slug"], self.workspace.slug)
        for tab in ("overview", "contacts", "addresses", "kyc", "relationships", "merge"):
            response = self._get(f"{detail}?tab={tab}")
            self.assertNotContains(response, 'action="/party/')
        add = reverse("workspace_party:party_contact_add", args=[self.workspace.slug, party.pk])
        self.assertContains(self._get(f"{detail}?tab=contacts"), f'action="{add}"')
        self.assertEqual(self.client.post(add, {}).status_code, 403)
        data = {"contact_type": "MOBILE", "value": "9999999999", "is_primary": "on"}
        self._post(add, data, expected_url=f"{detail}?tab=contacts")
        with workspace_context(self.workspace.pk):
            contact = PartyContactMethod.objects.get(party=party)
            self.assertEqual(contact.value, "+919999999999")
        update = reverse("workspace_party:party_contact_update", args=[self.workspace.slug, party.pk, contact.pk])
        invalid = self.client.post(update, {"csrfmiddlewaretoken": self.client.cookies["csrftoken"].value, "contact_type": "MOBILE", "value": "bad"})
        self.assertEqual(invalid.status_code, 200)
        self.assertNotContains(invalid, 'action="/party/')
        wrong = reverse("workspace_party:party_contact_update", args=[second.slug, party.pk, contact.pk])
        self.assertEqual(self.client.post(wrong, {**data, "csrfmiddlewaretoken": self.client.cookies["csrftoken"].value}).status_code, 404)
        data["value"] = "8888888888"
        self._post(update, data, expected_url=f"{detail}?tab=contacts")
        delete = reverse("workspace_party:party_contact_delete", args=[self.workspace.slug, party.pk, contact.pk])
        self._post(delete, {}, expected_url=f"{detail}?tab=contacts")
        with workspace_context(self.workspace.pk):
            self.assertFalse(PartyContactMethod.objects.filter(pk=contact.pk).exists())
        denied_role, _ = Role.objects.get_or_create(name="NoAccess")
        outsider = get_user_model().objects.create_user(username="party-denied")
        Membership.objects.create(user=outsider, company=self.workspace, role=denied_role)
        self.client.force_login(outsider)
        self.assertEqual(self.client.post(add, {**data, "csrfmiddlewaretoken": self.client.cookies["csrftoken"].value}).status_code, 403)

    def test_borrower_autocomplete_is_workspace_scoped(self):
        from apps.tenant_apps.loans.forms import PawnDraftForm

        self.workspace = self._workspace("Search First")
        party = self._party()
        other = self._workspace("Search Second")
        with workspace_context(other.pk):
            Party.objects.create(display_name="MVP Other Borrower")
        with workspace_context(self.workspace.pk):
            form = PawnDraftForm(workspace=self.workspace)
            str(form["borrower"])
            widget = form.fields["borrower"].widget
            url = widget.get_url()
            token = widget.field_id
        response = self.client.get(url, {"field_id": token, "term": "MVP"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([str(row["id"]) for row in response.json()["results"]], [str(party.pk)])
        wrong = reverse("workspace_party:party_autocomplete", args=[other.slug])
        self.assertEqual(self.client.get(wrong, {"field_id": token, "term": "MVP"}).status_code, 404)
        self.assertEqual(self.client.get(url, {"field_id": "invalid", "term": "MVP"}).status_code, 404)
        denied_role, _ = Role.objects.get_or_create(name="NoAccess")
        denied = get_user_model().objects.create_user(username="search-denied")
        Membership.objects.create(user=denied, company=self.workspace, role=denied_role)
        self.client.force_login(denied)
        self.assertEqual(self.client.get(url, {"field_id": token, "term": "MVP"}).status_code, 403)

    def test_rates_navigation_and_mutations_keep_workspace(self):
        from apps.tenant_apps.rates.models import Rate, RateSource
        self.workspace = self._workspace("Rates First")
        other = self._workspace("Rates Second")
        def url(name, *args, workspace=None):
            return reverse("workspace_rates:" + name, args=[(workspace or self.workspace).slug, *args])
        self.assertContains(self._get(url("rate_list")), url("ratesource_create"))
        self._get(url("ratesource_create"))
        source_data = {"name": "Local source", "location": "Counter", "tax_included": "on"}
        response = self._post(url("ratesource_create"), source_data)
        with workspace_context(self.workspace.pk):
            source = RateSource.objects.get()
        self.assertEqual(response.url, url("ratesource_detail", source.pk))
        rate_data = {"rate_source": source.pk, "metal": "Gold", "currency": "INR", "purity": "24k", "buying_rate": "100", "selling_rate": "110"}
        self.assertContains(self._get(url("rate_create")), url("rate_list"))
        self._post(url("rate_create"), rate_data)
        with workspace_context(self.workspace.pk):
            rate = Rate.objects.get()
        rate_data["buying_rate"] = "101"
        self._post(url("rate_update", rate.pk), rate_data, expected_url=url("rate_detail", rate.pk))
        self.assertEqual(self.client.get(url("rate_update", rate.pk, workspace=other)).status_code, 404)
        self.assertEqual(self.client.post(url("rate_delete", rate.pk)).status_code, 403)
        self._post(url("rate_delete", rate.pk), expected_url=url("rate_list"))
        self._post(url("ratesource_delete", source.pk), expected_url=url("ratesource_list"))

    def test_notify_navigation_artifacts_and_actions_keep_workspace(self):
        from apps.tenant_apps.notify_v2.models import NotificationArtifact, NotificationBatch, NotificationEvent, NotificationEventType, NotificationJob, NotificationRecipient
        self.workspace = self._workspace("Notify First")
        other = self._workspace("Notify Second")
        with workspace_context(self.workspace.pk):
            kind = NotificationEventType.objects.create(key="acceptance", name="Acceptance", domain="LOAN")
            batch = NotificationBatch.objects.create(event_type=kind, name="Test letters")
            recipient = NotificationRecipient.objects.create(name_snapshot="Test Recipient")
            event = NotificationEvent.objects.create(event_type=kind, recipient=recipient, batch=batch)
            job = NotificationJob.objects.create(event=event, batch=batch, channel="LETTER")
            artifact = NotificationArtifact.objects.create(job=job, artifact_type="PDF", file=SimpleUploadedFile("test.pdf", b"%PDF-test", content_type="application/pdf"))
            empty = NotificationBatch.objects.create(event_type=kind, name="Empty")
        def url(name, *args, workspace=None):
            return reverse("workspace_notify:notify_v2_" + name, args=[(workspace or self.workspace).slug, *args])
        detail = url("batch_detail", batch.pk)
        self.assertContains(self._get(url("batch_list")), detail)
        download = url("artifact_download", batch.pk, artifact.pk)
        response = self._get(detail)
        self.assertContains(response, download)
        self.assertNotContains(response, artifact.file.url)
        self.assertEqual(self._pdf_bytes(self._get(download)), b"%PDF-test")
        wrong_batch = url("artifact_download", empty.pk, artifact.pk)
        self.assertEqual(self.client.get(wrong_batch).status_code, 404)
        self.assertEqual(self.client.get(url("artifact_download", batch.pk, artifact.pk, workspace=other)).status_code, 404)
        self.assertEqual(self.client.post(url("batch_mark_printed", batch.pk)).status_code, 403)
        self._post(url("batch_mark_printed", batch.pk), expected_url=detail)
        self._post(url("batch_mark_posted", batch.pk), expected_url=detail)
        self.assertContains(self._get(url("settings")), url("whatsapp_cloud_integration"))
        self._get(url("whatsapp_cloud_integration"))
        denied = get_user_model().objects.create_user(username="notify-route-denied")
        role, _ = Role.objects.get_or_create(name="NoAccess")
        Membership.objects.create(user=denied, company=self.workspace, role=role)
        self.client.force_login(denied)
        self.assertEqual(self.client.get(download).status_code, 403)

    @override_settings(WORKSPACE_SECRET_ENCRYPTION_KEY="lHcKWFYTr7srGTRy2gq31ALX5RzzX_UkI95mGaSeP-8=")
    def test_anonymous_signed_notify_callback_and_replay(self):
        import hashlib, hmac, json
        from apps.orgs.models import Domain
        from apps.tenant_apps.notify_v2.models import WhatsAppCloudWebhookReceipt
        from apps.tenant_apps.notify_v2.services.whatsapp_integration import set_whatsapp_cloud_integration
        self.workspace = self._workspace("Webhook First")
        other = self._workspace("Webhook Other")
        for workspace, phone, secret in ((self.workspace, "phone-first", "first-secret"), (other, "phone-other", "other-secret")):
            with workspace_context(workspace.pk):
                set_whatsapp_cloud_integration(workspace_id=workspace.pk, actor=self.owner,
                    api_version="v20.0", phone_number_id=phone, access_token="test-token",
                    webhook_verify_token="test-verify", app_secret=secret, is_enabled=True)
        endpoint = reverse("workspace_notify:notify_v2_whatsapp_cloud_webhook", args=[self.workspace.slug])
        client = Client(enforce_csrf_checks=True)
        verified = client.get(endpoint, {"hub.mode": "subscribe", "hub.verify_token": "test-verify", "hub.challenge": "challenge"})
        self.assertEqual(verified.status_code, 200)
        self.assertEqual(verified.content, b"challenge")
        payload = {"object": "whatsapp_business_account", "entry": [{"changes": [{"value": {
            "metadata": {"phone_number_id": "phone-first"},
            "statuses": [{"id": "test-message", "status": "delivered", "timestamp": "123"}],
        }}]}]}
        body = json.dumps(payload).encode()
        signature = "sha256=" + hmac.new(b"first-secret", body, hashlib.sha256).hexdigest()
        self.assertEqual(client.post(endpoint, body, content_type="application/json").status_code, 403)
        accepted = client.post(endpoint, body, content_type="application/json", HTTP_X_HUB_SIGNATURE_256=signature)
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(client.post(endpoint, body, content_type="application/json", HTTP_X_HUB_SIGNATURE_256=signature).json()["duplicate_statuses"], 1)
        wrong = reverse("workspace_notify:notify_v2_whatsapp_cloud_webhook", args=[other.slug])
        self.assertEqual(client.post(wrong, body, content_type="application/json", HTTP_X_HUB_SIGNATURE_256=signature).status_code, 403)
        self.assertIsNone(current_workspace_id())
        with workspace_context(self.workspace.pk):
            self.assertEqual(WhatsAppCloudWebhookReceipt.objects.count(), 1)
        with workspace_context(other.pk):
            self.assertEqual(WhatsAppCloudWebhookReceipt.objects.count(), 0)
        self.assertEqual(client.get(reverse("workspace_notify:notify_v2_settings", args=[self.workspace.slug])).status_code, 302)
        Domain.objects.create(tenant=other, domain="other-webhook.test")
        with override_settings(ALLOWED_HOSTS=["testserver", "other-webhook.test"]):
            self.assertEqual(client.get(endpoint, HTTP_HOST="other-webhook.test").status_code, 403)
        Company.all_objects.filter(pk=self.workspace.pk).update(lifecycle_state=Company.LifecycleState.SUSPENDED)
        self.assertEqual(client.get(endpoint).status_code, 403)

    def test_notify_admin_links_require_registered_workspace_domain(self):
        from apps.orgs.models import Domain
        self.workspace = self._workspace("Admin Links")
        Domain.objects.filter(tenant=self.workspace).delete()
        self.owner.is_staff = True
        self.owner.save(update_fields=["is_staff"])
        settings_url = reverse("workspace_notify:notify_v2_settings", args=[self.workspace.slug])
        self.assertNotContains(self._get(settings_url), '>Manage Templates</a>')
        Domain.objects.create(tenant=self.workspace, domain="admin-links.test")
        response = self._get(settings_url)
        self.assertContains(response, 'http://admin-links.test' + reverse("admin:notify_v2_notificationtemplate_changelist"))
