import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django_tenants.test.cases import TenantTestCase

from apps.tenant_apps.loans.domain import (
    CollateralMetal,
    LoanDocumentKind,
    LoanOutboxStatus,
    PawnLoanEventKind,
    PawnLoanState,
    TransactionKind,
)
from apps.tenant_apps.loans.models import (
    LoanLicense,
    LoanNumberSequence,
    LoanPolicySnapshot,
    LoanSeries,
    PawnLoanAccountingEvent,
)
from apps.tenant_apps.loans.services import (
    CollateralDraftInput,
    CreatePawnDraftCommand,
    PawnDisbursalError,
    approve_pawn_loan,
    assert_pawn_loan_financial_actions_allowed,
    create_pawn_draft,
    deliver_outbox_event,
    disburse_pawn_loan,
)
from apps.tenant_apps.party.models import Party


class PawnDisbursalServiceTests(TenantTestCase):
    test_schema_name = f"loans_disbursal_{uuid.uuid4().hex[:8]}"
    test_domain = f"loans-disbursal-{uuid.uuid4().hex[:8]}.test.com"

    @classmethod
    def get_test_schema_name(cls):
        return cls.test_schema_name

    @classmethod
    def get_test_tenant_domain(cls):
        return cls.test_domain

    @classmethod
    def setup_tenant(cls, tenant):
        owner, _ = get_user_model().objects.get_or_create(
            username="loans-disbursal-owner",
            defaults={"email": "loans-disbursal-owner@example.com"},
        )
        tenant.name = f"Loans Disbursal {uuid.uuid4().hex[:8]}"
        tenant.owner = owner
        tenant.creator = owner

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        self.actor = get_user_model().objects.create_user(
            username=f"disbursal-{uuid.uuid4().hex[:8]}",
            email=f"disbursal-{uuid.uuid4().hex[:8]}@example.com",
        )
        borrower = Party.objects.create(display_name="Disbursal Borrower")
        license = LoanLicense.objects.create(
            workspace=self.tenant,
            name="Disbursal License",
            license_number=f"PBL-{uuid.uuid4().hex[:8]}",
            issued_on=date(2026, 1, 1),
            expires_on=date(2027, 1, 1),
        )
        series = LoanSeries.objects.create(license=license, name="Main", code="A")
        LoanNumberSequence.objects.create(
            series=series,
            document_kind=LoanDocumentKind.PAWN_LOAN.value,
            prefix="PL-A-",
            width=5,
            maximum_number=10000,
        )
        self.loan = create_pawn_draft(
            CreatePawnDraftCommand(
                workspace_id=self.tenant.pk,
                borrower_id=borrower.pk,
                license_id=license.pk,
                series_id=series.pk,
                principal_amount=Decimal("50000.00"),
                monthly_interest_rate=Decimal("2.000000"),
                loan_date=date(2026, 8, 3),
                tenure_months=3,
                collateral=(
                    CollateralDraftInput(
                        description="Gold",
                        metal=CollateralMetal.GOLD,
                        gross_weight=Decimal("10"),
                        net_weight=Decimal("9"),
                        purity_percentage=Decimal("91.6"),
                        latest_appraised_value=Decimal("50000"),
                    ),
                ),
            ),
            actor=self.actor,
        )
        approve_pawn_loan(self.loan.pk, actor=self.actor)

    @patch("apps.tenant_apps.loans.services.pawn_disbursal.require_pawn_loan_accounting_readiness")
    def test_disbursal_is_atomic_and_creates_immutable_policy_and_outbox(self, readiness):
        result = disburse_pawn_loan(
            self.loan.pk,
            effective_date=date(2026, 8, 3),
            actor=self.actor,
        )
        self.loan.refresh_from_db()

        self.assertEqual(self.loan.state, PawnLoanState.ACTIVE.value)
        self.assertEqual(result.accounting_event.event_kind, TransactionKind.DISBURSAL.value)
        self.assertEqual(result.accounting_event.payload["values"]["principal"], "50000")
        self.assertEqual(LoanPolicySnapshot.objects.filter(loan=self.loan).count(), 1)
        self.assertEqual(result.policy_snapshot.accounting_recognition, "CASH")
        self.assertEqual(result.outbox.status, LoanOutboxStatus.PENDING.value)
        audit = self.loan.change_log.get(event_kind=PawnLoanEventKind.DISBURSED.value)
        self.assertEqual(audit.metadata["accounting_event_id"], result.accounting_event.pk)
        readiness.assert_called_once()

    @patch("apps.tenant_apps.loans.services.pawn_disbursal.require_pawn_loan_accounting_readiness")
    def test_repeat_disbursal_returns_the_original_event_without_duplicate_effects(self, _readiness):
        first = disburse_pawn_loan(self.loan.pk, effective_date=date(2026, 8, 3))
        repeat = disburse_pawn_loan(self.loan.pk, effective_date=date(2026, 8, 3))

        self.assertTrue(repeat.already_disbursed)
        self.assertEqual(first.accounting_event.pk, repeat.accounting_event.pk)
        self.assertEqual(PawnLoanAccountingEvent.objects.filter(loan=self.loan).count(), 1)
        self.assertEqual(LoanPolicySnapshot.objects.filter(loan=self.loan).count(), 1)

    @patch("apps.tenant_apps.loans.services.pawn_disbursal.require_pawn_loan_accounting_readiness")
    def test_expired_license_blocks_disbursal_before_any_financial_record(self, _readiness):
        self.loan.license.expires_on = date(2026, 8, 2)
        self.loan.license.save(update_fields=["expires_on"])

        with self.assertRaises(PawnDisbursalError):
            disburse_pawn_loan(self.loan.pk, effective_date=date(2026, 8, 3))

        self.loan.refresh_from_db()
        self.assertEqual(self.loan.state, PawnLoanState.APPROVED.value)
        self.assertFalse(LoanPolicySnapshot.objects.filter(loan=self.loan).exists())
        self.assertFalse(PawnLoanAccountingEvent.objects.filter(loan=self.loan).exists())

    @patch("apps.tenant_apps.loans.services.pawn_disbursal.require_pawn_loan_accounting_readiness")
    def test_outbox_failure_rolls_back_policy_and_state_transition(self, _readiness):
        with patch(
            "apps.tenant_apps.loans.services.pawn_disbursal.record_loan_accounting_event",
            side_effect=RuntimeError("outbox unavailable"),
        ):
            with self.assertRaises(RuntimeError):
                disburse_pawn_loan(self.loan.pk, effective_date=date(2026, 8, 3))

        self.loan.refresh_from_db()
        self.assertEqual(self.loan.state, PawnLoanState.APPROVED.value)
        self.assertFalse(LoanPolicySnapshot.objects.filter(loan=self.loan).exists())

    @patch("apps.tenant_apps.loans.services.pawn_disbursal.require_pawn_loan_accounting_readiness")
    def test_pending_or_failed_accounting_blocks_later_financial_actions(self, _readiness):
        result = disburse_pawn_loan(self.loan.pk, effective_date=date(2026, 8, 3))

        with self.assertRaises(PawnDisbursalError):
            assert_pawn_loan_financial_actions_allowed(self.loan.pk)
        result.outbox.status = LoanOutboxStatus.FAILED.value
        result.outbox.save(update_fields=["status", "updated_at"])
        with self.assertRaises(PawnDisbursalError):
            assert_pawn_loan_financial_actions_allowed(self.loan.pk)

        deliver_outbox_event(
            result.outbox.pk,
            delivery_handler=lambda _event: type(
                "Receipt", (), {"dea_voucher_id": 1, "dea_journal_entry_id": 2}
            )(),
        )
        allowed = assert_pawn_loan_financial_actions_allowed(self.loan.pk)
        self.assertEqual(allowed.pk, self.loan.pk)

    def test_disbursal_service_cannot_import_dea_models_or_posting_internals(self):
        source = (
            Path(__file__).parents[1] / "services" / "pawn_disbursal.py"
        ).read_text(encoding="utf-8")

        self.assertNotIn("apps.tenant_apps.dea.models", source)
        self.assertNotIn("apps.tenant_apps.dea.posting", source)
        self.assertNotIn("apps.tenant_apps.dea.services", source)
