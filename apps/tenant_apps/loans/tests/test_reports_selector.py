from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.tenant_apps.loans.domain import (
    CollateralCustodyState,
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
            license_expiry=(license_row,),
        )

        self.assertEqual(report.active_loans[0].loan, loan)
        self.assertEqual(report.daily_disbursals, (disbursal,))
        self.assertEqual(report.daily_repayments, (repayment,))
        self.assertEqual(report.storage_inventory, tuple(loan.collateral_items.all()))
        self.assertEqual(report.license_expiry, (license_row,))

    def test_daily_activity_exposes_original_and_compensating_correction_evidence(self):
        disbursal = self._event(1, TransactionKind.DISBURSAL, principal="1000")
        repayment = self._event(2, TransactionKind.REPAYMENT, principal="200")
        reversal = self._event(3, TransactionKind.REVERSAL, principal="200")
        for event in (disbursal, repayment, reversal):
            event.effective_date = self.as_of
        reversal.reversal_of_id = repayment.pk
        reversal.reversal_of = repayment
        reversal.payload["reversal"] = {
            "original_event_kind": TransactionKind.REPAYMENT.value,
            "reason": "Duplicate receipt",
        }
        repayment.reversed_by_event = reversal
        loan = self._loan(events=(disbursal, repayment, reversal))

        report = build_pawn_loan_reports(
            (loan,),
            as_of_date=self.as_of,
        )

        self.assertEqual(
            [row.correction_status for row in report.daily_activity],
            ["CURRENT", "REVERSED", "COMPENSATION"],
        )
        self.assertEqual(report.daily_activity[1].correction_event_id, reversal.pk)
        self.assertEqual(report.daily_activity[2].correction_event_id, repayment.pk)
        self.assertEqual(report.daily_activity[2].amount, Decimal("-200"))
        self.assertEqual(report.daily_activity[2].principal, Decimal("-200"))

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
        )

        codes = {issue.code for issue in report.issues}
        self.assertIn("DUPLICATE_EVENT_INTENT", codes)
        self.assertIn("IMPOSSIBLE_CUSTODY", codes)
        self.assertIn("CLOSED_LOAN_NOT_RECONCILED", codes)

    def test_interest_accrual_is_valid_operational_history(self):
        disbursal = self._event(1, TransactionKind.DISBURSAL, principal="1000")
        accrual = self._event(
            2,
            TransactionKind.INTEREST_ACCRUAL,
            interest="100",
        )
        loan = self._loan(events=(disbursal, accrual))

        report = build_pawn_loan_reports(
            (loan,),
            as_of_date=self.as_of,
        )

        self.assertEqual(report.issues, ())

    def test_itemized_renewal_opening_without_lines_is_reconciliation_error(self):
        opening = self._event(
            1,
            TransactionKind.RENEWAL_OPENING,
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
        )

        self.assertEqual(report.renewals, (renewal,))

    def test_itemized_opening_mismatch_is_reconciliation_error(self):
        opening = self._event(
            1,
            TransactionKind.RENEWAL_OPENING,
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
            loan_events=_Manager(*events),
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
        **values,
    ):
        event = SimpleNamespace(
            pk=pk,
            event_kind=kind.value,
            effective_date=date(2026, 2, 1),
            payload={"values": values, "reversal": None},
            payload_fingerprint=f"fingerprint-{pk}",
            idempotency_key=f"event-{pk}",
            reversal_of_id=None,
        )
        return event

    def _collateral(self, state):
        return SimpleNamespace(
            pk=501,
            custody_state=state.value,
            custody_history=_Manager(),
            release_items=_Manager(),
        )
