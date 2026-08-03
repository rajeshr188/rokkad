import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import override_settings
from django.urls import reverse
from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient

from apps.orgs.models import Membership, Role
from apps.tenant_apps.loans.domain import LoanDocumentKind
from apps.tenant_apps.loans.models import (
    LoanLicense,
    LoanNumberSequence,
    LoanSeries,
    PawnLoan,
    PawnLoanAccountingEvent,
    PawnLoanAccountingOutbox,
    PawnLoanRelease,
    PawnLoanReleaseItem,
)
from apps.tenant_apps.party.models import Party


@override_settings(
    ROOT_URLCONF="django_project.tenant_urls",
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)
class PawnDraftUiTests(TenantTestCase):
    test_schema_name = f"loans_draft_ui_{uuid.uuid4().hex[:8]}"
    test_domain = f"loans-draft-ui-{uuid.uuid4().hex[:8]}.test.com"

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
            username="pawn-draft-ui-owner",
            defaults={"email": "pawn-draft-ui-owner@example.com"},
        )
        tenant.name = f"Pawn Draft UI {uuid.uuid4().hex[:8]}"
        tenant.owner = owner
        tenant.creator = owner
        tenant.save()
        owner_role, _ = Role.objects.get_or_create(name="Owner")
        Membership.objects.get_or_create(user=owner, company=tenant, defaults={"role": owner_role})

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
        self.party = Party.objects.create(display_name="Draft Borrower")

    def test_create_is_blocked_with_clear_setup_action(self):
        response = self.client.get(reverse("loans:pawn_loan_create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "PawnLoan setup required")
        self.assertContains(response, "Open Loan Setup")
        self.assertContains(response, reverse("loans:license_list"))

    def test_staff_can_create_view_and_correct_a_draft_only(self):
        license, series = self._configured_setup()
        response = self.client.post(
            reverse("loans:pawn_loan_create"),
            self._payload(license, series),
        )

        loan = PawnLoan.objects.get()
        self.assertRedirects(
            response,
            reverse("loans:pawn_loan_detail", args=[loan.pk]),
            fetch_redirect_response=False,
        )
        self.assertEqual(loan.state, "DRAFT")
        self.assertEqual(loan.collateral_items.count(), 1)

        detail = self.client.get(reverse("loans:pawn_loan_detail", args=[loan.pk]))
        self.assertContains(detail, loan.loan_number)
        self.assertContains(detail, "Recommended next step")
        self.assertContains(detail, "Approve loan")
        self.assertNotContains(detail, "Loan ticket PDF")
        ticket = self.client.get(reverse("loans:pawn_loan_ticket_pdf", args=[loan.pk]))
        self.assertEqual(ticket.status_code, 409)

        payload = self._payload(license, series)
        payload["principal_amount"] = "12500.00"
        payload["collateral-0-description"] = "Corrected gold chain"
        response = self.client.post(reverse("loans:pawn_loan_update", args=[loan.pk]), payload)
        self.assertEqual(response.status_code, 302)
        loan.refresh_from_db()
        self.assertEqual(str(loan.principal_amount), "12500.00")
        self.assertEqual(loan.collateral_items.get().description, "Corrected gold chain")
        self.assertEqual(loan.change_log.count(), 2)

    def test_invalid_create_rerenders_without_consuming_number(self):
        license, series = self._configured_setup()
        payload = self._payload(license, series)
        payload["collateral-0-net_weight"] = "12.0000"
        response = self.client.post(reverse("loans:pawn_loan_create"), payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(PawnLoan.objects.count(), 0)
        sequence = LoanNumberSequence.objects.get(
            series=series, document_kind=LoanDocumentKind.PAWN_LOAN.value
        )
        self.assertEqual(sequence.next_number, 1)

    def test_internal_routes_are_not_added_to_primary_navigation(self):
        response = self.client.get(reverse("loans:license_list"))
        self.assertNotContains(response, reverse("loans:pawn_loan_list"))

    def test_internal_reports_render_all_operational_sections(self):
        license, series = self._configured_setup()
        self.client.post(reverse("loans:pawn_loan_create"), self._payload(license, series))

        response = self.client.get(reverse("loans:pawn_loan_reports"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Reports &amp; reconciliation")
        self.assertContains(response, "Actionable reconciliation")
        self.assertContains(response, "Active, due &amp; overdue")
        self.assertContains(response, "Finalized accruals")
        self.assertContains(response, "Repayments")
        self.assertContains(response, "Releases")
        self.assertContains(response, "Collateral custody")
        self.assertContains(response, "Posting health")

    def test_essential_pdf_routes_use_workspace_scoped_immutable_sources(self):
        license, series = self._configured_setup()
        self.client.post(reverse("loans:pawn_loan_create"), self._payload(license, series))
        loan = PawnLoan.objects.get()
        self.client.post(reverse("loans:pawn_loan_approve", args=[loan.pk]))
        repayment = PawnLoanAccountingEvent.objects.create(
            loan=loan,
            event_kind="REPAYMENT",
            effective_date=date(2026, 8, 3),
            payload={
                "values": {
                    "principal": "450",
                    "interest": "50",
                    "overdue_interest": "20",
                    "current_interest": "30",
                    "fees": "0",
                },
                "repayment": {"amount_received": "500"},
            },
            payload_fingerprint="receipt-fixture",
            idempotency_key="receipt-fixture",
            created_by=self.owner,
        )
        PawnLoanAccountingOutbox.objects.create(
            event=repayment,
            idempotency_key="receipt-fixture",
            payload=repayment.payload,
            payload_fingerprint="receipt-fixture",
            status="POSTED",
            dea_voucher_id=101,
            dea_journal_entry_id=102,
        )
        release_event = PawnLoanAccountingEvent.objects.create(
            loan=loan,
            event_kind="RELEASE_RECEIPT",
            effective_date=date(2026, 8, 3),
            payload={"values": {"principal": "10000", "interest": "0", "fees": "0"}},
            payload_fingerprint="release-fixture",
            idempotency_key="release-fixture",
            created_by=self.owner,
        )
        release = PawnLoanRelease.objects.create(
            workspace=self.tenant,
            loan=loan,
            release_number="RL-A-00001",
            request_key="release-document-fixture",
            effective_date=date(2026, 8, 3),
            is_full_release=True,
            settlement_amount=Decimal("10000"),
            principal_amount=Decimal("10000"),
            interest_amount=Decimal("0"),
            fee_amount=Decimal("0"),
            accounting_event=release_event,
            created_by=self.owner,
        )
        PawnLoanReleaseItem.objects.create(
            release=release,
            collateral_item=loan.collateral_items.get(),
            valuation_snapshot={"valuation_amount": "50000"},
        )

        routes = (
            reverse("loans:pawn_loan_ticket_pdf", args=[loan.pk]),
            reverse("loans:pawn_repayment_receipt_pdf", args=[loan.pk, repayment.pk]),
            reverse("loans:pawn_release_memo_pdf", args=[release.pk]),
        )
        for url in routes:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Content-Type"], "application/pdf")
            self.assertTrue(response.content.startswith(b"%PDF"))
            self.assertTrue(response["X-Rokkad-Verification-ID"].startswith("ROKKAD|"))

    def test_workspace_member_can_use_internal_draft_ui_but_not_setup(self):
        User = get_user_model()
        member = User.objects.create_user(
            username=f"pawn-staff-{uuid.uuid4().hex[:8]}",
            email=f"pawn-staff-{uuid.uuid4().hex[:8]}@example.com",
        )
        member_role, _ = Role.objects.get_or_create(name="Member")
        Membership.objects.create(user=member, company=self.tenant, role=member_role)
        self.client.force_login(member)

        self.assertEqual(self.client.get(reverse("loans:pawn_loan_list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("loans:license_list")).status_code, 403)

    def test_staff_can_approve_reopen_reapprove_and_cancel_through_ui(self):
        license, series = self._configured_setup()
        self.client.post(reverse("loans:pawn_loan_create"), self._payload(license, series))
        loan = PawnLoan.objects.get()

        response = self.client.post(reverse("loans:pawn_loan_approve", args=[loan.pk]))
        self.assertEqual(response.status_code, 302)
        loan.refresh_from_db()
        self.assertEqual(loan.state, "APPROVED")
        self.assertEqual(loan.approval_snapshots.count(), 1)

        response = self.client.post(
            reverse("loans:pawn_loan_reopen", args=[loan.pk]),
            {"reason": "Correct collateral valuation"},
        )
        self.assertEqual(response.status_code, 302)
        loan.refresh_from_db()
        self.assertEqual(loan.state, "DRAFT")
        self.client.post(reverse("loans:pawn_loan_approve", args=[loan.pk]))
        self.assertEqual(loan.approval_snapshots.count(), 2)

        response = self.client.post(
            reverse("loans:pawn_loan_cancel", args=[loan.pk]),
            {"reason": "Borrower withdrew"},
        )
        self.assertEqual(response.status_code, 302)
        loan.refresh_from_db()
        self.assertEqual(loan.state, "CANCELLED")

    def test_reason_form_does_not_transition_when_reason_is_missing(self):
        license, series = self._configured_setup()
        self.client.post(reverse("loans:pawn_loan_create"), self._payload(license, series))
        loan = PawnLoan.objects.get()

        response = self.client.post(reverse("loans:pawn_loan_cancel", args=[loan.pk]), {"reason": ""})
        self.assertEqual(response.status_code, 200)
        loan.refresh_from_db()
        self.assertEqual(loan.state, "DRAFT")

    def test_approved_detail_guides_staff_to_disbursal_and_dispatches_command(self):
        license, series = self._configured_setup()
        self.client.post(reverse("loans:pawn_loan_create"), self._payload(license, series))
        loan = PawnLoan.objects.get()
        self.client.post(reverse("loans:pawn_loan_approve", args=[loan.pk]))

        detail = self.client.get(reverse("loans:pawn_loan_detail", args=[loan.pk]))
        self.assertContains(detail, "Disburse loan")
        self.assertContains(detail, reverse("loans:pawn_loan_disburse", args=[loan.pk]))

        with patch("apps.tenant_apps.loans.views.disburse_pawn_loan") as command:
            response = self.client.post(
                reverse("loans:pawn_loan_disburse", args=[loan.pk]),
                {"effective_date": "2026-08-03"},
            )

        self.assertRedirects(
            response,
            reverse("loans:pawn_loan_detail", args=[loan.pk]),
            fetch_redirect_response=False,
        )
        command.assert_called_once_with(
            loan.pk,
            effective_date=date(2026, 8, 3),
            actor=self.owner,
        )

    def test_active_detail_exposes_complete_staff_lifecycle_and_repayment_command(self):
        license, series = self._configured_setup()
        self.client.post(reverse("loans:pawn_loan_create"), self._payload(license, series))
        loan = PawnLoan.objects.get()
        PawnLoan.objects.filter(pk=loan.pk).update(state="ACTIVE")
        balance = SimpleNamespace(
            principal_outstanding=Decimal("10000.00"),
            interest_outstanding=Decimal("200.00"),
            fees_outstanding=Decimal("0.00"),
            total_due=Decimal("10200.00"),
            posting_ready=True,
            posting_blockers=(),
        )
        with (
            patch("apps.tenant_apps.loans.views.get_pawn_loan_balance", return_value=balance),
            patch("apps.tenant_apps.loans.views.preview_pawn_loan_accruals", return_value=()),
        ):
            detail = self.client.get(reverse("loans:pawn_loan_detail", args=[loan.pk]))

        self.assertContains(detail, "Record repayment")
        self.assertContains(detail, "Accrue interest")
        self.assertContains(detail, "Partial release")
        self.assertContains(detail, "Full release")

        result = SimpleNamespace(
            allocation=SimpleNamespace(amount_received=Decimal("500.00"))
        )
        with patch(
            "apps.tenant_apps.loans.views.record_pawn_loan_repayment",
            return_value=result,
        ) as command:
            response = self.client.post(
                reverse("loans:pawn_loan_repay", args=[loan.pk]),
                {"amount": "500.00", "request_key": "ui-repayment-1"},
            )

        self.assertEqual(response.status_code, 302)
        command.assert_called_once_with(
            loan.pk,
            amount=Decimal("500.00"),
            request_key="ui-repayment-1",
            actor=self.owner,
        )

    def test_partial_release_previews_minimum_before_dispatch(self):
        license, series = self._configured_setup()
        self.client.post(reverse("loans:pawn_loan_create"), self._payload(license, series))
        loan = PawnLoan.objects.get()
        PawnLoan.objects.filter(pk=loan.pk).update(state="ACTIVE")
        collateral = loan.collateral_items.get()
        quote = SimpleNamespace(
            minimum_settlement=Decimal("2200.00"),
            fees_and_interest_settlement=Decimal("200.00"),
            principal_reduction_required=Decimal("2000.00"),
            blockers=(),
        )
        with (
            patch("apps.tenant_apps.loans.views._release_quote", return_value=quote),
            patch("apps.tenant_apps.loans.views.release_pawn_loan_partially") as command,
        ):
            response = self.client.post(
                reverse("loans:pawn_loan_release_partial", args=[loan.pk]),
                {
                    "selected_items": [collateral.pk],
                    "settlement_amount": "",
                    "request_key": "partial-preview-1",
                    "action": "preview",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "2200.00")
        self.assertContains(response, "Preview minimum")
        command.assert_not_called()

    def _configured_setup(self):
        license = LoanLicense.objects.create(
            workspace=self.tenant,
            name="UI License",
            license_number=f"PBL-{uuid.uuid4().hex[:8]}",
            issued_on=date(2026, 1, 1),
            expires_on=date(2027, 1, 1),
            created_by=self.owner,
        )
        series = LoanSeries.objects.create(license=license, name="Main", code="A")
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

    def _payload(self, license, series):
        return {
            "borrower": self.party.pk,
            "license": license.pk,
            "series": series.pk,
            "principal_amount": "10000.00",
            "monthly_interest_rate": "2.000000",
            "loan_date": "2026-07-18",
            "tenure_months": "3",
            "collateral-TOTAL_FORMS": "1",
            "collateral-INITIAL_FORMS": "0",
            "collateral-MIN_NUM_FORMS": "1",
            "collateral-MAX_NUM_FORMS": "1000",
            "collateral-0-description": "Gold chain",
            "collateral-0-metal": "GOLD",
            "collateral-0-gross_weight": "10.0000",
            "collateral-0-net_weight": "9.0000",
            "collateral-0-purity_percentage": "91.6000",
            "collateral-0-latest_appraised_value": "50000.00",
        }
