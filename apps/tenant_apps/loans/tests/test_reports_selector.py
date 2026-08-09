from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.tenant_apps.loans.domain import (
    CollateralCustodyState,
    LoanOutboxStatus,
    PawnLoanState,
    TransactionKind,
)
from apps.tenant_apps.loans.selectors import build_pawn_loan_reports


class _Manager:
    def __init__(self, *values):
        self.values = values

    def all(self):
        return self.values

    def exists(self):
        return bool(self.values)


class PawnLoanReportsSelectorTests(SimpleTestCase):
    as_of = date(2026, 8, 3)

    def test_portfolio_and_transaction_reports_use_canonical_event_fold(self):
        event = self._event(1, TransactionKind.DISBURSAL, principal="1000")
        repayment = self._event(
            2,
            TransactionKind.REPAYMENT,
            principal="200",
            interest="0",
        )
        loan = self._loan(events=(event, repayment))

        report = build_pawn_loan_reports(
            (loan,),
            as_of_date=self.as_of,
            dea_inspector=self._matching_evidence,
        )

        self.assertEqual(report.active_count, 1)
        self.assertEqual(report.total_principal_outstanding, Decimal("800.00"))
        self.assertEqual(report.total_due, Decimal("800.00"))
        self.assertEqual(report.repayments, (repayment,))
        self.assertEqual(report.portfolio[0].status, "OVERDUE")
        self.assertEqual(report.issues, ())

    def test_pilot_views_are_derived_from_the_same_report_bundle(self):
        disbursal = self._event(1, TransactionKind.DISBURSAL, principal="1000")
        repayment = self._event(2, TransactionKind.REPAYMENT, principal="200")
        disbursal.effective_date = self.as_of
        repayment.effective_date = self.as_of
        loan = self._loan(events=(disbursal, repayment))
        license_row = SimpleNamespace(status="EXPIRING")

        report = build_pawn_loan_reports(
            (loan,),
            as_of_date=self.as_of,
            dea_inspector=self._matching_evidence,
            license_expiry=(license_row,),
        )

        self.assertEqual(report.active_loans[0].loan, loan)
        self.assertEqual(report.daily_disbursals, (disbursal,))
        self.assertEqual(report.daily_repayments, (repayment,))
        self.assertEqual(report.storage_inventory, tuple(loan.collateral_items.all()))
        self.assertEqual(report.license_expiry, (license_row,))

    def test_missing_and_failed_accounting_are_categorized(self):
        failed = self._event(
            2,
            TransactionKind.REPAYMENT,
            status=LoanOutboxStatus.FAILED,
            error="DEA period is closed",
            principal="10",
        )
        loan = self._loan(events=(failed,))

        report = build_pawn_loan_reports(
            (loan,),
            as_of_date=self.as_of,
            dea_inspector=self._matching_evidence,
        )

        codes = {issue.code for issue in report.issues}
        self.assertIn("MISSING_DISBURSAL_EVENT", codes)
        self.assertIn("FAILED_ACCOUNTING_DELIVERY", codes)

    def test_duplicate_intent_and_impossible_custody_are_categorized(self):
        first = self._event(1, TransactionKind.DISBURSAL, principal="1000")
        duplicate = self._event(2, TransactionKind.DISBURSAL, principal="1000")
        duplicate.payload_fingerprint = first.payload_fingerprint
        item = self._collateral(CollateralCustodyState.IN_VAULT)
        loan = self._loan(
            state=PawnLoanState.CLOSED,
            events=(first, duplicate),
            collateral=(item,),
        )

        report = build_pawn_loan_reports(
            (loan,),
            as_of_date=self.as_of,
            dea_inspector=self._matching_evidence,
        )

        codes = {issue.code for issue in report.issues}
        self.assertIn("DUPLICATE_ACCOUNTING_INTENT", codes)
        self.assertIn("IMPOSSIBLE_CUSTODY", codes)
        self.assertIn("CLOSED_LOAN_NOT_RECONCILED", codes)

    def test_source_total_to_voucher_mismatch_is_categorized(self):
        event = self._event(1, TransactionKind.DISBURSAL, principal="1000")
        loan = self._loan(events=(event,))
        mismatch = SimpleNamespace(
            voucher_exists=True,
            journal_exists=True,
            source_matches=True,
            journal_matches_voucher=True,
            voucher_status="POSTED",
            source_voucher_count=1,
            debit_total=Decimal("900"),
            credit_total=Decimal("900"),
        )

        report = build_pawn_loan_reports(
            (loan,),
            as_of_date=self.as_of,
            dea_inspector=lambda **kwargs: mismatch,
        )

        self.assertIn(
            "BALANCE_VOUCHER_MISMATCH",
            {issue.code for issue in report.issues},
        )

    def test_cash_accrual_without_dea_reference_is_valid_operational_history(self):
        disbursal = self._event(1, TransactionKind.DISBURSAL, principal="1000")
        accrual = self._event(
            2,
            TransactionKind.INTEREST_ACCRUAL,
            interest="100",
            voucher_id=None,
            journal_id=None,
        )
        accrual.payload["accrual"] = {"accounting_recognition": "CASH"}
        loan = self._loan(events=(disbursal, accrual))

        report = build_pawn_loan_reports(
            (loan,),
            as_of_date=self.as_of,
            dea_inspector=self._matching_evidence,
        )

        self.assertNotIn(
            "MISSING_DEA_REFERENCE",
            {issue.code for issue in report.issues},
        )

    def test_reconciliation_reads_dea_only_through_public_facade(self):
        source = (
            Path(__file__).parents[1] / "selectors" / "reports.py"
        ).read_text(encoding="utf-8")

        self.assertIn("from apps.tenant_apps.dea import facade as dea_facade", source)
        self.assertNotIn("apps.tenant_apps.dea.models", source)
        self.assertNotIn("apps.tenant_apps.dea.services", source)

    def test_itemized_renewal_opening_without_lines_is_reconciliation_error(self):
        opening = self._event(
            1,
            TransactionKind.RENEWAL_OPENING,
            voucher_id=None,
            journal_id=None,
            principal="800",
            capitalized_interest_principal="0",
        )
        opening.principal_opening_lines = _Manager()
        item = self._collateral(CollateralCustodyState.IN_VAULT)
        item.allocated_principal = Decimal("800")
        item.monthly_interest_rate = Decimal("2")
        item.renewed_from_id = 400
        loan = self._loan(events=(opening,), collateral=(item,))

        report = build_pawn_loan_reports(
            (loan,),
            as_of_date=self.as_of,
            dea_inspector=self._matching_evidence,
        )

        self.assertIn(
            "MISSING_ITEM_PRINCIPAL_EVIDENCE",
            {issue.code for issue in report.issues},
        )

    def test_report_exposes_release_and_renew_once_from_source_loan(self):
        event = self._event(1, TransactionKind.DISBURSAL, principal="1000")
        renewal = SimpleNamespace(pk=91, renewal_number="REN-PL-A-00001")
        loan = self._loan(events=(event,))
        loan.renewal_as_source = renewal

        report = build_pawn_loan_reports(
            (loan,),
            as_of_date=self.as_of,
            dea_inspector=self._matching_evidence,
        )

        self.assertEqual(report.renewals, (renewal,))

    def test_itemized_opening_mismatch_is_reconciliation_error(self):
        opening = self._event(
            1,
            TransactionKind.RENEWAL_OPENING,
            voucher_id=None,
            journal_id=None,
            principal="800",
            capitalized_interest_principal="0",
        )
        item = self._collateral(CollateralCustodyState.IN_VAULT)
        item.allocated_principal = Decimal("800")
        item.monthly_interest_rate = Decimal("2")
        item.renewed_from_id = 400
        opening.principal_opening_lines = _Manager(
            SimpleNamespace(
                collateral_item_id=item.pk,
                principal_opened=Decimal("700"),
                monthly_interest_rate=Decimal("2"),
                predecessor_collateral_item_id=400,
            )
        )
        loan = self._loan(events=(opening,), collateral=(item,))

        report = build_pawn_loan_reports(
            (loan,),
            as_of_date=self.as_of,
            dea_inspector=self._matching_evidence,
        )

        self.assertIn(
            "ITEM_PRINCIPAL_EVIDENCE_MISMATCH",
            {issue.code for issue in report.issues},
        )

    def _loan(
        self,
        *,
        state=PawnLoanState.ACTIVE,
        events=(),
        collateral=None,
    ):
        if collateral is None:
            collateral = (self._collateral(CollateralCustodyState.IN_VAULT),)
        loan = SimpleNamespace(
            pk=71,
            loan_number="PL-A-00001",
            state=state.value,
            loan_date=date(2026, 1, 1),
            tenure_months=3,
            borrower=SimpleNamespace(display_name="Asha Devi"),
            accounting_events=_Manager(*events),
            collateral_items=_Manager(*collateral),
            interest_accruals=_Manager(),
            releases=_Manager(),
        )
        for event in events:
            event.loan = loan
        for item in collateral:
            item.loan = loan
        return loan

    def _event(
        self,
        pk,
        kind,
        *,
        status=LoanOutboxStatus.POSTED,
        error="",
        voucher_id=100,
        journal_id=200,
        **values,
    ):
        outbox = SimpleNamespace(
            status=status.value,
            last_error=error,
            dea_voucher_id=voucher_id,
            dea_journal_entry_id=journal_id,
            payload=None,
            payload_fingerprint=f"fingerprint-{pk}",
            idempotency_key=f"event-{pk}",
        )
        event = SimpleNamespace(
            pk=pk,
            event_kind=kind.value,
            effective_date=date(2026, 2, 1),
            payload={"values": values, "reversal": None},
            payload_fingerprint=f"fingerprint-{pk}",
            idempotency_key=f"event-{pk}",
            reversal_of_id=None,
            outbox=outbox,
        )
        outbox.payload = event.payload
        return event

    def _collateral(self, state):
        return SimpleNamespace(
            pk=501,
            custody_state=state.value,
            custody_history=_Manager(),
            release_items=_Manager(),
        )

    def _matching_evidence(self, **kwargs):
        return SimpleNamespace(
            voucher_exists=True,
            journal_exists=True,
            source_matches=True,
            journal_matches_voucher=True,
            voucher_status="POSTED",
            source_voucher_count=1,
            debit_total=Decimal("1000" if kwargs["source_event_id"] == 1 else "200"),
            credit_total=Decimal("1000" if kwargs["source_event_id"] == 1 else "200"),
        )
