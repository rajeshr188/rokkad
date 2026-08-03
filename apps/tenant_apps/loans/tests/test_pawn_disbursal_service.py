import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django_tenants.test.cases import TenantTestCase

from apps.tenant_apps.loans.domain import (
    CollateralMetal,
    CollateralCustodyState,
    LoanDocumentKind,
    LoanOutboxStatus,
    PawnLoanEventKind,
    PawnLoanState,
    TransactionKind,
)
from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.dea.facade import resolve_party_account
from apps.tenant_apps.dea.models import (
    AccountTransaction,
    AccountType,
    AccountType_Ext,
    AccountingPeriod,
    EntityType,
    Ledger,
    LedgerTransaction,
    TransactionType_DE,
    Voucher,
    VoucherStatus,
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
    PawnRepaymentError,
    approve_pawn_loan,
    assert_pawn_loan_financial_actions_allowed,
    create_pawn_draft,
    deliver_outbox_event,
    disburse_pawn_loan,
    record_pawn_loan_repayment,
)
from apps.tenant_apps.loans.selectors import get_pawn_loan_balance
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

        delivery_source = (
            Path(__file__).parents[1] / "integrations" / "dea_delivery.py"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "from apps.tenant_apps.dea import facade as dea_facade",
            delivery_source,
        )
        self.assertNotIn("apps.tenant_apps.dea.models", delivery_source)
        self.assertNotIn("apps.tenant_apps.dea.posting", delivery_source)
        self.assertNotIn("apps.tenant_apps.dea.services", delivery_source)

    def test_default_adapter_posts_balanced_dea_voucher_and_is_idempotent(self):
        self._seed_dea_disbursal_setup()

        with self.captureOnCommitCallbacks(execute=True):
            result = disburse_pawn_loan(
                self.loan.pk,
                effective_date=date(2026, 8, 3),
                actor=self.actor,
            )
        result.outbox.refresh_from_db()

        self.assertEqual(result.outbox.status, LoanOutboxStatus.POSTED.value)
        voucher = Voucher.objects.get(pk=result.outbox.dea_voucher_id)
        journal_entry = voucher.journal_entries.get(pk=result.outbox.dea_journal_entry_id)
        self.assertEqual(voucher.status, VoucherStatus.POSTED)
        self.assertEqual(voucher.voucher_type.name, "PAWN_LOAN_DISBURSAL")
        self.assertEqual(voucher.voucher_date, date(2026, 8, 3))
        self.assertEqual(
            voucher.doc_content_type,
            ContentType.objects.get_for_model(PawnLoanAccountingEvent),
        )
        ledger_txn = LedgerTransaction.objects.get(journal_entry=journal_entry)
        self.assertEqual(ledger_txn.ledgerno_dr.name, "LOAN_PRINCIPAL_CTRL")
        self.assertEqual(ledger_txn.ledgerno.name, "CASH")
        self.assertEqual(ledger_txn.amount.amount, Decimal("50000.00"))
        account_txn = AccountTransaction.objects.get(journal_entry=journal_entry)
        self.assertEqual(account_txn.ledgerno.name, "BORROWER_LOAN_CTRL")
        self.assertEqual(account_txn.XactTypeCode_id, "Dr")
        self.assertTrue(journal_entry.validate_balanced()[0])
        balance = get_pawn_loan_balance(
            self.loan.pk,
            as_of_date=date(2026, 8, 3),
        )
        self.assertEqual(balance.principal_outstanding, Decimal("50000.00"))
        self.assertEqual(balance.total_due, Decimal("50000.00"))
        self.assertTrue(balance.posting_ready)
        self.assertFalse(balance.closure_ready)

        repeated = deliver_outbox_event(result.outbox.pk)
        self.assertEqual(repeated.attempt_count, 1)
        self.assertEqual(Voucher.objects.filter(pk=voucher.pk).count(), 1)
        self.assertEqual(voucher.journal_entries.count(), 1)

    def test_repayment_posts_to_dea_reconciles_balance_and_keeps_collateral(self):
        self._seed_dea_disbursal_setup()
        with self.captureOnCommitCallbacks(execute=True):
            disbursal = disburse_pawn_loan(
                self.loan.pk,
                effective_date=date(2026, 8, 3),
                actor=self.actor,
            )
        disbursal.outbox.refresh_from_db()
        self.assertEqual(disbursal.outbox.status, LoanOutboxStatus.POSTED.value)

        with patch(
            "apps.tenant_apps.loans.services.pawn_repayment.timezone.localdate",
            return_value=date(2026, 8, 3),
        ):
            with self.captureOnCommitCallbacks(execute=True):
                repayment = record_pawn_loan_repayment(
                    self.loan.pk,
                    amount=Decimal("1000.00"),
                    request_key="repayment-001",
                    actor=self.actor,
                )
        repayment.outbox.refresh_from_db()

        self.assertEqual(repayment.outbox.status, LoanOutboxStatus.POSTED.value)
        self.assertEqual(repayment.allocation.principal, Decimal("1000.00"))
        self.assertEqual(repayment.allocation.interest, Decimal("0.00"))
        self.assertEqual(repayment.allocation.fees, Decimal("0.00"))
        voucher = Voucher.objects.get(pk=repayment.outbox.dea_voucher_id)
        self.assertEqual(voucher.voucher_type.name, "PAWN_LOAN_REPAYMENT")
        journal_entry = voucher.journal_entries.get(
            pk=repayment.outbox.dea_journal_entry_id
        )
        ledger_txn = LedgerTransaction.objects.get(journal_entry=journal_entry)
        self.assertEqual(ledger_txn.ledgerno_dr.name, "CASH")
        self.assertEqual(ledger_txn.ledgerno.name, "LOAN_PRINCIPAL_CTRL")
        self.assertEqual(ledger_txn.amount.amount, Decimal("1000.00"))
        account_txn = AccountTransaction.objects.get(journal_entry=journal_entry)
        self.assertEqual(account_txn.ledgerno.name, "BORROWER_LOAN_CTRL")
        self.assertEqual(account_txn.XactTypeCode_id, "Cr")
        self.assertTrue(journal_entry.validate_balanced()[0])

        balance = get_pawn_loan_balance(
            self.loan.pk,
            as_of_date=date(2026, 8, 3),
        )
        self.assertEqual(balance.principal_paid, Decimal("1000.00"))
        self.assertEqual(balance.principal_outstanding, Decimal("49000.00"))
        self.assertEqual(balance.total_due, Decimal("49000.00"))
        self.assertTrue(balance.posting_ready)
        self.assertEqual(
            self.loan.collateral_items.get().custody_state,
            CollateralCustodyState.IN_VAULT.value,
        )

        repeated = record_pawn_loan_repayment(
            self.loan.pk,
            amount=Decimal("1000.00"),
            request_key="repayment-001",
        )
        self.assertTrue(repeated.already_recorded)
        self.assertEqual(repeated.accounting_event.pk, repayment.accounting_event.pk)
        self.assertEqual(
            PawnLoanAccountingEvent.objects.filter(
                loan=self.loan,
                event_kind=TransactionKind.REPAYMENT.value,
            ).count(),
            1,
        )
        with self.assertRaises(PawnRepaymentError):
            record_pawn_loan_repayment(
                self.loan.pk,
                amount=Decimal("999.00"),
                request_key="repayment-001",
            )

    def test_repayment_rejects_overpayment_without_recording_an_event(self):
        self._seed_dea_disbursal_setup()
        with self.captureOnCommitCallbacks(execute=True):
            disbursal = disburse_pawn_loan(
                self.loan.pk,
                effective_date=date(2026, 8, 3),
                actor=self.actor,
            )
        disbursal.outbox.refresh_from_db()
        self.assertEqual(
            disbursal.outbox.status,
            LoanOutboxStatus.POSTED.value,
            disbursal.outbox.last_error,
        )

        with patch(
            "apps.tenant_apps.loans.services.pawn_repayment.timezone.localdate",
            return_value=date(2026, 8, 3),
        ):
            with self.assertRaises(PawnRepaymentError):
                record_pawn_loan_repayment(
                    self.loan.pk,
                    amount=Decimal("50000.01"),
                    request_key="overpayment",
                )

        self.assertFalse(
            PawnLoanAccountingEvent.objects.filter(
                loan=self.loan,
                event_kind=TransactionKind.REPAYMENT.value,
            ).exists()
        )

    def test_pending_repayment_blocks_a_different_dependent_repayment(self):
        self._seed_dea_disbursal_setup()
        with self.captureOnCommitCallbacks(execute=True):
            disbursal = disburse_pawn_loan(
                self.loan.pk,
                effective_date=date(2026, 8, 3),
                actor=self.actor,
            )
        disbursal.outbox.refresh_from_db()
        self.assertEqual(
            disbursal.outbox.status,
            LoanOutboxStatus.POSTED.value,
            disbursal.outbox.last_error,
        )

        with patch(
            "apps.tenant_apps.loans.services.pawn_repayment.timezone.localdate",
            return_value=date(2026, 8, 3),
        ):
            with self.captureOnCommitCallbacks(execute=False) as callbacks:
                first = record_pawn_loan_repayment(
                    self.loan.pk,
                    amount=Decimal("100.00"),
                    request_key="pending-repayment",
                )
            self.assertEqual(len(callbacks), 1)
            self.assertEqual(first.outbox.status, LoanOutboxStatus.PENDING.value)

            repeated = record_pawn_loan_repayment(
                self.loan.pk,
                amount=Decimal("100.00"),
                request_key="pending-repayment",
            )
            self.assertTrue(repeated.already_recorded)
            with self.assertRaises(PawnRepaymentError):
                record_pawn_loan_repayment(
                    self.loan.pk,
                    amount=Decimal("50.00"),
                    request_key="dependent-repayment",
                )

    def _seed_dea_disbursal_setup(self):
        debit, _ = TransactionType_DE.objects.get_or_create(
            XactTypeCode="Dr", defaults={"name": "Debit"}
        )
        AccountType_Ext.objects.get_or_create(
            description="Debtor", defaults={"XactTypeCode": debit}
        )
        EntityType.objects.get_or_create(name="Person")
        asset, _ = AccountType.objects.get_or_create(
            AccountType="Asset",
            defaults={"description": "Asset Account", "code_prefix": "1"},
        )
        income, _ = AccountType.objects.get_or_create(
            AccountType="Income",
            defaults={"description": "Income Account", "code_prefix": "4"},
        )
        for key in ("CASH", "LOAN_PRINCIPAL_CTRL", "BORROWER_LOAN_CTRL"):
            Ledger.objects.get_or_create(name=key, defaults={"AccountType": asset})
        Ledger.objects.get_or_create(
            name="INTEREST_INCOME", defaults={"AccountType": income}
        )
        Ledger.objects.get_or_create(
            name="INTEREST_RECEIVABLE",
            defaults={"AccountType": asset, "code": "1.90"},
        )
        Ledger.objects.get_or_create(
            name="DOCUMENT_CHARGE_INCOME",
            defaults={"AccountType": income, "code": "4.90"},
        )
        AccountingPeriod.objects.get_or_create(
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 31),
            defaults={"name": "August 2026", "status": "OPEN"},
        )
        Customer.objects.create(
            firstname=f"Borrower-{uuid.uuid4().hex[:8]}",
            lastname="PawnLoan",
            party=self.loan.borrower,
        )
        resolve_party_account(
            self.loan.borrower,
            role_key="BORROWER",
            purpose="BORROWER_LOAN_RECEIVABLE",
            create=True,
        )
