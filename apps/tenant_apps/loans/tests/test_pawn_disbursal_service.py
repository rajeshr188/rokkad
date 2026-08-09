import uuid
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.utils import timezone
from django_tenants.test.cases import TenantTestCase

from apps.configuration.services import PreferenceService
from apps.tenant_apps.loans.domain import (
    AccountingRecognition,
    CollateralMetal,
    CollateralCustodyState,
    InterestMethod,
    LoanDocumentKind,
    LoanOutboxStatus,
    PawnLoanEventKind,
    PawnLoanRenewalMode,
    PawnLoanState,
    PartialMonthMethod,
    TransactionKind,
    ValuationMethod,
    WorkspacePolicyDefaults,
    resolve_policy,
)
from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.dea.facade import (
    inspect_pawn_loan_accounting_reference,
    resolve_party_account,
)
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
    PawnCollateralItem,
    PawnLoanAccountingEvent,
    PawnLoanAuction,
    PawnLoanAuctionReversal,
    PawnCollateralCustodyEvent,
    PawnLoanInterestAccrual,
    PawnLoanRelease,
    PawnLoanReleaseReversal,
    PawnLoanRenewal,
    PawnLoanRenewalReversal,
    PawnLoanPrincipalOpeningLine,
)
from apps.tenant_apps.loans.services import (
    CollateralDraftInput,
    CreatePawnDraftCommand,
    PawnDisbursalError,
    PawnRepaymentError,
    PawnInterestError,
    PawnReversalError,
    approve_pawn_loan,
    append_collateral_photo,
    assess_pawn_loan_accounting_readiness,
    assert_pawn_loan_financial_actions_allowed,
    create_pawn_draft,
    deliver_outbox_event,
    disburse_pawn_loan,
    ensure_pawn_borrower_accounting,
    capitalize_pawn_loan_interest,
    finalize_pawn_loan_accrual,
    preview_pawn_loan_accruals,
    reverse_pawn_loan_event,
    record_pawn_loan_repayment,
    release_pawn_loan_in_full,
    release_pawn_loan_partially,
    PawnReleaseError,
    PawnAuctionError,
    cancel_pawn_loan_auction,
    complete_pawn_loan_auction,
    initiate_pawn_loan_auction,
    PawnRenewalError,
    RetainedCollateralInput,
    create_pawn_loan_economic_policy,
    create_pawn_metal_interest_rate_policy,
    renew_pawn_loan,
    reverse_pawn_loan_renewal,
    reverse_pawn_loan_auction,
    start_pawn_loan_auction,
)
from apps.tenant_apps.loans.selectors import (
    get_pawn_loan_balance,
    get_pawn_loan_release_readiness,
    get_pawn_loan_reports,
)
from apps.tenant_apps.loans.services.pawn_tranches import (
    get_pawn_principal_tranche_balances,
)
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.rates.models import Rate, RateSource
from apps.tenant_apps.notify_v2.models import NotificationJob


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
        PreferenceService.set_workspace(
            self.tenant,
            "accounting__integration_mode",
            "DEA",
        )
        release_date = patch(
            "apps.tenant_apps.loans.services.pawn_release.timezone.localdate",
            return_value=date(2026, 8, 3),
        )
        release_date.start()
        self.addCleanup(release_date.stop)
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
        LoanNumberSequence.objects.create(
            series=series,
            document_kind=LoanDocumentKind.PAWN_LOAN_RELEASE.value,
            prefix="RL-A-",
            width=5,
            maximum_number=10000,
        )
        create_pawn_loan_economic_policy(
            workspace=self.tenant,
            license=license,
            valuation_method=ValuationMethod.LATEST_APPRAISAL,
            maximum_ltv_ratio=Decimal("1.00"),
            advance_interest_periods=0,
            effective_from=date(2026, 1, 1),
        )
        create_pawn_metal_interest_rate_policy(
            workspace=self.tenant,
            license=license,
            metal=CollateralMetal.GOLD,
            monthly_interest_rate=Decimal("2.00"),
            effective_from=date(2026, 1, 1),
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
                        allocated_principal=Decimal("50000"),
                    ),
                ),
            ),
            actor=self.actor,
        )
        append_collateral_photo(
            self.loan.collateral_items.get().pk,
            upload=SimpleUploadedFile(
                "gold.jpg", b"\xff\xd8\xff\xe0evidence", content_type="image/jpeg"
            ),
            actor=self.actor,
        )
        approve_pawn_loan(self.loan.pk, actor=self.actor)

    @patch(
        "apps.tenant_apps.loans.services.accounting_outbox.is_dea_integration_enabled",
        return_value=False,
    )
    @patch("apps.tenant_apps.loans.services.pawn_disbursal.require_pawn_loan_accounting_readiness")
    def test_disbursal_is_atomic_and_creates_immutable_policy_and_outbox(
        self,
        readiness,
        _integration_enabled,
    ):
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

    @patch("apps.tenant_apps.loans.services.borrower_accounting.AuditLog.log")
    def test_borrower_accounting_setup_is_real_idempotent_and_unblocks_readiness(
        self, audit
    ):
        self._seed_dea_disbursal_setup(include_borrower_account=False)

        first = ensure_pawn_borrower_accounting(
            self.loan.pk,
            actor=self.tenant.owner,
        )
        second = ensure_pawn_borrower_accounting(
            self.loan.pk,
            actor=self.tenant.owner,
        )

        self.assertTrue(first.customer_created)
        self.assertTrue(first.mapping_created)
        self.assertFalse(second.customer_created)
        self.assertFalse(second.mapping_created)
        self.assertEqual(first.account.pk, second.account.pk)
        self.assertEqual(first.mapping.pk, second.mapping.pk)
        self.assertEqual(first.mapping.role_key, "BORROWER")
        self.assertEqual(first.mapping.purpose, "BORROWER_LOAN_RECEIVABLE")
        self.assertEqual(first.mapping.status, "ACTIVE")
        self.assertEqual(first.mapping.control_ledger.name, "BORROWER_LOAN_CTRL")
        self.assertEqual(self.loan.borrower.legacy_customer.pk, first.customer.pk)
        self.assertTrue(
            assess_pawn_loan_accounting_readiness(
                self.loan,
                effective_date=date(2026, 8, 3),
            ).ready
        )
        audit.assert_called_once()

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
        evidence = inspect_pawn_loan_accounting_reference(
            voucher_id=voucher.pk,
            journal_entry_id=journal_entry.pk,
            source_event_id=result.outbox.event_id,
        )
        self.assertEqual(evidence.debit_total, Decimal("50000.00"))
        self.assertEqual(evidence.credit_total, Decimal("50000.00"))
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

    def test_collateral_economics_posts_gross_receivable_net_cash_and_deductions(self):
        approval = self.loan.approval_snapshots.get()
        payload = dict(approval.payload)
        payload["collateral_economics"] = {
            "advance_interest_periods": 1,
            "monthly_interest": "1000.00",
            "advance_interest": "1000.00",
            "deducted_fees": "500.00",
            "net_disbursed": "48500.00",
            "tranches": [
                {
                    "collateral_item_id": self.loan.collateral_items.get().pk,
                    "allocated_principal": "50000.00",
                    "monthly_interest_rate": "2.000000",
                    "advance_interest": "1000.00",
                }
            ],
            "fees": [{"code": "DOC", "amount": "500.00", "deducted_at_disbursal": True}],
        }
        self.loan.approval_snapshots.filter(pk=approval.pk).update(payload=payload)
        self._seed_dea_disbursal_setup()

        with self.captureOnCommitCallbacks(execute=True):
            result = disburse_pawn_loan(
                self.loan.pk,
                effective_date=date(2026, 8, 3),
                actor=self.actor,
            )
        result.outbox.refresh_from_db()

        journal = Voucher.objects.get(pk=result.outbox.dea_voucher_id).journal_entries.get(
            pk=result.outbox.dea_journal_entry_id
        )
        postings = {
            row.ledgerno.name: row.amount.amount
            for row in LedgerTransaction.objects.filter(journal_entry=journal)
        }
        self.assertEqual(postings["CASH"], Decimal("48500.00"))
        self.assertEqual(postings["INTEREST_INCOME"], Decimal("1000.00"))
        self.assertEqual(postings["DOCUMENT_CHARGE_INCOME"], Decimal("500.00"))
        account_txn = AccountTransaction.objects.get(journal_entry=journal)
        self.assertEqual(account_txn.amount.amount, Decimal("50000.00"))
        self.assertEqual(result.disbursal_snapshot.net_disbursed, Decimal("48500.0000"))
        self.assertTrue(journal.validate_balanced()[0])

    def test_accrual_disbursal_defers_advance_interest_as_unearned_revenue(self):
        approval = self.loan.approval_snapshots.get()
        payload = dict(approval.payload)
        payload["collateral_economics"] = {
            "advance_interest_periods": 1,
            "monthly_interest": "1000.00",
            "advance_interest": "1000.00",
            "deducted_fees": "0.00",
            "net_disbursed": "49000.00",
            "tranches": [
                {
                    "collateral_item_id": self.loan.collateral_items.get().pk,
                    "allocated_principal": "50000.00",
                    "monthly_interest_rate": "2.000000",
                    "advance_interest": "1000.00",
                }
            ],
            "fees": [],
        }
        self.loan.approval_snapshots.filter(pk=approval.pk).update(payload=payload)
        self._seed_dea_disbursal_setup()
        liability, _ = AccountType.objects.get_or_create(
            AccountType="Liability",
            defaults={"description": "Liability Account", "code_prefix": "2"},
        )
        Ledger.objects.get_or_create(
            name="Unearned Revenue", defaults={"AccountType": liability}
        )
        policy = resolve_policy(
            workspace_defaults=WorkspacePolicyDefaults(
                accounting_recognition=AccountingRecognition.ACCRUAL
            )
        )

        with patch(
            "apps.tenant_apps.loans.services.pawn_disbursal.resolve_policy",
            return_value=policy,
        ):
            with self.captureOnCommitCallbacks(execute=True):
                result = disburse_pawn_loan(
                    self.loan.pk,
                    effective_date=date(2026, 8, 3),
                    actor=self.actor,
                )
        result.outbox.refresh_from_db()

        postings = {
            row.ledgerno.name: row.amount.amount
            for row in LedgerTransaction.objects.filter(
                journal_entry_id=result.outbox.dea_journal_entry_id
            )
        }
        self.assertEqual(postings["CASH"], Decimal("49000.00"))
        self.assertEqual(postings["Unearned Revenue"], Decimal("1000.00"))
        self.assertNotIn("INTEREST_INCOME", postings)

        self._open_period(date(2026, 9, 1), date(2026, 9, 30), "September 2026")
        with patch(
            "apps.tenant_apps.loans.services.pawn_interest.timezone.localdate",
            return_value=date(2026, 9, 2),
        ):
            with self.captureOnCommitCallbacks(execute=True):
                accrual = finalize_pawn_loan_accrual(
                    self.loan.pk,
                    period_number=1,
                    actor=self.actor,
                )
        accrual.outbox.refresh_from_db()
        self.assertEqual(accrual.accrual.recognized_interest, Decimal("0.0000"))
        self.assertEqual(
            accrual.accounting_event.payload["values"]["advance_interest_applied"],
            "1000",
        )
        accrual_posting = LedgerTransaction.objects.get(
            journal_entry_id=accrual.outbox.dea_journal_entry_id
        )
        self.assertEqual(accrual_posting.ledgerno_dr.name, "Unearned Revenue")
        self.assertEqual(accrual_posting.ledgerno.name, "INTEREST_INCOME")
        self.assertEqual(accrual_posting.amount.amount, Decimal("1000.00"))
        balance = get_pawn_loan_balance(self.loan.pk, as_of_date=date(2026, 9, 2))
        self.assertEqual(balance.interest_outstanding, Decimal("0.00"))

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

    def test_cash_accrual_finalizes_full_period_and_previews_partial_slab(self):
        policy = resolve_policy(
            workspace_defaults=WorkspacePolicyDefaults(
                partial_month_method=PartialMonthMethod.SLAB,
                partial_month_cutoff_days=15,
                partial_month_lower_fraction=Decimal("0.5"),
            )
        )
        self._activate_loan(policy)

        previews = preview_pawn_loan_accruals(
            self.loan.pk,
            as_of_date=date(2026, 9, 10),
        )
        self.assertEqual([item.period_number for item in previews], [1, 2])
        self.assertEqual(previews[0].recognized_interest, Decimal("1000.00"))
        self.assertEqual(previews[1].period_fraction, Decimal("0.5"))
        self.assertEqual(previews[1].recognized_interest, Decimal("500.00"))
        self.assertTrue(previews[1].is_partial)

        with patch(
            "apps.tenant_apps.loans.services.pawn_interest.timezone.localdate",
            return_value=date(2026, 9, 10),
        ):
            with self.assertRaises(PawnInterestError):
                finalize_pawn_loan_accrual(self.loan.pk, period_number=2)
            with self.captureOnCommitCallbacks(execute=True):
                result = finalize_pawn_loan_accrual(
                    self.loan.pk,
                    period_number=1,
                    actor=self.actor,
                )
        result.outbox.refresh_from_db()

        self.assertEqual(result.outbox.status, LoanOutboxStatus.POSTED.value)
        self.assertIsNone(result.outbox.dea_voucher_id)
        self.assertEqual(result.accrual.unrounded_interest, Decimal("1000"))
        self.assertEqual(result.accrual.recognized_interest, Decimal("1000.00"))
        self.assertEqual(PawnLoanInterestAccrual.objects.filter(loan=self.loan).count(), 1)
        balance = get_pawn_loan_balance(self.loan.pk, as_of_date=date(2026, 9, 10))
        self.assertEqual(balance.interest_outstanding, Decimal("1000.00"))

        repeated = finalize_pawn_loan_accrual(
            self.loan.pk,
            period_number=1,
        )
        self.assertTrue(repeated.already_finalized)
        self.assertEqual(repeated.accrual.pk, result.accrual.pk)

        with patch(
            "apps.tenant_apps.loans.services.pawn_reversal.timezone.localdate",
            return_value=date(2026, 9, 10),
        ):
            with self.captureOnCommitCallbacks(execute=True):
                reversed_accrual = reverse_pawn_loan_event(
                    result.accounting_event.pk,
                    reason="Cash accrual correction",
                    actor=self.tenant.owner,
                )
        reversed_accrual.outbox.refresh_from_db()
        self.assertEqual(
            reversed_accrual.outbox.status,
            LoanOutboxStatus.POSTED.value,
        )
        self.assertIsNone(reversed_accrual.outbox.dea_voucher_id)
        balance = get_pawn_loan_balance(self.loan.pk, as_of_date=date(2026, 9, 10))
        self.assertEqual(balance.interest_outstanding, Decimal("0.00"))

    def test_accrual_policy_posts_receivable_income_and_capitalization(self):
        policy = resolve_policy(
            workspace_defaults=WorkspacePolicyDefaults(
                interest_method=InterestMethod.COMPOUND,
                capitalization_interval_periods=1,
                accounting_recognition=AccountingRecognition.ACCRUAL,
            )
        )
        self._activate_loan(policy)
        self._open_period(date(2026, 9, 1), date(2026, 9, 30), "September 2026")

        with patch(
            "apps.tenant_apps.loans.services.pawn_interest.timezone.localdate",
            return_value=date(2026, 9, 2),
        ):
            with self.captureOnCommitCallbacks(execute=True):
                accrual = finalize_pawn_loan_accrual(
                    self.loan.pk,
                    period_number=1,
                    actor=self.actor,
                )
        accrual.outbox.refresh_from_db()
        self.assertEqual(accrual.outbox.status, LoanOutboxStatus.POSTED.value)
        accrual_voucher = Voucher.objects.get(pk=accrual.outbox.dea_voucher_id)
        accrual_txn = LedgerTransaction.objects.get(
            journal_entry_id=accrual.outbox.dea_journal_entry_id
        )
        self.assertEqual(accrual_voucher.voucher_type.name, "PAWN_LOAN_INTEREST_ACCRUAL")
        self.assertEqual(accrual_txn.ledgerno_dr.name, "INTEREST_RECEIVABLE")
        self.assertEqual(accrual_txn.ledgerno.name, "INTEREST_INCOME")
        accrual_account_txn = AccountTransaction.objects.get(
            journal_entry_id=accrual.outbox.dea_journal_entry_id
        )
        self.assertEqual(accrual_account_txn.XactTypeCode_id, "Dr")

        with self.captureOnCommitCallbacks(execute=True):
            capitalized = capitalize_pawn_loan_interest(
                self.loan.pk,
                through_period_number=1,
                actor=self.actor,
            )
        capitalized.outbox.refresh_from_db()
        self.assertEqual(capitalized.outbox.status, LoanOutboxStatus.POSTED.value)
        capitalization_voucher = Voucher.objects.get(
            pk=capitalized.outbox.dea_voucher_id
        )
        capitalization_txn = LedgerTransaction.objects.get(
            journal_entry_id=capitalized.outbox.dea_journal_entry_id
        )
        self.assertEqual(
            capitalization_voucher.voucher_type.name,
            "PAWN_LOAN_INTEREST_CAPITALIZATION",
        )
        self.assertEqual(capitalization_txn.ledgerno_dr.name, "LOAN_PRINCIPAL_CTRL")
        self.assertEqual(capitalization_txn.ledgerno.name, "INTEREST_RECEIVABLE")
        balance = get_pawn_loan_balance(self.loan.pk, as_of_date=date(2026, 9, 2))
        self.assertEqual(balance.principal_outstanding, Decimal("51000.00"))
        self.assertEqual(balance.interest_outstanding, Decimal("0.00"))

        repeated = capitalize_pawn_loan_interest(
            self.loan.pk,
            through_period_number=1,
        )
        self.assertTrue(repeated.already_recorded)
        self.assertEqual(repeated.accounting_event.pk, capitalized.accounting_event.pk)

    def test_itemized_compound_accrual_blocks_after_unattributed_capitalization(self):
        policy = resolve_policy(
            workspace_defaults=WorkspacePolicyDefaults(
                interest_method=InterestMethod.COMPOUND,
                capitalization_interval_periods=2,
                accounting_recognition=AccountingRecognition.CASH,
            )
        )
        self._activate_loan(policy)

        with patch(
            "apps.tenant_apps.loans.services.pawn_interest.timezone.localdate",
            return_value=date(2026, 10, 2),
        ):
            with self.assertRaises(PawnInterestError):
                finalize_pawn_loan_accrual(self.loan.pk, period_number=2)

        for period_number, business_date in (
            (1, date(2026, 9, 2)),
            (2, date(2026, 10, 2)),
        ):
            with patch(
                "apps.tenant_apps.loans.services.pawn_interest.timezone.localdate",
                return_value=business_date,
            ):
                with self.captureOnCommitCallbacks(execute=True):
                    finalized = finalize_pawn_loan_accrual(
                        self.loan.pk,
                        period_number=period_number,
                        actor=self.actor,
                    )
            finalized.outbox.refresh_from_db()
            self.assertEqual(finalized.outbox.status, LoanOutboxStatus.POSTED.value)

        self.assertEqual(
            preview_pawn_loan_accruals(
                self.loan.pk,
                as_of_date=date(2026, 11, 2),
                include_partial=False,
            ),
            (),
        )
        with self.captureOnCommitCallbacks(execute=True):
            capitalized = capitalize_pawn_loan_interest(
                self.loan.pk,
                through_period_number=2,
                actor=self.actor,
            )
        capitalized.outbox.refresh_from_db()
        self.assertEqual(capitalized.outbox.status, LoanOutboxStatus.POSTED.value)
        self.assertIsNone(capitalized.outbox.dea_voucher_id)

        with self.assertRaisesMessage(
            PawnInterestError,
            "Capitalized principal lacks immutable item attribution",
        ):
            preview_pawn_loan_accruals(
                self.loan.pk,
                as_of_date=date(2026, 11, 2),
                include_partial=False,
            )

        self._open_period(date(2026, 11, 1), date(2026, 11, 30), "November 2026")
        with patch(
            "apps.tenant_apps.loans.services.pawn_repayment.timezone.localdate",
            return_value=date(2026, 11, 2),
        ):
            with self.captureOnCommitCallbacks(execute=True):
                repayment = record_pawn_loan_repayment(
                    self.loan.pk,
                    amount=Decimal("1000.00"),
                    request_key="capitalized-interest-collection",
                    actor=self.actor,
                )
        repayment.outbox.refresh_from_db()
        repayment_txn = LedgerTransaction.objects.get(
            journal_entry_id=repayment.outbox.dea_journal_entry_id
        )
        self.assertEqual(repayment_txn.ledgerno_dr.name, "CASH")
        self.assertEqual(repayment_txn.ledgerno.name, "INTEREST_INCOME")
        self.assertFalse(
            AccountTransaction.objects.filter(
                journal_entry_id=repayment.outbox.dea_journal_entry_id
            ).exists()
        )
        balance = get_pawn_loan_balance(self.loan.pk, as_of_date=date(2026, 11, 2))
        self.assertEqual(
            balance.capitalized_interest_principal_outstanding,
            Decimal("1000.00"),
        )
        self.assertEqual(balance.original_principal_outstanding, Decimal("50000.00"))

    def test_reversal_requires_admin_reason_and_newest_first_order(self):
        self._activate_loan()
        with patch(
            "apps.tenant_apps.loans.services.pawn_repayment.timezone.localdate",
            return_value=date(2026, 8, 3),
        ):
            with self.captureOnCommitCallbacks(execute=True):
                repayment = record_pawn_loan_repayment(
                    self.loan.pk,
                    amount=Decimal("1000.00"),
                    request_key="reversal-target",
                    actor=self.actor,
                )
        repayment.outbox.refresh_from_db()
        disbursal = self.loan.accounting_events.get(
            event_kind=TransactionKind.DISBURSAL.value
        )
        original_repayment_payload = dict(repayment.accounting_event.payload)

        with patch(
            "apps.tenant_apps.loans.services.pawn_reversal.timezone.localdate",
            return_value=date(2026, 8, 3),
        ):
            with self.assertRaises(PawnReversalError):
                reverse_pawn_loan_event(
                    repayment.accounting_event.pk,
                    reason="Unauthorized correction",
                    actor=self.actor,
                )
            with self.assertRaises(PawnReversalError):
                reverse_pawn_loan_event(
                    repayment.accounting_event.pk,
                    reason="",
                    actor=self.tenant.owner,
                )
            with self.assertRaises(PawnReversalError):
                reverse_pawn_loan_event(
                    disbursal.pk,
                    reason="Wrong order",
                    actor=self.tenant.owner,
                )

            with self.captureOnCommitCallbacks(execute=True):
                repayment_reversal = reverse_pawn_loan_event(
                    repayment.accounting_event.pk,
                    reason="Duplicate borrower receipt",
                    actor=self.tenant.owner,
                )
        repayment_reversal.outbox.refresh_from_db()
        self.assertEqual(
            repayment_reversal.outbox.status,
            LoanOutboxStatus.POSTED.value,
        )
        repayment_voucher = Voucher.objects.get(pk=repayment.outbox.dea_voucher_id)
        self.assertEqual(repayment_voucher.status, VoucherStatus.REVERSED)
        reversal_entry = repayment_voucher.journal_entries.get(
            pk=repayment_reversal.outbox.dea_journal_entry_id
        )
        self.assertEqual(
            reversal_entry.is_reversal_of_id,
            repayment.outbox.dea_journal_entry_id,
        )
        repayment.accounting_event.refresh_from_db()
        self.assertEqual(repayment.accounting_event.payload, original_repayment_payload)
        balance = get_pawn_loan_balance(self.loan.pk, as_of_date=date(2026, 8, 3))
        self.assertEqual(balance.principal_outstanding, Decimal("50000.00"))

        repeated = reverse_pawn_loan_event(
            repayment.accounting_event.pk,
            reason="Duplicate borrower receipt",
            actor=self.tenant.owner,
        )
        self.assertTrue(repeated.already_reversed)
        self.assertEqual(
            repeated.reversal_event.pk,
            repayment_reversal.reversal_event.pk,
        )
        with self.assertRaises(PawnReversalError):
            reverse_pawn_loan_event(
                repayment.accounting_event.pk,
                reason="Conflicting replacement reason",
                actor=self.tenant.owner,
            )
        with patch(
            "apps.tenant_apps.loans.services.pawn_reversal.timezone.localdate",
            return_value=date(2026, 8, 3),
        ):
            with self.captureOnCommitCallbacks(execute=True):
                disbursal_reversal = reverse_pawn_loan_event(
                    disbursal.pk,
                    reason="Loan was disbursed in error",
                    actor=self.tenant.owner,
                )
        disbursal_reversal.outbox.refresh_from_db()
        self.loan.refresh_from_db()
        self.assertEqual(self.loan.state, PawnLoanState.APPROVED.value)
        balance = get_pawn_loan_balance(self.loan.pk, as_of_date=date(2026, 8, 3))
        self.assertEqual(balance.principal_outstanding, Decimal("0.00"))
        self.assertEqual(balance.total_due, Decimal("0.00"))
        self.assertEqual(
            self.loan.change_log.filter(
                event_kind=PawnLoanEventKind.REVERSAL_RECORDED.value
            ).count(),
            2,
        )

    def test_accrual_and_capitalization_reverse_in_strict_order(self):
        policy = resolve_policy(
            workspace_defaults=WorkspacePolicyDefaults(
                interest_method=InterestMethod.COMPOUND,
                capitalization_interval_periods=1,
                accounting_recognition=AccountingRecognition.ACCRUAL,
            )
        )
        self._activate_loan(policy)
        self._open_period(date(2026, 9, 1), date(2026, 9, 30), "September 2026")
        with patch(
            "apps.tenant_apps.loans.services.pawn_interest.timezone.localdate",
            return_value=date(2026, 9, 2),
        ):
            with self.captureOnCommitCallbacks(execute=True):
                accrual = finalize_pawn_loan_accrual(
                    self.loan.pk,
                    period_number=1,
                    actor=self.actor,
                )
        with self.captureOnCommitCallbacks(execute=True):
            capitalization = capitalize_pawn_loan_interest(
                self.loan.pk,
                through_period_number=1,
                actor=self.actor,
            )
        accrual.outbox.refresh_from_db()
        capitalization.outbox.refresh_from_db()

        with patch(
            "apps.tenant_apps.loans.services.pawn_reversal.timezone.localdate",
            return_value=date(2026, 9, 2),
        ):
            with self.assertRaises(PawnReversalError):
                reverse_pawn_loan_event(
                    accrual.accounting_event.pk,
                    reason="Must reverse capitalization first",
                    actor=self.tenant.owner,
                )
            with self.captureOnCommitCallbacks(execute=True):
                cap_reversal = reverse_pawn_loan_event(
                    capitalization.accounting_event.pk,
                    reason="Incorrect capitalization",
                    actor=self.tenant.owner,
                )
        cap_reversal.outbox.refresh_from_db()
        balance = get_pawn_loan_balance(self.loan.pk, as_of_date=date(2026, 9, 2))
        self.assertEqual(balance.principal_outstanding, Decimal("50000.00"))
        self.assertEqual(balance.interest_outstanding, Decimal("1000.00"))

        with patch(
            "apps.tenant_apps.loans.services.pawn_reversal.timezone.localdate",
            return_value=date(2026, 9, 2),
        ):
            with self.captureOnCommitCallbacks(execute=True):
                accrual_reversal = reverse_pawn_loan_event(
                    accrual.accounting_event.pk,
                    reason="Incorrect accrual period",
                    actor=self.tenant.owner,
                )
        accrual_reversal.outbox.refresh_from_db()
        balance = get_pawn_loan_balance(self.loan.pk, as_of_date=date(2026, 9, 2))
        self.assertEqual(balance.principal_outstanding, Decimal("50000.00"))
        self.assertEqual(balance.interest_outstanding, Decimal("0.00"))
        self.assertEqual(PawnLoanInterestAccrual.objects.filter(loan=self.loan).count(), 1)
        self.assertEqual(
            Voucher.objects.get(pk=accrual.outbox.dea_voucher_id).status,
            VoucherStatus.REVERSED,
        )
        self.assertEqual(
            Voucher.objects.get(pk=capitalization.outbox.dea_voucher_id).status,
            VoucherStatus.REVERSED,
        )

    def test_release_readiness_uses_tenant_rate_and_canonical_balance(self):
        self._activate_loan()
        rate_source = RateSource.objects.create(name="Local", location="Market")
        rate = self._create_release_rate(rate_source)
        collateral = self.loan.collateral_items.get()

        readiness = get_pawn_loan_release_readiness(
            self.loan.pk,
            selected_item_ids=(collateral.pk,),
            as_of_date=date(2026, 8, 3),
        )

        self.assertTrue(readiness.ready)
        self.assertTrue(readiness.is_full_release)
        self.assertEqual(
            readiness.item_valuations[0].calculated_metal_value,
            Decimal("49464.00"),
        )
        self.assertEqual(readiness.item_valuations[0].rate_id, rate.pk)
        self.assertEqual(readiness.minimum_settlement, Decimal("50000.00"))

    def test_full_release_posts_settlement_returns_custody_and_closes(self):
        self._activate_loan()
        source = RateSource.objects.create(name="Release", location="Market")
        self._create_release_rate(source)

        with self.captureOnCommitCallbacks(execute=True):
            result = release_pawn_loan_in_full(
                self.loan.pk,
                settlement_amount=Decimal("51000.00"),
                request_key="release-1",
                actor=self.actor,
            )

        result.outbox.refresh_from_db()
        self.loan.refresh_from_db()
        collateral = self.loan.collateral_items.get()
        self.assertEqual(self.loan.state, PawnLoanState.CLOSED.value)
        self.assertEqual(
            collateral.custody_state,
            CollateralCustodyState.WITH_CUSTOMER.value,
        )
        self.assertEqual(result.release.release_number, "RL-A-00001")
        self.assertEqual(result.release.interest_amount, Decimal("1000.00"))
        self.assertEqual(
            self.loan.interest_accruals.get().period_fraction,
            Decimal("1.0000"),
        )
        self.assertEqual(result.outbox.status, LoanOutboxStatus.POSTED.value)
        self.assertEqual(PawnLoanRelease.objects.filter(loan=self.loan).count(), 1)
        self.assertEqual(
            PawnCollateralCustodyEvent.objects.filter(
                collateral_item=collateral,
                from_state=CollateralCustodyState.IN_VAULT.value,
                to_state=CollateralCustodyState.WITH_CUSTOMER.value,
            ).count(),
            1,
        )
        balance = get_pawn_loan_balance(
            self.loan.pk,
            as_of_date=date(2026, 8, 3),
        )
        self.assertTrue(balance.financially_settled)
        self.assertTrue(balance.collateral_return_complete)
        self.assertTrue(balance.closure_ready)

        repeated = release_pawn_loan_in_full(
            self.loan.pk,
            settlement_amount=Decimal("51000.00"),
            request_key="release-1",
            actor=self.actor,
        )
        self.assertTrue(repeated.already_released)
        self.assertEqual(repeated.release.pk, result.release.pk)

    def test_full_release_fails_before_mutation_when_accrual_is_missing(self):
        self._activate_loan()
        with patch(
            "apps.tenant_apps.loans.services.pawn_release.preview_pawn_loan_accruals",
            return_value=(object(),),
        ):
            with self.assertRaises(PawnReleaseError):
                release_pawn_loan_in_full(
                    self.loan.pk,
                    settlement_amount=Decimal("50000.00"),
                    request_key="release-missing-accrual",
                    actor=self.actor,
                )

        self.loan.refresh_from_db()
        self.assertEqual(self.loan.state, PawnLoanState.ACTIVE.value)
        self.assertFalse(PawnLoanRelease.objects.filter(loan=self.loan).exists())
        self.assertEqual(
            self.loan.collateral_items.get().custody_state,
            CollateralCustodyState.IN_VAULT.value,
        )

    def test_partial_collateral_release_is_rejected_without_mutation(self):
        selected_item = self.loan.collateral_items.get()

        with self.assertRaisesRegex(PawnReleaseError, "release and renew"):
            release_pawn_loan_partially(
                self.loan.pk,
                selected_item_ids=(selected_item.pk,),
                settlement_amount=Decimal("0.00"),
                request_key="unsupported-partial-release",
                actor=self.actor,
            )

        self.assertFalse(PawnLoanRelease.objects.filter(loan=self.loan).exists())
        selected_item.refresh_from_db()
        self.assertEqual(
            selected_item.custody_state,
            CollateralCustodyState.IN_VAULT.value,
        )

    def test_full_release_reversal_restores_accounting_custody_and_lifecycle(self):
        self._activate_loan()
        source = RateSource.objects.create(name="Reversal", location="Market")
        self._create_release_rate(source)
        with self.captureOnCommitCallbacks(execute=True):
            released = release_pawn_loan_in_full(
                self.loan.pk,
                settlement_amount=Decimal("51000.00"),
                request_key="release-to-reverse",
                actor=self.actor,
            )
        released.outbox.refresh_from_db()
        original_payload = released.accounting_event.payload
        collateral = self.loan.collateral_items.get()

        with self.assertRaises(PawnReversalError):
            reverse_pawn_loan_event(
                released.accounting_event.pk,
                reason="Unauthorized correction",
                actor=self.actor,
            )
        collateral.custody_state = CollateralCustodyState.WITH_FUNDING_LENDER.value
        collateral.save(update_fields=["custody_state", "updated_at"])
        with self.assertRaises(PawnReversalError):
            reverse_pawn_loan_event(
                released.accounting_event.pk,
                reason="Custody is incompatible",
                actor=self.tenant.owner,
            )
        collateral.custody_state = CollateralCustodyState.WITH_CUSTOMER.value
        collateral.save(update_fields=["custody_state", "updated_at"])

        with self.captureOnCommitCallbacks(execute=True):
            reversed_release = reverse_pawn_loan_event(
                released.accounting_event.pk,
                reason="Release recorded before physical handoff",
                actor=self.tenant.owner,
            )
        reversed_release.outbox.refresh_from_db()
        reversed_release.catch_up_reversal_event.outbox.refresh_from_db()
        self.loan.refresh_from_db()
        collateral.refresh_from_db()
        released.accounting_event.refresh_from_db()

        self.assertEqual(reversed_release.outbox.status, LoanOutboxStatus.POSTED.value)
        self.assertEqual(
            reversed_release.catch_up_reversal_event.outbox.status,
            LoanOutboxStatus.POSTED.value,
        )
        self.assertEqual(self.loan.state, PawnLoanState.ACTIVE.value)
        self.assertEqual(
            collateral.custody_state,
            CollateralCustodyState.IN_VAULT.value,
        )
        self.assertEqual(released.accounting_event.payload, original_payload)
        self.assertEqual(PawnLoanRelease.objects.filter(loan=self.loan).count(), 1)
        reversal_record = PawnLoanReleaseReversal.objects.get(
            release=released.release
        )
        self.assertEqual(
            reversal_record.reason,
            "Release recorded before physical handoff",
        )
        self.assertEqual(released.release.custody_events.count(), 2)
        balance = get_pawn_loan_balance(
            self.loan.pk,
            as_of_date=date(2026, 8, 3),
        )
        self.assertEqual(balance.principal_outstanding, Decimal("50000.00"))
        self.assertEqual(balance.interest_outstanding, Decimal("0.00"))
        self.assertFalse(balance.collateral_return_complete)
        restarted = preview_pawn_loan_accruals(
            self.loan.pk,
            as_of_date=date(2026, 8, 3),
        )[0]
        self.assertEqual(restarted.period_number, 1)
        self.assertEqual(restarted.period_start, date(2026, 8, 3))
        original_voucher = Voucher.objects.get(pk=released.outbox.dea_voucher_id)
        self.assertEqual(original_voucher.status, VoucherStatus.REVERSED)

        repeated = reverse_pawn_loan_event(
            released.accounting_event.pk,
            reason="Release recorded before physical handoff",
            actor=self.tenant.owner,
        )
        self.assertTrue(repeated.already_reversed)
        self.assertEqual(repeated.release_reversal.pk, reversal_record.pk)

    def test_auction_recovery_posts_closes_and_reverses_with_custody_evidence(self):
        self._activate_loan()
        self._open_period(date(2026, 12, 1), date(2026, 12, 31), "December 2026")
        self.loan.borrower.primary_email = "auction-borrower@example.com"
        self.loan.borrower.save(update_fields=["primary_email"])

        with patch(
            "apps.tenant_apps.loans.services.pawn_auctions.timezone.localdate",
            return_value=date(2026, 12, 4),
        ), patch(
            "apps.tenant_apps.loans.services.pawn_notices.timezone.localdate",
            return_value=date(2026, 12, 4),
        ), patch(
            "apps.tenant_apps.loans.services.pawn_notices.timezone.now",
            return_value=timezone.make_aware(datetime(2026, 12, 4, 10, 0)),
        ):
            with self.captureOnCommitCallbacks(execute=True):
                auction = initiate_pawn_loan_auction(
                    self.loan.pk,
                    scheduled_date=date(2026, 12, 5),
                    channel="EMAIL",
                    request_key="auction-1",
                    actor=self.tenant.owner,
                )

        notice = auction.notice
        NotificationJob.objects.filter(pk=notice.notification_job_id).update(
            status=NotificationJob.Status.SENT,
            sent_at=timezone.now(),
        )
        with patch(
            "apps.tenant_apps.loans.services.pawn_auctions.timezone.localdate",
            return_value=date(2026, 12, 5),
        ):
            auction = start_pawn_loan_auction(auction.pk, actor=self.tenant.owner)
            with patch(
                "apps.tenant_apps.loans.services.pawn_auctions.preview_pawn_loan_accruals",
                return_value=(),
            ):
                with self.assertRaisesRegex(PawnAuctionError, "exactly clear"):
                    complete_pawn_loan_auction(
                        auction.pk,
                        recovery_amount=Decimal("49999.00"),
                        buyer_name="Auction Buyer",
                        actor=self.tenant.owner,
                    )
                with self.captureOnCommitCallbacks(execute=True):
                    completed = complete_pawn_loan_auction(
                        auction.pk,
                        recovery_amount=Decimal("50000.00"),
                        buyer_name="Auction Buyer",
                        buyer_reference="SALE-001",
                        actor=self.tenant.owner,
                    )

        completed.outbox.refresh_from_db()
        self.loan.refresh_from_db()
        collateral = self.loan.collateral_items.get()
        collateral.refresh_from_db()
        self.assertEqual(completed.outbox.status, LoanOutboxStatus.POSTED.value)
        self.assertEqual(completed.accounting_event.event_kind, TransactionKind.AUCTION_RECOVERY.value)
        self.assertEqual(self.loan.state, PawnLoanState.CLOSED.value)
        self.assertEqual(collateral.custody_state, CollateralCustodyState.AUCTION_DISPOSED.value)
        self.assertEqual(completed.auction.items.count(), 1)
        self.assertEqual(completed.auction.items.get().snapshot["description"], "Gold")
        with self.assertRaisesRegex(PawnReversalError, "auction reversal workflow"):
            reverse_pawn_loan_event(
                completed.accounting_event.pk,
                reason="Must restore custody too",
                actor=self.tenant.owner,
            )

        with patch(
            "apps.tenant_apps.loans.services.pawn_auctions.timezone.localdate",
            return_value=date(2026, 12, 5),
        ):
            with self.captureOnCommitCallbacks(execute=True):
                reversed_auction = reverse_pawn_loan_auction(
                    completed.auction.pk,
                    reason="Buyer settlement was voided",
                    actor=self.tenant.owner,
                )

        reversed_auction.recovery_reversal_event.outbox.refresh_from_db()
        self.loan.refresh_from_db()
        collateral.refresh_from_db()
        self.assertEqual(
            reversed_auction.recovery_reversal_event.outbox.status,
            LoanOutboxStatus.POSTED.value,
        )
        self.assertEqual(self.loan.state, PawnLoanState.ACTIVE.value)
        self.assertEqual(collateral.custody_state, CollateralCustodyState.IN_VAULT.value)
        self.assertTrue(PawnLoanAuctionReversal.objects.filter(auction=auction).exists())

    def test_in_progress_auction_can_be_cancelled_but_requires_admin_reason(self):
        self._activate_loan()
        self.loan.borrower.primary_email = "cancel-auction@example.com"
        self.loan.borrower.save(update_fields=["primary_email"])
        with patch(
            "apps.tenant_apps.loans.services.pawn_auctions.timezone.localdate",
            return_value=date(2026, 12, 4),
        ), patch(
            "apps.tenant_apps.loans.services.pawn_notices.timezone.localdate",
            return_value=date(2026, 12, 4),
        ), patch(
            "apps.tenant_apps.loans.services.pawn_notices.timezone.now",
            return_value=timezone.make_aware(datetime(2026, 12, 4, 10, 0)),
        ):
            auction = initiate_pawn_loan_auction(
                self.loan.pk,
                scheduled_date=date(2026, 12, 5),
                channel="EMAIL",
                request_key="auction-cancel",
                actor=self.tenant.owner,
            )
        NotificationJob.objects.filter(pk=auction.notice.notification_job_id).update(
            status=NotificationJob.Status.SENT,
            sent_at=timezone.now(),
        )
        with patch(
            "apps.tenant_apps.loans.services.pawn_auctions.timezone.localdate",
            return_value=date(2026, 12, 5),
        ):
            auction = start_pawn_loan_auction(auction.pk, actor=self.tenant.owner)
        with self.assertRaisesRegex(PawnAuctionError, "requires a reason"):
            cancel_pawn_loan_auction(auction.pk, reason="", actor=self.tenant.owner)
        cancelled = cancel_pawn_loan_auction(
            auction.pk,
            reason="Borrower settled before auction",
            actor=self.tenant.owner,
        )
        self.assertEqual(cancelled.state, "CANCELLED")
        self.assertEqual(PawnLoanAuction.objects.filter(loan=self.loan).count(), 1)

    def test_pay_and_renew_posts_net_settlement_and_composite_reversal(self):
        self._activate_loan()
        self._create_release_rate(
            RateSource.objects.create(name="Renewal", location="Market")
        )
        with patch(
            "apps.tenant_apps.loans.services.pawn_renewals.timezone.localdate",
            return_value=date(2026, 8, 3),
        ), patch(
            "apps.tenant_apps.loans.services.pawn_renewals.preview_pawn_loan_accruals",
            return_value=(),
        ), self.captureOnCommitCallbacks(execute=True):
            result = renew_pawn_loan(
                self.loan.pk,
                mode=PawnLoanRenewalMode.PAY_AND_RENEW,
                renewal_date=date(2026, 8, 3),
                principal_paid=Decimal("11000.00"),
                top_up_amount=Decimal("0.00"),
                successor_license_id=self.loan.license_id,
                successor_series_id=self.loan.series_id,
                monthly_interest_rate=Decimal("2.000000"),
                tenure_months=3,
                request_key="renew-paydown-1",
                actor=self.actor,
            )

        result.source_loan.refresh_from_db()
        result.successor_loan.refresh_from_db()
        result.settlement_outbox.refresh_from_db()
        result.opening_outbox.refresh_from_db()
        self.assertEqual(result.source_loan.state, PawnLoanState.CLOSED.value)
        self.assertEqual(result.successor_loan.state, PawnLoanState.ACTIVE.value)
        self.assertEqual(result.renewal.successor_principal_amount, Decimal("39000.00"))
        self.assertIsNotNone(result.settlement_outbox.dea_voucher_id)
        self.assertIsNone(result.opening_outbox.dea_voucher_id)
        self.assertEqual(
            get_pawn_loan_balance(self.loan.pk, as_of_date=date(2026, 8, 3)).principal_outstanding,
            Decimal("0.00"),
        )
        self.assertEqual(
            get_pawn_loan_balance(result.successor_loan.pk, as_of_date=date(2026, 8, 3)).principal_outstanding,
            Decimal("39000.00"),
        )
        source_item = self.loan.collateral_items.get()
        successor_item = result.successor_loan.collateral_items.get()
        self.assertEqual(source_item.custody_state, CollateralCustodyState.RENEWAL_TRANSFERRED.value)
        self.assertEqual(successor_item.renewed_from_id, source_item.pk)
        reports = get_pawn_loan_reports(as_of_date=date(2026, 8, 3))
        self.assertEqual(
            [(issue.code, issue.loan.loan_number) for issue in reports.issues],
            [],
        )

        with self.assertRaisesRegex(PawnReversalError, "renewal reversal workflow"):
            reverse_pawn_loan_event(
                result.settlement_event.pk,
                reason="Use composite reversal",
                actor=self.tenant.owner,
            )
        with self.captureOnCommitCallbacks(execute=True):
            reversed_result = reverse_pawn_loan_renewal(
                result.renewal.pk,
                reason="Renewal entered against the wrong series",
                actor=self.tenant.owner,
            )

        result.source_loan.refresh_from_db()
        result.successor_loan.refresh_from_db()
        source_item.refresh_from_db()
        successor_item.refresh_from_db()
        self.assertEqual(result.source_loan.state, PawnLoanState.ACTIVE.value)
        self.assertEqual(result.successor_loan.state, PawnLoanState.CANCELLED.value)
        self.assertEqual(source_item.custody_state, CollateralCustodyState.IN_VAULT.value)
        self.assertEqual(successor_item.custody_state, CollateralCustodyState.RENEWAL_REVERSED.value)
        self.assertTrue(PawnLoanRenewalReversal.objects.filter(renewal=result.renewal).exists())
        self.assertEqual(
            get_pawn_loan_balance(self.loan.pk, as_of_date=date(2026, 8, 4)).principal_outstanding,
            Decimal("50000.00"),
        )
        self.assertEqual(
            get_pawn_loan_balance(result.successor_loan.pk, as_of_date=date(2026, 8, 4)).principal_outstanding,
            Decimal("0.00"),
        )
        self.assertFalse(reversed_result.already_reversed)

    def test_release_and_renew_returns_omitted_and_accepts_added_collateral(self):
        returned_item = PawnCollateralItem.objects.create(
            loan=self.loan,
            description="Returned gold bracelet",
            metal=CollateralMetal.GOLD.value,
            gross_weight=Decimal("10"),
            net_weight=Decimal("9"),
            purity_percentage=Decimal("91.6"),
            latest_appraised_value=Decimal("50000.00"),
        )
        self._activate_loan()
        self._create_release_rate(
            RateSource.objects.create(name="Release renew", location="Market")
        )
        create_pawn_metal_interest_rate_policy(
            workspace=self.tenant,
            license=self.loan.license,
            metal=CollateralMetal.SILVER,
            monthly_interest_rate=Decimal("4"),
            effective_from=date(2026, 1, 1),
        )
        retained_item = self.loan.collateral_items.exclude(pk=returned_item.pk).get()

        with patch(
            "apps.tenant_apps.loans.services.pawn_renewals.timezone.localdate",
            return_value=date(2026, 8, 3),
        ), patch(
            "apps.tenant_apps.loans.services.pawn_renewals.preview_pawn_loan_accruals",
            return_value=(),
        ), self.captureOnCommitCallbacks(execute=True):
            result = renew_pawn_loan(
                self.loan.pk,
                mode=PawnLoanRenewalMode.PAY_AND_RENEW,
                renewal_date=date(2026, 8, 3),
                principal_paid=Decimal("11000.00"),
                top_up_amount=Decimal("0.00"),
                successor_license_id=self.loan.license_id,
                successor_series_id=self.loan.series_id,
                tenure_months=3,
                request_key="release-renew-collateral-plan",
                retained_collateral=(
                    RetainedCollateralInput(retained_item.pk, Decimal("30000.00")),
                ),
                additional_collateral=(
                    CollateralDraftInput(
                        description="Added silver anklet",
                        metal=CollateralMetal.SILVER,
                        gross_weight=Decimal("100"),
                        net_weight=Decimal("95"),
                        purity_percentage=Decimal("90"),
                        latest_appraised_value=Decimal("50000.00"),
                        allocated_principal=Decimal("9000.00"),
                    ),
                ),
                additional_photo_uploads=(
                    SimpleUploadedFile(
                        "added-silver.jpg",
                        b"\xff\xd8\xff\xe0renewal-evidence",
                        content_type="image/jpeg",
                    ),
                ),
                actor=self.actor,
            )

        retained_item.refresh_from_db()
        returned_item.refresh_from_db()
        successor_items = tuple(
            result.successor_loan.collateral_items.order_by("pk")
        )
        self.assertEqual(
            retained_item.custody_state,
            CollateralCustodyState.RENEWAL_TRANSFERRED.value,
        )
        self.assertEqual(
            returned_item.custody_state,
            CollateralCustodyState.WITH_CUSTOMER.value,
        )
        self.assertEqual(len(successor_items), 2)
        self.assertEqual(successor_items[0].renewed_from_id, retained_item.pk)
        self.assertIsNone(successor_items[1].renewed_from_id)
        self.assertEqual(successor_items[0].allocated_principal, Decimal("30000.0000"))
        self.assertEqual(successor_items[1].allocated_principal, Decimal("9000.0000"))
        self.assertEqual(successor_items[0].monthly_interest_rate, Decimal("2.000000"))
        self.assertEqual(successor_items[1].monthly_interest_rate, Decimal("4.000000"))
        opening_lines = tuple(
            PawnLoanPrincipalOpeningLine.objects.filter(
                accounting_event=result.opening_event
            ).order_by("allocation_order")
        )
        self.assertEqual(len(opening_lines), 2)
        self.assertEqual(opening_lines[0].predecessor_collateral_item_id, retained_item.pk)
        self.assertIsNone(opening_lines[1].predecessor_collateral_item_id)
        self.assertEqual(
            sum((line.principal_opened for line in opening_lines), Decimal("0")),
            Decimal("39000.0000"),
        )
        with self.assertRaisesRegex(ValidationError, "immutable"):
            opening_lines[0].save()
        reconstructed = get_pawn_principal_tranche_balances(result.successor_loan)
        self.assertEqual(
            sum((row.principal_outstanding for row in reconstructed), Decimal("0")),
            Decimal("39000.0000"),
        )
        successor_preview = preview_pawn_loan_accruals(
            result.successor_loan.pk,
            as_of_date=date(2026, 9, 2),
            include_partial=False,
        )[0]
        self.assertEqual(successor_preview.calculation_base, Decimal("39000.0000"))
        self.assertEqual(successor_preview.recognized_interest, Decimal("960.00"))
        reports = get_pawn_loan_reports(as_of_date=date(2026, 8, 3))
        self.assertEqual(
            [
                (issue.code, issue.loan.loan_number)
                for issue in reports.issues
            ],
            [],
        )

        with self.captureOnCommitCallbacks(execute=True):
            reversed_result = reverse_pawn_loan_renewal(
                result.renewal.pk,
                reason="Collateral selection was recorded incorrectly",
                actor=self.tenant.owner,
            )
        retained_item.refresh_from_db()
        returned_item.refresh_from_db()
        result.source_loan.refresh_from_db()
        result.successor_loan.refresh_from_db()
        self.assertEqual(result.source_loan.state, PawnLoanState.ACTIVE.value)
        self.assertEqual(result.successor_loan.state, PawnLoanState.CANCELLED.value)
        self.assertEqual(retained_item.custody_state, CollateralCustodyState.IN_VAULT.value)
        self.assertEqual(returned_item.custody_state, CollateralCustodyState.IN_VAULT.value)
        self.assertTrue(
            result.opening_event.reversed_by_event.pk
            == reversed_result.opening_reversal_event.pk
        )
        self.assertEqual(
            sum(
                (
                    row.principal_outstanding
                    for row in get_pawn_principal_tranche_balances(
                        result.successor_loan
                    )
                ),
                Decimal("0"),
            ),
            Decimal("0"),
        )

    def test_renewal_is_idempotent(self):
        self._activate_loan()
        self._create_release_rate(
            RateSource.objects.create(name="Renew idem", location="Market")
        )
        call = dict(
            mode=PawnLoanRenewalMode.PAY_AND_RENEW,
            renewal_date=date(2026, 8, 3),
            principal_paid=Decimal("11000.00"),
            top_up_amount=Decimal("0.00"),
            successor_license_id=self.loan.license_id,
            successor_series_id=self.loan.series_id,
            monthly_interest_rate=Decimal("2.000000"),
            tenure_months=3,
            request_key="renew-idempotent-1",
            actor=self.actor,
        )
        with patch(
            "apps.tenant_apps.loans.services.pawn_renewals.timezone.localdate",
            return_value=date(2026, 8, 3),
        ), patch(
            "apps.tenant_apps.loans.services.pawn_renewals.preview_pawn_loan_accruals",
            return_value=(),
        ), self.captureOnCommitCallbacks(execute=True):
            first = renew_pawn_loan(self.loan.pk, **call)
            second = renew_pawn_loan(self.loan.pk, **call)

        self.assertFalse(first.already_renewed)
        self.assertTrue(second.already_renewed)
        self.assertEqual(first.renewal.pk, second.renewal.pk)
        self.assertEqual(PawnLoanRenewal.objects.filter(source_loan=self.loan).count(), 1)

    def test_top_up_renewal_rejects_principal_above_snapshot_ltv(self):
        self._activate_loan()
        self._create_release_rate(
            RateSource.objects.create(name="Renew LTV", location="Market")
        )
        with patch(
            "apps.tenant_apps.loans.services.pawn_renewals.timezone.localdate",
            return_value=date(2026, 8, 3),
        ), patch(
            "apps.tenant_apps.loans.services.pawn_renewals.preview_pawn_loan_accruals",
            return_value=(),
        ):
            with self.assertRaisesRegex(PawnRenewalError, "exceeds the allowed"):
                renew_pawn_loan(
                    self.loan.pk,
                    mode=PawnLoanRenewalMode.TOP_UP_RENEW,
                    renewal_date=date(2026, 8, 3),
                    principal_paid=Decimal("0.00"),
                    top_up_amount=Decimal("1000.00"),
                    successor_license_id=self.loan.license_id,
                    successor_series_id=self.loan.series_id,
                    monthly_interest_rate=Decimal("2.000000"),
                    tenure_months=3,
                    request_key="renew-topup-ltv",
                    actor=self.actor,
                )

        self.loan.refresh_from_db()
        self.assertEqual(self.loan.state, PawnLoanState.ACTIVE.value)
        self.assertFalse(PawnLoanRenewal.objects.filter(source_loan=self.loan).exists())

    def test_top_up_renewal_increases_successor_principal_with_net_cash_posting(self):
        self.loan.collateral_items.update(latest_appraised_value=Decimal("100000.00"))
        policy = resolve_policy(
            WorkspacePolicyDefaults(
                valuation_method=ValuationMethod.LATEST_APPRAISAL,
                maximum_ltv_ratio=Decimal("0.80"),
            )
        )
        self._activate_loan(policy=policy)
        with patch(
            "apps.tenant_apps.loans.services.pawn_renewals.timezone.localdate",
            return_value=date(2026, 8, 3),
        ), patch(
            "apps.tenant_apps.loans.services.pawn_renewals.preview_pawn_loan_accruals",
            return_value=(),
        ), self.captureOnCommitCallbacks(execute=True):
            result = renew_pawn_loan(
                self.loan.pk,
                mode=PawnLoanRenewalMode.TOP_UP_RENEW,
                renewal_date=date(2026, 8, 3),
                principal_paid=Decimal("0.00"),
                top_up_amount=Decimal("10000.00"),
                successor_license_id=self.loan.license_id,
                successor_series_id=self.loan.series_id,
                monthly_interest_rate=Decimal("2.000000"),
                tenure_months=3,
                request_key="renew-topup-success",
                actor=self.actor,
            )

        result.settlement_outbox.refresh_from_db()
        self.assertEqual(result.renewal.successor_principal_amount, Decimal("60000.00"))
        self.assertIsNotNone(result.settlement_outbox.dea_voucher_id)
        voucher = Voucher.objects.get(pk=result.settlement_outbox.dea_voucher_id)
        self.assertEqual(
            voucher.lines.get(side="Dr", account__isnull=True).amount.amount,
            Decimal("10000.00"),
        )

    def _activate_loan(self, policy=None):
        self._seed_dea_disbursal_setup()
        policy_patch = patch(
            "apps.tenant_apps.loans.services.pawn_disbursal.resolve_policy",
            return_value=policy,
        ) if policy else None
        if policy_patch:
            policy_patch.start()
        try:
            with self.captureOnCommitCallbacks(execute=True):
                result = disburse_pawn_loan(
                    self.loan.pk,
                    effective_date=date(2026, 8, 3),
                    actor=self.actor,
                )
        finally:
            if policy_patch:
                policy_patch.stop()
        result.outbox.refresh_from_db()
        self.assertEqual(result.outbox.status, LoanOutboxStatus.POSTED.value)
        return result

    def _create_release_rate(self, source):
        rate = Rate.objects.create(
            metal=Rate.Metal.GOLD,
            currency=Rate.Currency.INR,
            purity=Rate.Purity.K24,
            buying_rate=Decimal("6000.00"),
            selling_rate=Decimal("6100.00"),
            rate_source=source,
        )
        Rate.objects.filter(pk=rate.pk).update(
            timestamp=timezone.make_aware(datetime(2026, 8, 3, 12, 0))
        )
        rate.refresh_from_db()
        return rate

    def _open_period(self, start, end, name):
        AccountingPeriod.objects.get_or_create(
            start_date=start,
            end_date=end,
            defaults={"name": name, "status": "OPEN"},
        )

    def _seed_dea_disbursal_setup(self, *, include_borrower_account=True):
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
        if include_borrower_account:
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
