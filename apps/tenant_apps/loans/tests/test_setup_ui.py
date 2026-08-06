import uuid
import io
import json
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import RequestFactory, override_settings
from django.urls import reverse
from django.utils import timezone
from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient

from apps.tenant_apps.loans.access import assert_loans_setup_access
from apps.tenant_apps.loans.domain import LoanDocumentKind
from apps.tenant_apps.loans.models import (
    LoanChangeLog,
    LoanLicense,
    LoanDocumentIssue,
    LoanDocumentLayout,
    LoanDocumentLayoutRevision,
    LoanNumberSequence,
    LoanSeries,
    PawnLoan,
    PawnLoanApprovalSnapshot,
    PawnLoanAccountingEvent,
    PawnLoanAccountingOutbox,
    PawnLoanEconomicPolicy,
    PawnMetalInterestRatePolicy,
)
from apps.tenant_apps.loans.views import _license_for_workspace
from apps.tenant_apps.party.models import Party
from apps.orgs.models import Membership, Role
from PIL import Image as PillowImage
from apps.tenant_apps.loans.documents import starter_layout
from apps.tenant_apps.loans.services import LoanDocumentLayoutService


@override_settings(
    ROOT_URLCONF="django_project.tenant_urls",
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    },
)
class LoansSetupUiTests(TenantTestCase):
    test_schema_name = f"loans_setup_{uuid.uuid4().hex[:8]}"
    test_domain = f"loans-setup-{uuid.uuid4().hex[:8]}.test.com"

    @classmethod
    def get_test_schema_name(cls):
        return cls.test_schema_name

    @classmethod
    def get_test_tenant_domain(cls):
        return cls.test_domain

    @classmethod
    def setup_tenant(cls, tenant):
        User = get_user_model()
        owner, _ = User.objects.get_or_create(
            username="loans-setup-owner",
            defaults={"email": "loans-setup-owner@example.com"},
        )
        tenant.name = f"Loans Setup {uuid.uuid4().hex[:8]}"
        tenant.owner = owner
        tenant.creator = owner
        tenant.save()
        owner_role, _ = Role.objects.get_or_create(name="Owner")
        Membership.objects.get_or_create(
            user=owner,
            company=tenant,
            defaults={"role": owner_role},
        )

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        static_url = patch(
            "django.templatetags.static.StaticNode.handle_simple",
            side_effect=lambda path: f"/static/{path}",
        )
        static_url.start()
        self.addCleanup(static_url.stop)
        self.owner = self.tenant.owner
        self.client = TenantClient(self.tenant)
        self.client.force_login(self.owner)

    def tenant_get(self, url):
        return self.client.get(url)

    def tenant_post(self, url, data=None):
        return self.client.post(url, data or {})

    def test_owner_can_complete_license_and_series_setup_without_admin(self):
        response = self.tenant_post(
            reverse("loans:license_create"),
            {
                "name": "Primary Pawn License",
                "license_number": "PBL-UI-1",
                "issuing_authority": "State Authority",
                "issued_on": "2026-01-01",
                "expires_on": "2027-01-01",
                "notes": "",
            },
        )
        license = LoanLicense.objects.get(license_number="PBL-UI-1")
        self.assertRedirects(
            response,
            reverse("loans:license_detail", args=[license.pk]),
            fetch_redirect_response=False,
        )

        response = self.tenant_post(
            reverse("loans:series_create", args=[license.pk]),
            {
                "name": "Main Counter",
                "code": "A",
                "is_active": "on",
                "pawn_loan_prefix": "PL-A-",
                "release_prefix": "RL-A-",
                "number_width": 5,
                "maximum_number": 10000,
            },
        )

        self.assertEqual(response.status_code, 302)
        series = LoanSeries.objects.get(license=license, code="A")
        self.assertEqual(series.number_sequences.count(), 2)
        detail = self.tenant_get(reverse("loans:license_detail", args=[license.pk]))
        self.assertContains(detail, "PL-A-00001")
        self.assertContains(detail, "RL-A-00001")
        self.assertContains(detail, "Ready")
        self.assertContains(detail, "New Loans Setup")

    def test_detail_preview_does_not_consume_a_number(self):
        license, series = self._configured_setup()
        sequence = LoanNumberSequence.objects.get(
            series=series, document_kind=LoanDocumentKind.PAWN_LOAN.value
        )

        self.tenant_get(reverse("loans:license_detail", args=[license.pk]))
        self.tenant_get(reverse("loans:license_detail", args=[license.pk]))

        sequence.refresh_from_db()
        self.assertEqual(sequence.next_number, 1)

    def test_owner_can_add_workspace_economic_configuration(self):
        response = self.tenant_post(
            reverse("loans:pawn_economics_setup"),
            {
                "action": "configuration",
                "configuration-license": "",
                "configuration-valuation_method": "LATEST_APPRAISAL",
                "configuration-maximum_ltv_ratio": "0.80",
                "configuration-advance_interest_periods": "1",
                "configuration-gold_monthly_interest_rate": "2",
                "configuration-silver_monthly_interest_rate": "4",
                "configuration-effective_from": "2026-08-05",
            },
        )

        self.assertRedirects(
            response,
            reverse("loans:pawn_economics_setup"),
            fetch_redirect_response=False,
        )
        self.assertEqual(PawnLoanEconomicPolicy.objects.count(), 1)
        self.assertEqual(PawnMetalInterestRatePolicy.objects.count(), 2)
        page = self.tenant_get(reverse("loans:pawn_economics_setup"))
        self.assertContains(page, "PawnLoan economic policies")
        self.assertContains(page, "Gold")
        self.assertContains(page, "Silver")

    def test_expiry_is_post_only_and_blocks_readiness_without_deleting_license(self):
        license, _ = self._configured_setup()
        expire_url = reverse("loans:license_expire", args=[license.pk])

        self.assertEqual(self.tenant_get(expire_url).status_code, 405)
        response = self.tenant_post(expire_url)

        self.assertEqual(response.status_code, 302)
        license.refresh_from_db()
        self.assertFalse(license.is_active)
        detail = self.tenant_get(reverse("loans:license_detail", args=[license.pk]))
        self.assertContains(detail, "new drafts blocked")

    def test_exhausted_sequence_is_visible_and_not_ready(self):
        license, series = self._configured_setup()
        sequence = LoanNumberSequence.objects.get(
            series=series, document_kind=LoanDocumentKind.PAWN_LOAN.value
        )
        sequence.next_number = sequence.maximum_number + 1
        sequence.save(update_fields=["next_number"])

        detail = self.tenant_get(reverse("loans:license_detail", args=[license.pk]))

        self.assertContains(detail, "sequence is exhausted")
        self.assertContains(detail, "Not ready")

    def test_non_member_is_denied_setup_access(self):
        user = get_user_model().objects.create_user(
            username=f"setup-outsider-{uuid.uuid4().hex[:8]}",
            email=f"setup-outsider-{uuid.uuid4().hex[:8]}@example.com",
        )
        request = RequestFactory().get("/loans/setup/")
        request.user = user
        request.tenant = self.tenant

        with self.assertRaises(PermissionDenied):
            assert_loans_setup_access(request)

    def test_workspace_filtered_lookup_fails_closed(self):
        request = RequestFactory().get("/loans/setup/licenses/999/")
        request.loans_workspace = self.tenant
        with patch(
            "apps.tenant_apps.loans.views.get_object_or_404"
        ) as get_object_or_404:
            _license_for_workspace(request, 999)

        get_object_or_404.assert_called_once_with(
            LoanLicense, pk=999, workspace=self.tenant
        )

    def test_operations_console_surfaces_mvp_blockers_and_audit_evidence(self):
        license, series = self._configured_setup()
        loan = self._loan(license, series, "PL-A-00001", state="APPROVED")
        event = PawnLoanAccountingEvent.objects.create(
            loan=loan,
            event_kind="DISBURSAL",
            effective_date=date(2026, 8, 1),
            payload={"values": {"principal": "10000.00"}},
            payload_fingerprint="event-fingerprint",
            idempotency_key="operations-event-1",
            created_by=self.owner,
        )
        outbox = PawnLoanAccountingOutbox.objects.create(
            event=event,
            idempotency_key="operations-outbox-1",
            payload={"event": "DISBURSAL"},
            payload_fingerprint="outbox-fingerprint",
            status="FAILED",
            attempt_count=2,
            last_error="DEA posting unavailable",
        )
        stale_event = PawnLoanAccountingEvent.objects.create(
            loan=loan,
            event_kind="INTEREST_ACCRUAL",
            effective_date=date(2026, 8, 2),
            payload={},
            payload_fingerprint="stale-event-fingerprint",
            idempotency_key="operations-event-2",
            created_by=self.owner,
        )
        PawnLoanAccountingOutbox.objects.create(
            event=stale_event,
            idempotency_key="operations-outbox-2",
            payload={},
            payload_fingerprint="stale-outbox-fingerprint",
            status="PROCESSING",
            claimed_at=timezone.now() - timedelta(minutes=30),
        )
        release_sequence = LoanNumberSequence.objects.get(
            series=series,
            document_kind=LoanDocumentKind.PAWN_LOAN_RELEASE.value,
        )
        release_sequence.next_number = release_sequence.maximum_number + 1
        release_sequence.save(update_fields=["next_number"])
        LoanChangeLog.objects.create(
            loan=loan,
            event_kind="APPROVED",
            from_state="DRAFT",
            to_state="APPROVED",
            actor=self.owner,
        )

        response = self.tenant_get(reverse("loans:pawn_operations_console"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "PawnLoan operations console")
        self.assertContains(response, "Ready to allocate")
        self.assertContains(response, "EXHAUSTED")
        self.assertContains(response, "Stale processing claims need support review")
        self.assertContains(response, "DEA posting unavailable")
        self.assertContains(response, loan.loan_number)
        self.assertContains(response, "Accounting setup by serviceable loan")
        self.assertContains(response, "Recent lifecycle audit")
        self.assertContains(response, reverse("loans:pawn_outbox_retry", args=[outbox.pk]))
        self.assertContains(response, reverse("loans:pawn_operations_runbook"))

    def test_operations_retry_returns_to_console(self):
        license, series = self._configured_setup()
        loan = self._loan(license, series, "PL-A-00002")
        event = PawnLoanAccountingEvent.objects.create(
            loan=loan,
            event_kind="DISBURSAL",
            effective_date=date(2026, 8, 1),
            payload={},
            payload_fingerprint="retry-event-fingerprint",
            idempotency_key="operations-retry-event",
            created_by=self.owner,
        )
        outbox = PawnLoanAccountingOutbox.objects.create(
            event=event,
            idempotency_key="operations-retry-outbox",
            payload={},
            payload_fingerprint="retry-outbox-fingerprint",
            status="FAILED",
        )

        with patch(
            "apps.tenant_apps.loans.views.retry_failed_outbox_event"
        ) as retry:
            response = self.tenant_post(
                reverse("loans:pawn_outbox_retry", args=[outbox.pk]),
                {"next": "operations"},
            )

        self.assertRedirects(
            response,
            reverse("loans:pawn_operations_console"),
            fetch_redirect_response=False,
        )
        retry.assert_called_once_with(outbox.pk)

    def test_operations_pages_require_owner_or_admin(self):
        member = get_user_model().objects.create_user(
            username=f"operations-member-{uuid.uuid4().hex[:8]}"
        )
        member_role, _ = Role.objects.get_or_create(name="Member")
        Membership.objects.create(user=member, company=self.tenant, role=member_role)
        self.client.force_login(member)

        self.assertEqual(
            self.tenant_get(reverse("loans:pawn_operations_console")).status_code,
            403,
        )
        self.assertEqual(
            self.tenant_get(reverse("loans:pawn_operations_runbook")).status_code,
            403,
        )
        self.assertEqual(
            self.tenant_get(reverse("loans:document_layout_list")).status_code,
            403,
        )
        self.assertEqual(
            self.tenant_get(reverse("loans:document_layout_guide")).status_code,
            403,
        )
        self.assertEqual(
            self.tenant_get(reverse("loans:document_layout_designer", args=[1])).status_code,
            403,
        )

    def test_owner_can_open_document_layout_starter_guide(self):
        response = self.tenant_get(reverse("loans:document_layout_guide"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Create draft")
        self.assertContains(response, "Resolution order:")
        self.assertContains(response, "Series &rarr; License &rarr; Workspace")

    def test_owner_can_create_publish_and_assign_starter_ticket_layout(self):
        response = self.tenant_post(
            reverse("loans:document_layout_create"),
            {"name": "Counter ticket", "document_type": "loan_ticket"},
        )
        revision = LoanDocumentLayoutRevision.objects.select_related("layout").get(
            layout__name="Counter ticket"
        )
        self.assertEqual(revision.definition["schema_version"], 2)
        self.assertEqual(revision.definition["layout_mode"], "FLOW")
        self.assertRedirects(
            response,
            reverse("loans:document_layout_detail", args=[revision.pk]),
            fetch_redirect_response=False,
        )
        detail = self.tenant_get(
            reverse("loans:document_layout_detail", args=[revision.pk])
        )
        self.assertContains(detail, "Structured layout definition")
        self.assertContains(detail, "Publish and freeze")
        self.assertContains(detail, "Visual Flow editor")

        designer = self.tenant_get(
            reverse("loans:document_layout_designer", args=[revision.pk])
        )
        self.assertEqual(designer.status_code, 200)
        self.assertContains(designer, "Body blocks")
        add_block = self.tenant_post(
            reverse("loans:document_layout_designer", args=[revision.pk]),
            {
                "operation": "add_block", "block_type": "SPACER",
                "binding": "", "bindings": [], "text": "", "height_mm": 9,
            },
        )
        self.assertEqual(add_block.status_code, 302)
        revision.refresh_from_db()
        self.assertEqual(revision.definition["blocks"][-1]["type"], "spacer")
        save_settings = self.tenant_post(
            reverse("loans:document_layout_designer", args=[revision.pk]),
            {
                "operation": "save_settings", "page_size": "A5", "margin_mm": 10,
                "primary_color": "#7c2d12", "border_color": "#d6d3d1",
                "font_family": "HELVETICA", "body_font_size_pt": 9,
                "heading_font_size_pt": 16,
            },
        )
        self.assertEqual(save_settings.status_code, 302)
        revision.refresh_from_db()
        self.assertEqual(revision.definition["page_size"], "A5")
        self.assertEqual(revision.definition["page"]["margin_mm"], 10)

        definition = starter_layout("loan_ticket").canonical_dict()
        definition["name"] = "Updated counter ticket"
        update = self.tenant_post(
            reverse("loans:document_layout_update", args=[revision.pk]),
            {"definition": json.dumps(definition)},
        )
        self.assertEqual(update.status_code, 302)
        revision.refresh_from_db()
        self.assertEqual(revision.definition["name"], "Updated counter ticket")

        image_buffer = io.BytesIO()
        PillowImage.new("RGB", (20, 20), color="blue").save(image_buffer, format="PNG")
        upload = self.client.post(
            reverse("loans:document_layout_asset_add", args=[revision.pk]),
            {
                "key": "business.logo",
                "kind": "IMAGE",
                "file": SimpleUploadedFile("logo.png", image_buffer.getvalue(), content_type="image/png"),
            },
        )
        self.assertEqual(upload.status_code, 302)
        self.assertTrue(revision.assets.filter(key="business.logo").exists())

        response = self.tenant_post(
            reverse("loans:document_layout_publish", args=[revision.pk])
        )
        self.assertEqual(response.status_code, 302)
        revision.refresh_from_db()
        self.assertEqual(revision.state, "PUBLISHED")

        response = self.tenant_post(
            reverse("loans:document_layout_assign", args=[revision.pk]),
            {"license": "", "series": ""},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(revision.assignments.filter(is_active=True).exists())

    def test_published_ticket_layout_drives_official_issue_and_reprint(self):
        license, series = self._configured_setup()
        loan = self._loan(license, series, "PL-DOC-00001", state="APPROVED")
        PawnLoanApprovalSnapshot.objects.create(
            loan=loan,
            version=1,
            payload={
                "loan_number": loan.loan_number,
                "loan_date": str(loan.loan_date),
                "principal_amount": str(loan.principal_amount),
                "monthly_interest_rate": str(loan.monthly_interest_rate),
                "tenure_months": loan.tenure_months,
                "borrower_id": loan.borrower_id,
                "collateral": [],
            },
            fingerprint="ui-approval-fingerprint",
            approved_by=self.owner,
        )
        revision = LoanDocumentLayoutService.create_layout(
            workspace=self.tenant,
            document_type="loan_ticket",
            name=f"Issued ticket {uuid.uuid4().hex[:6]}",
            definition=starter_layout("loan_ticket").canonical_dict(),
            actor=self.owner,
        )
        revision = LoanDocumentLayoutService.publish(
            revision=revision, actor=self.owner
        )
        LoanDocumentLayoutService.assign(
            revision=revision,
            workspace=self.tenant,
            license=license,
            series=series,
            actor=self.owner,
        )

        preview = self.tenant_get(
            f"{reverse('loans:document_layout_preview', args=[revision.pk])}?loan={loan.pk}"
        )
        test_print = self.tenant_get(
            f"{reverse('loans:document_layout_preview', args=[revision.pk])}?loan={loan.pk}&download=1"
        )
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview["X-Rokkad-Preview"], "true")
        self.assertIn(b"PREVIEW / NOT AN OFFICIAL ISSUE", preview.content)
        self.assertTrue(test_print["Content-Disposition"].startswith("attachment"))

        url = reverse("loans:pawn_loan_ticket_pdf", args=[loan.pk])
        first = self.tenant_get(url)
        second = self.tenant_get(url)

        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.content.startswith(b"%PDF"))
        self.assertEqual(first["X-Rokkad-Document-Issue"], second["X-Rokkad-Document-Issue"])
        self.assertEqual(LoanDocumentIssue.objects.filter(source_id=str(loan.pk)).count(), 1)

        fixed = self.tenant_get(f"{url}?renderer=fixed")
        self.assertEqual(fixed.status_code, 200)
        self.assertNotIn("X-Rokkad-Document-Issue", fixed)

        clone_response = self.tenant_post(
            reverse("loans:document_layout_clone", args=[revision.pk])
        )
        self.assertEqual(clone_response.status_code, 302)
        self.assertTrue(revision.layout.revisions.filter(version=2, state="DRAFT").exists())
        retire_response = self.tenant_post(
            reverse("loans:document_layout_retire", args=[revision.pk])
        )
        self.assertEqual(retire_response.status_code, 302)
        revision.refresh_from_db()
        self.assertEqual(revision.state, "RETIRED")

    def _configured_setup(self):
        license = LoanLicense.objects.create(
            workspace=self.tenant,
            name="Configured License",
            license_number=f"PBL-{uuid.uuid4().hex[:8]}",
            issued_on=date(2026, 1, 1),
            expires_on=date(2027, 1, 1),
            created_by=self.owner,
        )
        series = LoanSeries.objects.create(
            license=license, name="Main", code="A"
        )
        for kind, prefix in (
            (LoanDocumentKind.PAWN_LOAN.value, "PL-A-"),
            (LoanDocumentKind.PAWN_LOAN_RELEASE.value, "RL-A-"),
        ):
            LoanNumberSequence.objects.create(
                series=series,
                document_kind=kind,
                prefix=prefix,
                width=5,
                maximum_number=10000,
            )
        return license, series

    def _loan(self, license, series, number, *, state="DRAFT"):
        return PawnLoan.objects.create(
            workspace=self.tenant,
            license=license,
            series=series,
            borrower=Party.objects.create(display_name=f"Borrower {number}"),
            loan_number=number,
            state=state,
            principal_amount=Decimal("10000.00"),
            monthly_interest_rate=Decimal("2.000000"),
            loan_date=date(2026, 8, 1),
            created_by=self.owner,
            updated_by=self.owner,
        )
