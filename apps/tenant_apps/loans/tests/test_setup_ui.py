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
from apps.tenant_apps.loans.domain.future_funding import FUNDING_LOAN_RUNTIME_SUPPORTED, FundingLoanState
from apps.tenant_apps.loans.models import (
    FundingLoan,
    FundingLoanCancellation,
    FundingLoanDraftCollateral,
    FundingLoanDraftTerms,
    FundingLoanSequence,
    LoanChangeLog,
    LoanLicense,
    LoanLicenseRevision,
    LoanDocumentIssue,
    LoanDocumentLayout,
    LoanDocumentLayoutRevision,
    LoanNumberSequence,
    LoanSeries,
    PawnLoan,
    PawnCollateralItem,
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
        self.assertFalse(FUNDING_LOAN_RUNTIME_SUPPORTED)

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
        self.assertFalse(FUNDING_LOAN_RUNTIME_SUPPORTED)

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
        self.assertFalse(FUNDING_LOAN_RUNTIME_SUPPORTED)

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
            "apps.tenant_apps.loans.views.get_funding_loan_summaries",
            return_value=(summary,),
        ), patch(
            "apps.tenant_apps.loans.views.get_funding_loan_integrity_findings",
            return_value=(finding,),
        ):
            response = self.tenant_get(reverse("loans:funding_loan_read_console"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "FundingLoan read console")
        self.assertContains(response, "FL-000041")
        self.assertContains(response, "CUSTODY_TIMELINE")
        self.assertContains(response, "Controlled MVP preview")

        with patch(
            "apps.tenant_apps.loans.views.get_funding_loan_detail",
            return_value=detail,
        ):
            response = self.tenant_get(
                reverse("loans:funding_loan_read_detail", args=[41])
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Funding lender")
        self.assertContains(response, "Operational balance")
        self.assertFalse(FUNDING_LOAN_RUNTIME_SUPPORTED)

    def test_funding_read_detail_returns_404_for_unknown_workspace_loan(self):
        response = self.tenant_get(
            reverse("loans:funding_loan_read_detail", args=[999999])
        )

        self.assertEqual(response.status_code, 404)

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
