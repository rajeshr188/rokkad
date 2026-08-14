import uuid
import io
import json
import fitz
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
from apps.tenant_apps.loans.domain import CollateralCustodyState, CollateralMetal, LoanDocumentKind
from apps.tenant_apps.loans.domain.future_funding import FundingLoanState
from apps.tenant_apps.loans.models import (
    FundingLoan,
    FundingLoanCancellation,
    FundingLoanDraftCollateral,
    FundingLoanDraftTerms,
    FundingLoanSequence,
    LoanChangeLog,
    LoanLicense,
    LoanLicenseRevision,
    LoanMonitoringPolicy,
    LoanDocumentIssue,
    LoanDocumentLayout,
    LoanDocumentLayoutRevision,
    LoanDocumentPrintProfile,
    LoanDocumentPrintProfileRevision,
    LoanNumberSequence,
    LoanProduct,
    LoanProductVersion,
    LoanSeries,
    PawnLoan,
    PawnCollateralItem,
    PawnLoanApprovalSnapshot,
    PawnLoanAccountingEvent,
    PawnLoanAccountingOutbox,
    PawnLoanEconomicPolicy,
    PawnLoanNotice,
    PawnMetalInterestRatePolicy,
    PawnPhysicalVerificationSession,
    PawnStorageLocation,
)
from apps.tenant_apps.loans.views import _license_for_workspace
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.loans.tests.factories import ensure_test_product_version
from apps.orgs.models import Membership, Role
from PIL import Image as PillowImage
from apps.tenant_apps.loans.documents import built_in_print_profile, starter_layout
from apps.tenant_apps.loans.services import (
    LoanDocumentLayoutService,
    LoanDocumentPrintProfileService,
)


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

    def test_owner_can_seed_review_activate_and_retire_loan_products(self):
        response = self.tenant_post(reverse("loans:loan_product_seed_defaults"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(LoanProduct.objects.filter(workspace=self.tenant).count(), 4)
        version = LoanProductVersion.objects.get(product__workspace=self.tenant, product__code="GOLD-BULLET")
        page = self.tenant_get(reverse("loans:loan_product_list"))
        self.assertContains(page, "Single-payment bullet")
        self.assertContains(page, "Operational only; DPD date unchanged")

        response = self.tenant_post(reverse("loans:loan_product_version_activate", args=[version.pk]))
        self.assertEqual(response.status_code, 302)
        version.refresh_from_db()
        self.assertEqual(version.status, "ACTIVE")

        response = self.tenant_post(reverse("loans:loan_product_version_retire", args=[version.pk]))
        self.assertEqual(response.status_code, 302)
        version.refresh_from_db()
        self.assertEqual(version.status, "RETIRED")

    @patch("apps.tenant_apps.loans.views.refresh_loan_risk_snapshot")
    def test_owner_can_refresh_one_risk_snapshot_with_htmx_redirect(self, refresh):
        license, series = self._configured_setup()
        loan = self._loan(license, series, "PL-RISK-00001", state="ACTIVE")

        response = self.client.post(
            reverse("loans:pawn_risk_refresh_one", args=[loan.pk]),
            {"as_of": "2026-08-13"},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response["HX-Redirect"], reverse("loans:pawn_risk_portfolio"))
        refresh.assert_called_once_with(loan.pk, as_of_date=date(2026, 8, 13))

    @patch("apps.tenant_apps.loans.views.reassess_pawn_loans_batch")
    def test_owner_can_refresh_bounded_due_risk_batch(self, reassess):
        reassess.return_value = {"selected": 2, "current": 2, "errors": []}

        response = self.tenant_post(
            reverse("loans:pawn_risk_refresh_batch"),
            {"as_of": "2026-08-13"},
        )

        self.assertRedirects(
            response,
            reverse("loans:pawn_risk_portfolio"),
            fetch_redirect_response=False,
        )
        reassess.assert_called_once_with(
            workspace_id=self.tenant.pk,
            as_of_date=date(2026, 8, 13),
            batch_size=50,
        )

    @patch("apps.tenant_apps.loans.views.reassess_pawn_loans_batch")
    def test_owner_batch_risk_refresh_uses_htmx_redirect_response(self, reassess):
        reassess.return_value = {"selected": 1, "current": 1, "errors": []}

        response = self.client.post(
            reverse("loans:pawn_risk_refresh_batch"),
            {"as_of": "2026-08-13"},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 204)
        self.assertEqual(
            response["HX-Redirect"],
            reverse("loans:pawn_risk_portfolio"),
        )

    @patch("apps.tenant_apps.loans.views.reassess_pawn_loans_batch")
    def test_member_cannot_refresh_risk_monitoring(self, reassess):
        User = get_user_model()
        member = User.objects.create_user(
            username=f"risk-member-{uuid.uuid4().hex[:8]}",
            email=f"risk-member-{uuid.uuid4().hex[:8]}@example.com",
        )
        member_role, _ = Role.objects.get_or_create(name="Member")
        Membership.objects.create(
            user=member,
            company=self.tenant,
            role=member_role,
        )
        member_client = TenantClient(self.tenant)
        member_client.force_login(member)

        response = member_client.post(
            reverse("loans:pawn_risk_refresh_batch"),
            {"as_of": "2026-08-13"},
        )

        self.assertEqual(response.status_code, 403)
        reassess.assert_not_called()

    def test_document_issue_list_filters_and_paginates_immutable_evidence(self):
        def create_issue(sequence, **overrides):
            values = {
                "workspace": self.tenant,
                "document_type": "repayment_receipt",
                "issue_kind": LoanDocumentIssue.Kind.OFFICIAL,
                "source_type": "PawnLoanRepayment",
                "source_id": f"SOURCE-{sequence}",
                "source_fingerprint": f"fingerprint-{sequence}",
                "fixed_renderer_version": "test-v1",
                "payload_schema_version": 1,
                "payload_hash": f"payload-{sequence}",
                "pdf_hash": f"pdf-{sequence}",
                "artifact": SimpleUploadedFile(
                    f"issue-{sequence}.pdf",
                    b"%PDF-1.4 test evidence",
                    content_type="application/pdf",
                ),
                "issued_by": self.owner,
            }
            values.update(overrides)
            return LoanDocumentIssue.objects.create(**values)

        for sequence in range(51):
            create_issue(sequence)

        prior_issue = create_issue(
            "special-original",
            document_type="loan_ticket",
            source_type="PawnLoan",
            source_id="SPECIAL-LOAN",
        )
        special_issue = create_issue(
            "special-regenerated",
            document_type="loan_ticket",
            issue_kind=LoanDocumentIssue.Kind.REGENERATED,
            source_type="PawnLoan",
            source_id="SPECIAL-LOAN",
            prior_issue=prior_issue,
            print_profile_name="Special Profile",
            print_profile_version=1,
            print_profile_hash="profile-special",
            print_profile_source_scope=LoanDocumentIssue.PrintProfileSource.BUILT_IN,
        )
        issued_at = timezone.now() - timedelta(days=2)
        LoanDocumentIssue.objects.filter(pk=special_issue.pk).update(
            issued_at=issued_at
        )

        first_page = self.tenant_get(reverse("loans:document_issue_list"))
        self.assertEqual(first_page.status_code, 200)
        self.assertEqual(first_page.context["page_obj"].paginator.count, 53)
        self.assertEqual(len(first_page.context["issues"]), 50)

        receipt_page = self.client.get(
            reverse("loans:document_issue_list"),
            {"document_type": "repayment_receipt"},
        )
        self.assertEqual(receipt_page.context["page_obj"].paginator.count, 51)
        self.assertContains(
            receipt_page,
            "?document_type=repayment_receipt&amp;page=2",
        )
        receipt_page_two = self.client.get(
            reverse("loans:document_issue_list"),
            {"document_type": "repayment_receipt", "page": 2},
        )
        self.assertEqual(len(receipt_page_two.context["issues"]), 1)

        filtered = self.client.get(
            reverse("loans:document_issue_list"),
            {
                "q": "Special Profile",
                "document_type": "loan_ticket",
                "issue_kind": LoanDocumentIssue.Kind.REGENERATED,
                "profile_scope": LoanDocumentIssue.PrintProfileSource.BUILT_IN,
                "issued_date_from": issued_at.date().isoformat(),
                "issued_date_to": issued_at.date().isoformat(),
            },
        )
        self.assertEqual(list(filtered.context["issues"]), [special_issue])
        self.assertContains(filtered, "SPECIAL-LOAN")
        self.assertContains(filtered, "Built-in fallback")

        historical = self.client.get(
            reverse("loans:document_issue_list"),
            {"profile_scope": "NOT_RECORDED"},
        )
        self.assertEqual(historical.context["page_obj"].paginator.count, 52)

    def test_storage_and_verification_worklists_filter_hierarchy_and_paginate(self):
        branches = [
            PawnStorageLocation.objects.create(
                workspace=self.tenant,
                level=PawnStorageLocation.Level.BRANCH,
                code=f"BR-{sequence:03d}",
                name=f"Branch {sequence}",
                created_by=self.owner,
            )
            for sequence in range(51)
        ]
        special_branch = PawnStorageLocation.objects.create(
            workspace=self.tenant,
            level=PawnStorageLocation.Level.BRANCH,
            code="SPECIAL-BRANCH",
            name="Special Branch",
            created_by=self.owner,
        )
        special_vault = PawnStorageLocation.objects.create(
            workspace=self.tenant,
            parent=special_branch,
            level=PawnStorageLocation.Level.VAULT,
            code="SPECIAL-VAULT",
            name="Special Vault",
            created_by=self.owner,
        )
        special_cabinet = PawnStorageLocation.objects.create(
            workspace=self.tenant,
            parent=special_vault,
            level=PawnStorageLocation.Level.CABINET,
            code="SPECIAL-CABINET",
            name="Special Cabinet",
            created_by=self.owner,
        )
        special_box = PawnStorageLocation.objects.create(
            workspace=self.tenant,
            parent=special_cabinet,
            level=PawnStorageLocation.Level.BOX,
            code="SPECIAL-BOX",
            name="Special Box",
            created_by=self.owner,
        )
        special_slot = PawnStorageLocation.objects.create(
            workspace=self.tenant,
            parent=special_box,
            level=PawnStorageLocation.Level.SLOT,
            code="SPECIAL-SLOT",
            name="Special Slot",
            is_active=False,
            created_by=self.owner,
        )

        branch_page = self.client.get(
            reverse("loans:pawn_storage_location_list"),
            {"level": PawnStorageLocation.Level.BRANCH},
        )
        self.assertEqual(branch_page.context["page_obj"].paginator.count, 52)
        self.assertEqual(len(branch_page.context["locations"]), 50)
        self.assertContains(branch_page, "?level=BRANCH&amp;page=2")

        storage_filtered = self.client.get(
            reverse("loans:pawn_storage_location_list"),
            {
                "q": "Special Branch",
                "within": special_branch.pk,
                "level": PawnStorageLocation.Level.SLOT,
                "status": "INACTIVE",
            },
        )
        self.assertEqual(list(storage_filtered.context["locations"]), [special_slot])
        self.assertContains(storage_filtered, "SPECIAL-SLOT")

        for branch in branches:
            PawnPhysicalVerificationSession.objects.create(
                workspace=self.tenant,
                scope_location=branch,
                started_by=self.owner,
            )
        special_session = PawnPhysicalVerificationSession.objects.create(
            workspace=self.tenant,
            scope_location=special_slot,
            status=PawnPhysicalVerificationSession.Status.COMPLETED,
            started_by=self.owner,
            completed_by=self.owner,
            completed_at=timezone.now(),
        )
        started_date = timezone.localdate()

        open_sessions = self.client.get(
            reverse("loans:pawn_physical_verification_list"),
            {"status": PawnPhysicalVerificationSession.Status.OPEN},
        )
        self.assertEqual(open_sessions.context["page_obj"].paginator.count, 51)
        self.assertEqual(len(open_sessions.context["sessions"]), 50)
        self.assertContains(open_sessions, "?status=OPEN&amp;page=2")

        verification_filtered = self.client.get(
            reverse("loans:pawn_physical_verification_list"),
            {
                "q": "Special Branch",
                "within": special_branch.pk,
                "status": PawnPhysicalVerificationSession.Status.COMPLETED,
                "started_date_from": started_date.isoformat(),
                "started_date_to": started_date.isoformat(),
            },
        )
        self.assertEqual(
            list(verification_filtered.context["sessions"]),
            [special_session],
        )
        self.assertContains(verification_filtered, "SPECIAL-SLOT")

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
                "supporting_document": SimpleUploadedFile(
                    "license.pdf",
                    b"%PDF-1.4\n%%EOF",
                    content_type="application/pdf",
                ),
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
        self.assertContains(detail, "Loans Setup")

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
                "configuration-interest_method": "COMPOUND",
                "configuration-partial_month_method": "SLAB",
                "configuration-partial_month_cutoff_days": "15",
                "configuration-partial_month_lower_fraction": "0.5",
                "configuration-capitalization_interval_periods": "12",
                "configuration-accounting_recognition": "CASH",
                "configuration-rounding_method": "PER_ACCRUAL_PERIOD",
                "configuration-currency_quantum": "0.01",
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
        policy = PawnLoanEconomicPolicy.objects.get()
        self.assertEqual(policy.interest_method, "COMPOUND")
        self.assertEqual(policy.partial_month_method, "SLAB")
        self.assertEqual(policy.accounting_recognition, "CASH")
        self.assertEqual(PawnMetalInterestRatePolicy.objects.count(), 2)
        page = self.tenant_get(reverse("loans:pawn_economics_setup"))
        self.assertContains(page, "PawnLoan economic policies")
        self.assertContains(page, "Gold")
        self.assertContains(page, "Silver")
        self.assertContains(page, "Compound")
        self.assertContains(page, "Slab")

    def test_owner_can_add_workspace_monitoring_policy(self):
        response = self.tenant_post(
            reverse("loans:pawn_economics_setup"),
            {
                "action": "monitoring",
                "monitoring-license": "",
                "monitoring-effective_from": "2026-08-01",
                "monitoring-compliance_profile": "Owner-approved pilot",
                "monitoring-maturity_warning_days": "30",
                "monitoring-operational_grace_days": "3",
                "monitoring-dpd_watch_threshold": "1",
                "monitoring-dpd_substandard_threshold": "90",
                "monitoring-ltv_warning_ratio": "0.70",
                "monitoring-ltv_breach_ratio": "0.80",
                "monitoring-ltv_critical_ratio": "0.90",
                "monitoring-rate_freshness_days": "7",
                "monitoring-appraisal_freshness_days": "90",
            },
        )

        self.assertRedirects(
            response,
            reverse("loans:pawn_economics_setup"),
            fetch_redirect_response=False,
        )
        policy = LoanMonitoringPolicy.objects.get()
        self.assertEqual(policy.version, 1)
        self.assertEqual(policy.compliance_profile, "Owner-approved pilot")
        page = self.tenant_get(reverse("loans:pawn_economics_setup"))
        self.assertContains(page, "Owner-approved pilot")

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

    def test_owner_can_record_and_download_license_renewal_evidence(self):
        license, _ = self._configured_setup()
        response = self.tenant_post(
            reverse("loans:license_renew", args=[license.pk]),
            {
                "license_number": license.license_number,
                "issuing_authority": "Renewal Authority",
                "issued_on": "2027-01-02",
                "expires_on": "2028-01-01",
                "notes": "Renewed for pilot",
                "supporting_document": SimpleUploadedFile(
                    "renewal.pdf",
                    b"%PDF-1.4\n%%EOF",
                    content_type="application/pdf",
                ),
            },
        )

        self.assertRedirects(
            response,
            reverse("loans:license_detail", args=[license.pk]),
            fetch_redirect_response=False,
        )
        revision = license.revisions.get(kind=LoanLicenseRevision.Kind.RENEWAL)
        download = self.tenant_get(
            reverse(
                "loans:license_revision_document",
                args=[license.pk, revision.pk],
            )
        )
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download["X-Content-Type-Options"], "nosniff")
        self.assertEqual(download.content, b"%PDF-1.4\n%%EOF")

        register = self.tenant_get(reverse("loans:license_register_pdf"))
        self.assertEqual(register.status_code, 200)
        self.assertTrue(register.content.startswith(b"%PDF-"))

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

        runbook = self.tenant_get(reverse("loans:pawn_operations_runbook"))
        self.assertContains(runbook, "Scheduled risk reassessment")
        self.assertContains(runbook, "tenant_command reassess_pawn_loans")
        self.assertContains(runbook, "selected=0")
        self.assertContains(runbook, "non-zero process exit")

    def test_notice_and_delivery_diagnostics_filter_and_paginate(self):
        license, series = self._configured_setup()
        loan = self._loan(license, series, "PL-UP2-00001")
        scheduled_for = timezone.now()
        for sequence in range(51):
            PawnLoanNotice.objects.create(
                workspace=self.tenant,
                loan=loan,
                notice_kind="REPAYMENT_REMINDER",
                channel="EMAIL",
                request_key=f"up2-notice-{sequence}",
                scheduled_for=scheduled_for,
                recipient_name=f"Recipient {sequence}",
                recipient_email=f"recipient-{sequence}@example.com",
                payload_snapshot={},
                created_by=self.owner,
            )
        special_notice = PawnLoanNotice.objects.create(
            workspace=self.tenant,
            loan=loan,
            notice_kind="INTEREST_DUE",
            channel="EMAIL",
            request_key="up2-notice-special",
            scheduled_for=scheduled_for,
            recipient_name="Special Notice Recipient",
            recipient_email="special@example.com",
            payload_snapshot={},
            created_by=self.owner,
        )

        notice_page = self.client.get(
            reverse("loans:pawn_loan_notice_list"),
            {"notice_kind": "REPAYMENT_REMINDER"},
        )
        self.assertEqual(notice_page.context["page_obj"].paginator.count, 51)
        self.assertEqual(len(notice_page.context["notice_rows"]), 50)
        self.assertContains(
            notice_page,
            "?notice_kind=REPAYMENT_REMINDER&amp;page=2",
        )
        notice_filtered = self.client.get(
            reverse("loans:pawn_loan_notice_list"),
            {
                "q": "Special Notice Recipient",
                "notice_kind": "INTEREST_DUE",
                "channel": "EMAIL",
                "delivery_status": "MISSING",
                "scheduled_date_from": scheduled_for.date().isoformat(),
                "scheduled_date_to": scheduled_for.date().isoformat(),
            },
        )
        self.assertEqual(notice_filtered.context["page_obj"].paginator.count, 1)
        self.assertEqual(
            notice_filtered.context["notice_rows"][0].notice,
            special_notice,
        )
        self.assertEqual(notice_filtered.context["notice_rows"][0].status, "MISSING")
        self.assertContains(notice_filtered, "Missing")

        effective_date = date(2026, 8, 10)
        for sequence in range(51):
            event = PawnLoanAccountingEvent.objects.create(
                loan=loan,
                event_kind="DISBURSAL",
                effective_date=effective_date,
                payload={},
                payload_fingerprint=f"up2-event-fingerprint-{sequence}",
                idempotency_key=f"up2-event-{sequence}",
                created_by=self.owner,
            )
            PawnLoanAccountingOutbox.objects.create(
                event=event,
                idempotency_key=f"up2-outbox-{sequence}",
                payload={},
                payload_fingerprint=f"up2-outbox-fingerprint-{sequence}",
                status="FAILED",
                last_error=(
                    "SPECIAL DELIVERY FAILURE"
                    if sequence == 50
                    else f"Delivery failure {sequence}"
                ),
            )

        outbox_page = self.client.get(
            reverse("loans:pawn_operations_console"),
            {"status": "FAILED"},
        )
        self.assertEqual(outbox_page.context["page_obj"].paginator.count, 51)
        self.assertEqual(len(outbox_page.context["outboxes"]), 50)
        self.assertContains(outbox_page, "?status=FAILED&amp;page=2")
        outbox_filtered = self.client.get(
            reverse("loans:pawn_operations_console"),
            {
                "q": "SPECIAL DELIVERY FAILURE",
                "status": "FAILED",
                "event_kind": "DISBURSAL",
                "effective_date_from": effective_date.isoformat(),
                "effective_date_to": effective_date.isoformat(),
            },
        )
        self.assertEqual(outbox_filtered.context["page_obj"].paginator.count, 1)
        self.assertContains(outbox_filtered, "SPECIAL DELIVERY FAILURE")

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
            self.tenant_get(reverse("loans:pawn_risk_portfolio")).status_code,
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
            self.tenant_get(reverse("loans:document_print_profile_list")).status_code,
            403,
        )
        self.assertEqual(
            self.tenant_get(reverse("loans:document_issue_list")).status_code,
            403,
        )
        self.assertEqual(
            self.tenant_get(reverse("loans:pawn_loan_notice_list")).status_code,
            403,
        )
        self.assertEqual(
            self.tenant_get(reverse("loans:document_layout_designer", args=[1])).status_code,
            403,
        )
        self.assertEqual(
            self.tenant_get(reverse("loans:document_layout_overlay_designer", args=[1])).status_code,
            403,
        )
        self.assertEqual(
            self.tenant_get(reverse("loans:funding_loan_read_console")).status_code,
            403,
        )
        self.assertEqual(
            self.tenant_get(reverse("loans:funding_loan_read_detail", args=[1])).status_code,
            403,
        )
        self.assertEqual(
            self.tenant_get(reverse("loans:funding_loan_draft_create")).status_code,
            403,
        )
        self.assertEqual(
            self.tenant_get(reverse("loans:funding_loan_draft_inputs", args=[1])).status_code,
            403,
        )
        self.assertEqual(
            self.tenant_post(reverse("loans:funding_loan_draft_activate", args=[1]), {"confirmation": "ACTIVATE"}).status_code,
            403,
        )
        self.assertEqual(
            self.tenant_post(
                reverse("loans:funding_loan_repayment", args=[1]),
                {
                    "amount": "1.00",
                    "effective_date": "2026-08-08",
                    "request_key": str(uuid.uuid4()),
                },
            ).status_code,
            403,
        )
        self.assertEqual(
            self.tenant_post(
                reverse("loans:funding_loan_begin_settlement", args=[1]), {}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.tenant_post(
                reverse("loans:funding_loan_return_collateral", args=[1]),
                {
                    "collateral": ["1"],
                    "effective_date": "2026-08-08",
                    "request_key": str(uuid.uuid4()),
                },
            ).status_code,
            403,
        )
        self.assertEqual(
            self.tenant_post(
                reverse("loans:funding_loan_close", args=[1]),
                {"confirmation": "CLOSE"},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.tenant_post(
                reverse("loans:funding_loan_reverse_event", args=[1, 1]),
                {
                    "effective_date": "2026-08-08",
                    "reason": "Correction",
                    "request_key": str(uuid.uuid4()),
                },
            ).status_code,
            403,
        )
        self.assertEqual(
            self.tenant_get(reverse("loans:funding_loan_statement_pdf", args=[1])).status_code,
            403,
        )
        self.assertEqual(
            self.tenant_post(reverse("loans:funding_loan_draft_cancel", args=[1]), {"reason": "No"}).status_code,
            403,
        )

    def test_pilot_sensitive_routes_fail_at_the_http_permission_boundary(self):
        member = get_user_model().objects.create_user(
            username=f"pilot-boundary-member-{uuid.uuid4().hex[:8]}"
        )
        member_role, _ = Role.objects.get_or_create(name="Member")
        Membership.objects.create(user=member, company=self.tenant, role=member_role)
        self.client.force_login(member)

        administrator_routes = (
            ("get", reverse("loans:pawn_loan_reverse_event", args=[999, 999])),
            ("get", reverse("loans:pawn_loan_auction_initiate", args=[999])),
            ("post", reverse("loans:pawn_loan_auction_start", args=[999])),
            ("get", reverse("loans:pawn_loan_auction_cancel", args=[999])),
            ("get", reverse("loans:pawn_loan_auction_complete", args=[999])),
            ("get", reverse("loans:pawn_loan_auction_reverse", args=[999])),
            ("get", reverse("loans:pawn_loan_renewal_reverse", args=[999])),
        )
        owner_routes = (
            ("get", reverse("loans:pawn_storage_location_list")),
            ("get", reverse("loans:pawn_storage_location_create")),
            ("get", reverse("loans:pawn_storage_location_label", args=[999])),
            ("get", reverse("loans:pawn_storage_location_scan", args=[uuid.uuid4()])),
            ("get", reverse("loans:pawn_collateral_storage_transfer", args=[999, 999])),
            ("get", reverse("loans:pawn_physical_verification_list")),
            ("get", reverse("loans:pawn_physical_verification_detail", args=[999])),
            ("post", reverse("loans:pawn_physical_verification_complete", args=[999])),
            ("get", reverse("loans:pawn_physical_verification_resolve", args=[999])),
            ("post", reverse("loans:pawn_physical_verification_discrepancy_notice", args=[999])),
        )
        for method, url in administrator_routes + owner_routes:
            with self.subTest(method=method, url=url):
                response = getattr(self.client, method)(url)
                self.assertEqual(response.status_code, 403)

        admin = get_user_model().objects.create_user(
            username=f"pilot-boundary-admin-{uuid.uuid4().hex[:8]}"
        )
        admin_role, _ = Role.objects.get_or_create(name="Admin")
        Membership.objects.create(user=admin, company=self.tenant, role=admin_role)
        self.client.force_login(admin)
        for method, url in owner_routes:
            with self.subTest(role="Admin", method=method, url=url):
                response = getattr(self.client, method)(url)
                self.assertEqual(response.status_code, 403)
        self.assertEqual(
            self.client.get(
                reverse("loans:pawn_loan_auction_initiate", args=[999])
            ).status_code,
            404,
        )

    def test_owner_can_create_funding_draft_with_active_lender_only(self):
        active_lender = Party.objects.create(
            display_name="Active funding lender",
            status=Party.PartyStatus.ACTIVE,
        )
        inactive_lender = Party.objects.create(
            display_name="Inactive funding lender",
            status=Party.PartyStatus.INACTIVE,
        )
        create_url = reverse("loans:funding_loan_draft_create")

        page = self.tenant_get(create_url)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Active funding lender")
        self.assertNotContains(page, "Inactive funding lender")

        rejected = self.tenant_post(create_url, {"lender": inactive_lender.pk})
        self.assertEqual(rejected.status_code, 200)
        self.assertContains(rejected, "Select a valid choice")
        self.assertEqual(FundingLoan.objects.count(), 0)
        self.assertFalse(FundingLoanSequence.objects.exists())

        response = self.tenant_post(create_url, {"lender": active_lender.pk})
        funding_loan = FundingLoan.objects.get()

        self.assertRedirects(
            response,
            reverse("loans:funding_loan_read_detail", args=[funding_loan.pk]),
            fetch_redirect_response=False,
        )
        self.assertEqual(funding_loan.funding_number, "FL-000001")
        self.assertEqual(funding_loan.lender, active_lender)
        self.assertEqual(funding_loan.workspace, self.tenant)
        self.assertEqual(funding_loan.created_by, self.owner)

    def test_owner_can_complete_and_cancel_funding_draft_without_activation(self):
        lender = Party.objects.create(
            display_name="Draft completion lender",
            status=Party.PartyStatus.ACTIVE,
        )
        license, series = self._configured_setup()
        eligible_loan = self._loan(license, series, "PL-FUND-1", state="ACTIVE")
        ineligible_loan = self._loan(license, series, "PL-FUND-2", state="DRAFT")
        eligible_item = PawnCollateralItem.objects.create(
            loan=eligible_loan,
            description="Eligible gold chain",
            metal=CollateralMetal.GOLD.value,
            gross_weight=Decimal("10.0000"),
            net_weight=Decimal("9.0000"),
            purity_percentage=Decimal("91.6000"),
            latest_appraised_value=Decimal("10000.00"),
            custody_state=CollateralCustodyState.IN_VAULT.value,
        )
        PawnCollateralItem.objects.create(
            loan=ineligible_loan,
            description="Draft-loan gold ring",
            metal=CollateralMetal.GOLD.value,
            gross_weight=Decimal("5.0000"),
            net_weight=Decimal("4.5000"),
            purity_percentage=Decimal("91.6000"),
            latest_appraised_value=Decimal("5000.00"),
            custody_state=CollateralCustodyState.IN_VAULT.value,
        )
        self.tenant_post(reverse("loans:funding_loan_draft_create"), {"lender": lender.pk})
        funding_loan = FundingLoan.objects.get()
        inputs_url = reverse("loans:funding_loan_draft_inputs", args=[funding_loan.pk])

        page = self.tenant_get(inputs_url)
        self.assertContains(page, "Eligible gold chain")
        self.assertNotContains(page, "Draft-loan gold ring")

        response = self.tenant_post(
            inputs_url,
            {
                "principal_amount": "7000.00",
                "monthly_interest_rate": "1.500000",
                "activated_on": "2026-08-08",
                "maturity_on": "2026-11-08",
                "maximum_funding_ltv_ratio": "0.800000",
                "currency_quantum": "0.0100",
                "collateral": [eligible_item.pk],
            },
        )
        self.assertRedirects(
            response,
            reverse("loans:funding_loan_read_detail", args=[funding_loan.pk]),
            fetch_redirect_response=False,
        )
        funding_loan.refresh_from_db()
        self.assertEqual(funding_loan.state, FundingLoanState.DRAFT.value)
        self.assertTrue(FundingLoanDraftTerms.objects.filter(funding_loan=funding_loan).exists())
        self.assertTrue(FundingLoanDraftCollateral.objects.filter(funding_loan=funding_loan, collateral_item=eligible_item).exists())
        self.assertFalse(hasattr(funding_loan, "terms_snapshot"))
        eligible_item.refresh_from_db()
        self.assertEqual(eligible_item.custody_state, CollateralCustodyState.IN_VAULT.value)

        detail = self.tenant_get(reverse("loans:funding_loan_read_detail", args=[funding_loan.pk]))
        self.assertContains(detail, "pass the current activation policy")
        self.assertContains(detail, "Servicing and accounting remain unavailable")

        rejected = self.tenant_post(
            reverse("loans:funding_loan_draft_cancel", args=[funding_loan.pk]),
            {"reason": ""},
        )
        self.assertEqual(rejected.status_code, 302)
        funding_loan.refresh_from_db()
        self.assertEqual(funding_loan.state, FundingLoanState.DRAFT.value)

        self.tenant_post(
            reverse("loans:funding_loan_draft_cancel", args=[funding_loan.pk]),
            {"reason": "Lender withdrew the proposal"},
        )
        funding_loan.refresh_from_db()
        self.assertEqual(funding_loan.state, FundingLoanState.CANCELLED.value)
        cancellation = FundingLoanCancellation.objects.get(funding_loan=funding_loan)
        self.assertEqual(cancellation.reason, "Lender withdrew the proposal")
        self.assertEqual(cancellation.actor, self.owner)

    def test_owner_can_activate_saved_funding_draft_with_exact_confirmation(self):
        lender = Party.objects.create(
            display_name="Activation lender",
            status=Party.PartyStatus.ACTIVE,
        )
        license, series = self._configured_setup()
        pawn_loan = self._loan(license, series, "PL-ACTIVATE", state="ACTIVE")
        collateral = PawnCollateralItem.objects.create(
            loan=pawn_loan,
            description="Activation gold chain",
            metal=CollateralMetal.GOLD.value,
            gross_weight=Decimal("10.0000"),
            net_weight=Decimal("9.0000"),
            purity_percentage=Decimal("91.6000"),
            latest_appraised_value=Decimal("10000.00"),
            custody_state=CollateralCustodyState.IN_VAULT.value,
        )
        self.tenant_post(reverse("loans:funding_loan_draft_create"), {"lender": lender.pk})
        funding_loan = FundingLoan.objects.get()
        self.tenant_post(
            reverse("loans:funding_loan_draft_inputs", args=[funding_loan.pk]),
            {
                "principal_amount": "7000.00",
                "monthly_interest_rate": "1.500000",
                "activated_on": "2026-08-08",
                "maturity_on": "2026-11-08",
                "maximum_funding_ltv_ratio": "0.800000",
                "currency_quantum": "0.0100",
                "collateral": [collateral.pk],
            },
        )
        activate_url = reverse("loans:funding_loan_draft_activate", args=[funding_loan.pk])

        rejected = self.tenant_post(activate_url, {"confirmation": "activate"})
        self.assertEqual(rejected.status_code, 302)
        funding_loan.refresh_from_db()
        self.assertEqual(funding_loan.state, FundingLoanState.DRAFT.value)
        self.assertEqual(funding_loan.events.count(), 0)

        response = self.tenant_post(activate_url, {"confirmation": "ACTIVATE"})
        self.assertRedirects(
            response,
            reverse("loans:funding_loan_read_detail", args=[funding_loan.pk]),
            fetch_redirect_response=False,
        )
        funding_loan.refresh_from_db()
        collateral.refresh_from_db()
        self.assertEqual(funding_loan.state, FundingLoanState.ACTIVE.value)
        self.assertEqual(funding_loan.events.count(), 1)
        self.assertTrue(hasattr(funding_loan, "terms_snapshot"))
        self.assertTrue(hasattr(funding_loan, "pledge"))
        self.assertEqual(funding_loan.pledge.items.count(), 1)
        self.assertEqual(collateral.custody_state, CollateralCustodyState.WITH_FUNDING_LENDER.value)
        self.assertFalse(FundingLoanDraftTerms.objects.filter(funding_loan=funding_loan).exists())
        self.assertFalse(FundingLoanDraftCollateral.objects.filter(funding_loan=funding_loan).exists())
        detail = self.tenant_get(reverse("loans:funding_loan_read_detail", args=[funding_loan.pk]))
        self.assertContains(detail, "WITH_FUNDING_LENDER")
        self.assertNotContains(detail, "Activate and hand off collateral")

        repayment_url = reverse("loans:funding_loan_repayment", args=[funding_loan.pk])
        rejected = self.tenant_post(
            repayment_url,
            {
                "amount": "7000.01",
                "effective_date": "2026-09-08",
                "request_key": str(uuid.uuid4()),
            },
        )
        self.assertEqual(rejected.status_code, 302)
        self.assertEqual(funding_loan.events.count(), 1)

        request_key = str(uuid.uuid4())
        repayment = {
            "amount": "1000.00",
            "effective_date": "2026-09-08",
            "request_key": request_key,
        }
        self.tenant_post(repayment_url, repayment)
        self.tenant_post(repayment_url, repayment)
        self.assertEqual(funding_loan.events.count(), 2)
        repayment_event = funding_loan.events.get(operation="RECORD_REPAYMENT")
        self.assertEqual(repayment_event.principal_amount, Decimal("1000.0000"))
        self.assertEqual(repayment_event.interest_amount, Decimal("0.0000"))
        self.assertEqual(repayment_event.fee_amount, Decimal("0.0000"))
        self.assertEqual(repayment_event.actor, self.owner)

        for document_url in (
            reverse("loans:funding_loan_agreement_pdf", args=[funding_loan.pk]),
            reverse("loans:funding_loan_statement_pdf", args=[funding_loan.pk]),
            reverse(
                "loans:funding_loan_repayment_receipt_pdf",
                args=[funding_loan.pk, repayment_event.pk],
            ),
        ):
            document = self.tenant_get(document_url)
            self.assertEqual(document.status_code, 200)
            self.assertEqual(document["Content-Type"], "application/pdf")
            self.assertTrue(document.content.startswith(b"%PDF"))
            self.assertTrue(document["X-Rokkad-Verification-ID"])

        statement = self.tenant_get(
            reverse("loans:funding_loan_read_detail", args=[funding_loan.pk])
        )
        self.assertContains(statement, "Funding statement")
        self.assertContains(statement, "RECORD_REPAYMENT")
        self.assertContains(statement, "-1000.0000")
        self.assertContains(statement, "6000.0000")
        self.assertContains(statement, self.owner.username)

        correction_key = str(uuid.uuid4())
        correction_payload = {
            "effective_date": "2026-09-09",
            "reason": "Repayment was entered against the wrong source receipt",
            "request_key": correction_key,
        }
        correction_url = reverse(
            "loans:funding_loan_reverse_event",
            args=[funding_loan.pk, repayment_event.pk],
        )
        self.tenant_post(correction_url, correction_payload)
        self.tenant_post(correction_url, correction_payload)
        reversal = funding_loan.events.get(reversal_of=repayment_event)
        self.assertEqual(reversal.reason, correction_payload["reason"])
        self.assertEqual(reversal.actor, self.owner)
        self.assertEqual(funding_loan.events.filter(reversal_of=repayment_event).count(), 1)
        corrected_detail = self.tenant_get(
            reverse("loans:funding_loan_read_detail", args=[funding_loan.pk])
        )
        self.assertContains(corrected_detail, "Reversal")
        self.assertContains(corrected_detail, "7000.0000")

        self.tenant_post(
            repayment_url,
            {
                "amount": "1000.00",
                "effective_date": "2026-09-10",
                "request_key": str(uuid.uuid4()),
            },
        )

        active_detail = self.tenant_get(
            reverse("loans:funding_loan_read_detail", args=[funding_loan.pk])
        )
        self.assertContains(active_detail, "Settlement readiness")
        self.assertNotContains(active_detail, "Begin settlement review")
        self.assertNotContains(active_detail, "Return selected collateral")
        blocked_return = self.tenant_post(
            reverse("loans:funding_loan_return_collateral", args=[funding_loan.pk]),
            {
                "collateral": [str(collateral.pk)],
                "effective_date": "2026-09-08",
                "request_key": str(uuid.uuid4()),
            },
        )
        self.assertEqual(blocked_return.status_code, 302)
        self.assertEqual(funding_loan.returns.count(), 0)
        collateral.refresh_from_db()
        self.assertEqual(
            collateral.custody_state,
            CollateralCustodyState.WITH_FUNDING_LENDER.value,
        )

        self.tenant_post(
            repayment_url,
            {
                "amount": "6000.00",
                "effective_date": "2026-10-08",
                "request_key": str(uuid.uuid4()),
            },
        )
        settled_detail = self.tenant_get(
            reverse("loans:funding_loan_read_detail", args=[funding_loan.pk])
        )
        self.assertContains(settled_detail, "Begin settlement review")

        settlement_url = reverse(
            "loans:funding_loan_begin_settlement", args=[funding_loan.pk]
        )
        self.tenant_post(settlement_url, {})
        self.tenant_post(settlement_url, {})
        funding_loan.refresh_from_db()
        self.assertEqual(funding_loan.state, FundingLoanState.SETTLEMENT_PENDING.value)
        self.assertEqual(funding_loan.updated_by, self.owner)

        pending_detail = self.tenant_get(
            reverse("loans:funding_loan_read_detail", args=[funding_loan.pk])
        )
        self.assertContains(pending_detail, "Return selected collateral")
        self.assertNotContains(pending_detail, "Close FundingLoan")
        close_url = reverse("loans:funding_loan_close", args=[funding_loan.pk])
        self.tenant_post(close_url, {"confirmation": "CLOSE"})
        funding_loan.refresh_from_db()
        self.assertEqual(funding_loan.state, FundingLoanState.SETTLEMENT_PENDING.value)
        return_url = reverse(
            "loans:funding_loan_return_collateral", args=[funding_loan.pk]
        )
        return_key = str(uuid.uuid4())
        return_payload = {
            "collateral": [str(collateral.pk)],
            "effective_date": "2026-10-08",
            "request_key": return_key,
        }
        self.tenant_post(return_url, return_payload)
        self.tenant_post(return_url, return_payload)
        collateral.refresh_from_db()
        self.assertEqual(collateral.custody_state, CollateralCustodyState.IN_VAULT.value)
        self.assertEqual(funding_loan.returns.count(), 1)
        funding_return = funding_loan.returns.get()
        self.assertEqual(funding_return.actor, self.owner)
        self.assertEqual(funding_return.items.count(), 1)
        return_receipt = self.tenant_get(
            reverse(
                "loans:funding_loan_return_receipt_pdf",
                args=[funding_loan.pk, funding_return.pk],
            )
        )
        self.assertEqual(return_receipt.status_code, 200)
        self.assertEqual(return_receipt["Content-Type"], "application/pdf")
        self.assertTrue(return_receipt.content.startswith(b"%PDF"))
        self.assertIn(f"FundingReturn:{funding_return.pk}", return_receipt["X-Rokkad-Verification-ID"])

        ready_detail = self.tenant_get(
            reverse("loans:funding_loan_read_detail", args=[funding_loan.pk])
        )
        self.assertTrue(ready_detail.context["settlement"].financially_settled)
        self.assertTrue(ready_detail.context["settlement"].collateral_returned)
        self.assertTrue(ready_detail.context["settlement"].closure_ready)
        self.assertContains(ready_detail, "Financially settled:")
        self.assertContains(ready_detail, "Collateral returned:")
        self.assertContains(ready_detail, "RETURN_COLLATERAL")
        self.assertNotContains(ready_detail, "Return selected collateral")
        self.assertContains(ready_detail, "Close FundingLoan")

        self.tenant_post(close_url, {"confirmation": "close"})
        funding_loan.refresh_from_db()
        self.assertEqual(funding_loan.state, FundingLoanState.SETTLEMENT_PENDING.value)
        self.tenant_post(close_url, {"confirmation": "CLOSE"})
        self.tenant_post(close_url, {"confirmation": "CLOSE"})
        funding_loan.refresh_from_db()
        self.assertEqual(funding_loan.state, FundingLoanState.CLOSED.value)
        self.assertEqual(funding_loan.updated_by, self.owner)

        closed_detail = self.tenant_get(
            reverse("loans:funding_loan_read_detail", args=[funding_loan.pk])
        )
        self.assertContains(closed_detail, "CLOSED")
        self.assertNotContains(closed_detail, "Record repayment")
        self.assertNotContains(closed_detail, "Begin settlement review")
        self.assertNotContains(closed_detail, "Return selected collateral")
        self.assertNotContains(closed_detail, "Close FundingLoan")

    def test_owner_can_open_read_only_funding_console_and_detail(self):
        summary = type(
            "Summary",
            (),
            {
                "funding_loan_id": 41,
                "funding_number": "FL-000041",
                "lender_name": "Funding lender",
                "state": "ACTIVE",
                "principal_outstanding": Decimal("7000.0000"),
                "interest_outstanding": Decimal("90.0000"),
                "fees_outstanding": Decimal("10.0000"),
                "total_due": Decimal("7100.0000"),
                "active_collateral_count": 2,
            },
        )()
        finding = type(
            "Finding",
            (),
            {
                "code": "CUSTODY_TIMELINE",
                "funding_loan_id": 41,
                "object_type": "collateral_item",
                "object_id": 9,
                "message": "Latest custody evidence does not match the projection.",
            },
        )()
        detail = type(
            "Detail",
            (),
            {
                "summary": summary,
                "activated_on": date(2026, 8, 8),
                "maturity_on": date(2026, 11, 8),
                "monthly_interest_rate": Decimal("1.500000"),
                "maximum_funding_ltv_ratio": Decimal("0.800000"),
                "collateral": (),
                "timeline": (),
            },
        )()

        with patch(
            "apps.tenant_apps.loans.web.funding.get_funding_loan_summaries",
            return_value=(summary,),
        ), patch(
            "apps.tenant_apps.loans.web.funding.get_funding_loan_integrity_findings",
            return_value=(finding,),
        ):
            response = self.tenant_get(reverse("loans:funding_loan_read_console"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "FundingLoan read console")
        self.assertContains(response, "FL-000041")
        self.assertContains(response, "CUSTODY_TIMELINE")
        self.assertContains(response, "Controlled MVP preview")

        with patch(
            "apps.tenant_apps.loans.web.funding.get_funding_loan_detail",
            return_value=detail,
        ):
            response = self.tenant_get(
                reverse("loans:funding_loan_read_detail", args=[41])
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Funding lender")
        self.assertContains(response, "Operational balance")

    def test_funding_read_detail_returns_404_for_unknown_workspace_loan(self):
        response = self.tenant_get(
            reverse("loans:funding_loan_read_detail", args=[999999])
        )

        self.assertEqual(response.status_code, 404)

    def test_owner_can_open_document_layout_starter_guide(self):
        response = self.tenant_get(reverse("loans:document_layout_guide"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Understand the LPD7 boundary")
        self.assertContains(response, "Print profile owns")
        self.assertContains(response, "Resolution order:")
        self.assertContains(response, "Series &rarr; License &rarr; Workspace")
        self.assertContains(response, "Profile resolution:")
        self.assertContains(response, "Series &rarr; Workspace")
        self.assertContains(response, "Issued documents")
        self.assertContains(response, "?print_profile=legacy")

    def test_owner_can_create_publish_and_assign_starter_ticket_layout(self):
        response = self.tenant_post(
            reverse("loans:document_layout_create"),
            {"name": "Counter ticket", "document_type": "loan_ticket"},
        )
        revision = LoanDocumentLayoutRevision.objects.select_related("layout").get(
            layout__name="Counter ticket"
        )
        self.assertEqual(revision.definition["schema_version"], 3)
        self.assertEqual(revision.definition["layout_mode"], "FLOW")
        self.assertNotIn("copy_mode", revision.definition)
        self.assertNotIn("sheet", revision.definition)
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

        downgrade = self.tenant_post(
            reverse("loans:document_layout_update", args=[revision.pk]),
            {"definition": json.dumps(
                starter_layout("loan_ticket", schema_version=2).canonical_dict()
            )},
        )
        self.assertEqual(downgrade.status_code, 302)
        revision.refresh_from_db()
        self.assertEqual(revision.definition["schema_version"], 3)

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

        definition = starter_layout("loan_ticket", schema_version=3).canonical_dict()
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

    def test_owner_can_create_absolute_overlay_starter_draft(self):
        response = self.tenant_post(
            reverse("loans:document_layout_create"),
            {
                "name": "Existing form ticket", "document_type": "loan_ticket",
                "layout_mode": "ABSOLUTE_OVERLAY",
            },
        )

        revision = LoanDocumentLayoutRevision.objects.get(layout__name="Existing form ticket")
        self.assertRedirects(
            response, reverse("loans:document_layout_detail", args=[revision.pk]),
            fetch_redirect_response=False,
        )
        self.assertEqual(revision.definition["layout_mode"], "ABSOLUTE_OVERLAY")
        self.assertEqual(revision.definition["background_asset_key"], "form.background")
        detail = self.tenant_get(reverse("loans:document_layout_detail", args=[revision.pk]))
        self.assertNotContains(detail, "Visual Flow editor")
        self.assertContains(detail, "Visual overlay editor")

        pdf = fitz.open()
        page = pdf.new_page()
        page.insert_text((30, 30), "FORM BACKGROUND")
        background_bytes = pdf.tobytes()
        pdf.close()
        upload = self.client.post(
            reverse("loans:document_layout_asset_add", args=[revision.pk]),
            {
                "key": "form.background", "kind": "BACKGROUND",
                "file": SimpleUploadedFile("form.pdf", background_bytes, content_type="application/pdf"),
            },
        )
        self.assertEqual(upload.status_code, 302)
        editor_url = reverse("loans:document_layout_overlay_designer", args=[revision.pk])
        editor = self.tenant_get(editor_url)
        self.assertEqual(editor.status_code, 200)
        self.assertContains(editor, "Drag a rectangle")
        self.assertContains(editor, "Physical paper, imposition, sequence, and duplex behavior belong to Print profiles")
        self.assertNotContains(editor, "Legacy copy mode")
        self.assertNotContains(editor, "Sheet composition")
        background = self.tenant_get(
            reverse("loans:document_layout_overlay_background", args=[revision.pk])
        )
        self.assertEqual(background.status_code, 200)
        self.assertEqual(background["Content-Type"], "image/png")

        title = revision.definition["blocks"][0]
        move = self.tenant_post(editor_url, {
            "operation": "save_block", "index": 0, "block_type": "title",
            "binding": "", "asset_key": "", "text": title.get("text", ""),
            "x_mm": 20, "y_mm": title["y_mm"], "width_mm": title["width_mm"],
            "height_mm": title["height_mm"], "font_size_pt": title["font_size_pt"],
            "align": title["align"],
        })
        self.assertEqual(move.status_code, 302)
        revision.refresh_from_db()
        self.assertEqual(revision.definition["blocks"][0]["x_mm"], 20)

    def test_published_ticket_layout_drives_official_issue_and_reprint(self):
        license, series = self._configured_setup()
        loan = self._loan(license, series, "PL-DOC-00001", state="APPROVED")
        approval_payload = {
            "loan_number": loan.loan_number,
            "loan_date": str(loan.loan_date),
            "principal_amount": str(loan.principal_amount),
            "monthly_interest_rate": str(loan.monthly_interest_rate),
            "tenure_months": loan.tenure_months,
            "borrower_id": loan.borrower_id,
            "collateral": [],
        }
        PawnLoanApprovalSnapshot.objects.create(
            loan=loan,
            version=1,
            payload=approval_payload,
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
        self.assertEqual(first["X-Rokkad-Print-Profile"], "Built-in A5 Both Simplex")
        self.assertEqual(first["X-Rokkad-Print-Profile-Hash"], second["X-Rokkad-Print-Profile-Hash"])
        self.assertEqual(LoanDocumentIssue.objects.filter(source_id=str(loan.pk)).count(), 1)
        issue = LoanDocumentIssue.objects.get(source_id=str(loan.pk))
        self.assertEqual(issue.print_profile_source_scope, "BUILT_IN")
        self.assertEqual(issue.print_profile_hash, first["X-Rokkad-Print-Profile-Hash"])
        evidence = self.tenant_get(
            reverse("loans:document_issue_detail", args=[issue.pk])
        )
        self.assertContains(evidence, "Built-in A5 Both Simplex")
        artifact = self.tenant_get(
            reverse("loans:document_issue_artifact", args=[issue.pk])
        )
        self.assertEqual(artifact.content, first.content)
        self.assertEqual(artifact["X-Rokkad-PDF-Hash"], issue.pdf_hash)

        profile_definition = built_in_print_profile(
            "A4_SIDE_BY_SIDE"
        ).canonical_dict()
        profile_definition["name"] = "Series counter A4"
        profile_revision = LoanDocumentPrintProfileService.create_profile(
            workspace=self.tenant,
            document_type="loan_ticket",
            name="Series counter A4",
            definition=profile_definition,
            actor=self.owner,
        )
        profile_revision = LoanDocumentPrintProfileService.publish(
            revision=profile_revision, actor=self.owner
        )
        LoanDocumentPrintProfileService.assign(
            revision=profile_revision,
            workspace=self.tenant,
            series=series,
            actor=self.owner,
        )

        unchanged_reprint = self.tenant_get(url)
        self.assertEqual(
            unchanged_reprint["X-Rokkad-Document-Issue"],
            first["X-Rokkad-Document-Issue"],
        )
        self.assertEqual(unchanged_reprint.content, first.content)

        PawnLoanApprovalSnapshot.objects.create(
            loan=loan,
            version=2,
            payload=approval_payload,
            fingerprint="ui-approval-fingerprint-2",
            approved_by=self.owner,
        )
        future = self.tenant_get(url)
        self.assertEqual(future.status_code, 200)
        self.assertNotEqual(
            future["X-Rokkad-Document-Issue"], first["X-Rokkad-Document-Issue"]
        )
        self.assertEqual(future["X-Rokkad-Print-Profile"], "Series counter A4")
        future_issue = LoanDocumentIssue.objects.get(
            pk=future["X-Rokkad-Document-Issue"]
        )
        self.assertEqual(future_issue.print_profile_source_scope, "SERIES")
        self.assertEqual(
            future_issue.print_profile_revision_id, profile_revision.pk
        )
        future_pdf = fitz.open(stream=future.content, filetype="pdf")
        self.assertEqual(len(future_pdf), 1)
        self.assertGreater(future_pdf[0].rect.width, future_pdf[0].rect.height)
        future_pdf.close()

        PawnLoanApprovalSnapshot.objects.create(
            loan=loan,
            version=3,
            payload=approval_payload,
            fingerprint="ui-approval-fingerprint-3",
            approved_by=self.owner,
        )
        legacy = self.tenant_get(f"{url}?print_profile=legacy")
        self.assertEqual(legacy.status_code, 200)
        self.assertEqual(
            legacy["X-Rokkad-Print-Profile"],
            "Legacy embedded Legacy Original",
        )
        legacy_issue = LoanDocumentIssue.objects.get(
            pk=legacy["X-Rokkad-Document-Issue"]
        )
        self.assertEqual(
            legacy_issue.print_profile_source_scope, "LEGACY_LAYOUT"
        )

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

    def test_schema_v3_ticket_issue_requires_and_records_resolved_profile(self):
        license, series = self._configured_setup()
        loan = self._loan(license, series, "PL-DOC-V3-00001", state="APPROVED")
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
            fingerprint="schema-v3-approval-fingerprint",
            approved_by=self.owner,
        )
        revision = LoanDocumentLayoutService.create_layout(
            workspace=self.tenant,
            document_type="loan_ticket",
            name=f"Logical ticket {uuid.uuid4().hex[:6]}",
            definition=starter_layout(
                "loan_ticket", schema_version=3
            ).canonical_dict(),
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

        ticket_url = reverse("loans:pawn_loan_ticket_pdf", args=[loan.pk])
        blocked_legacy = self.tenant_get(f"{ticket_url}?print_profile=legacy")
        self.assertEqual(blocked_legacy.status_code, 409)
        self.assertContains(
            blocked_legacy, "no embedded physical composition", status_code=409
        )
        self.assertFalse(LoanDocumentIssue.objects.filter(source_id=str(loan.pk)).exists())

        response = self.tenant_get(ticket_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Rokkad-Print-Profile"], "Built-in A5 Both Simplex")
        issue = LoanDocumentIssue.objects.get(source_id=str(loan.pk))
        self.assertEqual(issue.revision_id, revision.pk)
        self.assertEqual(issue.print_profile_source_scope, "BUILT_IN")
        self.assertTrue(issue.print_profile_hash)

    def test_owner_can_manage_assign_preview_and_retire_print_profile(self):
        license, series = self._configured_setup()
        loan = self._loan(license, series, "PL-PROFILE-00001", state="APPROVED")
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
            fingerprint="profile-ui-approval",
            approved_by=self.owner,
        )
        layout_definition = starter_layout("loan_ticket").canonical_dict()
        layout_definition["copy_mode"] = "ORIGINAL_DUPLICATE"
        layout_revision = LoanDocumentLayoutService.create_layout(
            workspace=self.tenant,
            document_type="loan_ticket",
            name=f"Profile preview layout {uuid.uuid4().hex[:6]}",
            definition=layout_definition,
            actor=self.owner,
        )
        layout_revision = LoanDocumentLayoutService.publish(
            revision=layout_revision, actor=self.owner
        )
        LoanDocumentLayoutService.assign(
            revision=layout_revision,
            workspace=self.tenant,
            series=series,
            actor=self.owner,
        )

        create = self.tenant_post(
            reverse("loans:document_print_profile_create"),
            {
                "name": "Front counter profile",
                "composition": "A5_BOTH_SIMPLEX",
                "scaling_policy": "FIT_PRINTABLE_AREA",
                "flip_edge_guidance": "NOT_APPLICABLE",
                "printer_guidance": "Load A5 paper in tray 2.",
            },
        )
        profile_revision = LoanDocumentPrintProfileRevision.objects.get(
            profile__name="Front counter profile", version=1
        )
        self.assertRedirects(
            create,
            reverse(
                "loans:document_print_profile_detail",
                args=[profile_revision.pk],
            ),
            fetch_redirect_response=False,
        )
        detail = self.tenant_get(
            reverse("loans:document_print_profile_detail", args=[profile_revision.pk])
        )
        self.assertContains(detail, "Front counter profile")
        self.assertContains(detail, "Preview and test print")

        preview_url = reverse(
            "loans:document_print_profile_preview", args=[profile_revision.pk]
        )
        preview = self.tenant_get(
            f"{preview_url}?layout={layout_revision.pk}&loan={loan.pk}"
        )
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview["X-Rokkad-Preview"], "true")
        self.assertEqual(preview["X-Rokkad-Print-Profile"], "Front counter profile")
        preview_pdf = fitz.open(stream=preview.content, filetype="pdf")
        self.assertEqual(len(preview_pdf), 2)
        preview_pdf.close()

        update = self.tenant_post(
            reverse("loans:document_print_profile_update", args=[profile_revision.pk]),
            {
                "composition": "A4_SIDE_BY_SIDE",
                "scaling_policy": "FIT_PRINTABLE_AREA",
                "flip_edge_guidance": "NOT_APPLICABLE",
                "printer_guidance": "Use landscape A4.",
            },
        )
        self.assertEqual(update.status_code, 302)
        profile_revision.refresh_from_db()
        self.assertEqual(
            profile_revision.definition["composition"], "A4_SIDE_BY_SIDE"
        )

        self.tenant_post(
            reverse("loans:document_print_profile_publish", args=[profile_revision.pk])
        )
        profile_revision.refresh_from_db()
        self.assertEqual(profile_revision.state, "PUBLISHED")
        assign = self.tenant_post(
            reverse("loans:document_print_profile_assign", args=[profile_revision.pk]),
            {"series": series.pk},
        )
        self.assertEqual(assign.status_code, 302)
        self.assertTrue(
            profile_revision.assignments.filter(
                series=series, is_active=True
            ).exists()
        )

        test_print = self.tenant_get(
            f"{preview_url}?layout={layout_revision.pk}&loan={loan.pk}&download=1"
        )
        self.assertTrue(test_print["Content-Disposition"].startswith("attachment"))
        test_pdf = fitz.open(stream=test_print.content, filetype="pdf")
        self.assertEqual(len(test_pdf), 1)
        self.assertGreater(test_pdf[0].rect.width, test_pdf[0].rect.height)
        test_pdf.close()

        clone = self.tenant_post(
            reverse("loans:document_print_profile_clone", args=[profile_revision.pk])
        )
        cloned_revision = LoanDocumentPrintProfileRevision.objects.get(
            profile=profile_revision.profile, version=2
        )
        self.assertRedirects(
            clone,
            reverse(
                "loans:document_print_profile_detail", args=[cloned_revision.pk]
            ),
            fetch_redirect_response=False,
        )
        self.assertEqual(cloned_revision.state, "DRAFT")

        self.tenant_post(
            reverse("loans:document_print_profile_retire", args=[profile_revision.pk])
        )
        profile_revision.refresh_from_db()
        self.assertEqual(profile_revision.state, "RETIRED")
        self.assertFalse(profile_revision.assignments.filter(is_active=True).exists())
        self.assertEqual(
            LoanDocumentPrintProfile.objects.filter(
                workspace=self.tenant, name="Front counter profile"
            ).count(),
            1,
        )

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
            product_version=ensure_test_product_version(self.tenant),
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
