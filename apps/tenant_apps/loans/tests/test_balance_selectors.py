from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.tenant_apps.loans.domain import (
    AccountingRecognition,
    CollateralCustodyState,
    InterestMethod,
    LoanOutboxStatus,
    TransactionKind,
)
from apps.tenant_apps.loans.selectors import (
    PawnLoanBalanceSelectorError,
    calculate_pawn_loan_balance,
)


class PawnLoanBalanceSelectorTests(SimpleTestCase):
    def setUp(self):
        self.loan = SimpleNamespace(
            pk=71,
            loan_date=date(2026, 1, 31),
            tenure_months=3,
        )

    def test_simple_cash_policy_centralizes_all_due_components_and_overdue(self):
        events = (
            self._event(1, TransactionKind.DISBURSAL, principal="10000"),
            self._event(
                2,
                TransactionKind.INTEREST_ACCRUAL,
                interest="500",
                fees_assessed="100",
            ),
            self._event(
                3,
                TransactionKind.REPAYMENT,
                principal="2000",
                interest="300",
                fees="100",
            ),
        )

        balance = calculate_pawn_loan_balance(
            self.loan,
            events=events,
            collateral_items=(self._collateral(CollateralCustodyState.IN_VAULT),),
            policy_snapshot=self._policy(InterestMethod.SIMPLE, AccountingRecognition.CASH),
            as_of_date=date(2026, 5, 1),
        )

        self.assertEqual(balance.due_date, date(2026, 4, 30))
        self.assertEqual(balance.principal_outstanding, Decimal("8000.00"))
        self.assertEqual(balance.interest_paid, Decimal("300.00"))
        self.assertEqual(balance.interest_outstanding, Decimal("200.00"))
        self.assertEqual(balance.overdue_interest_outstanding, Decimal("200.00"))
        self.assertEqual(balance.current_interest_outstanding, Decimal("0.00"))
        self.assertEqual(balance.fees_paid, Decimal("100.00"))
        self.assertEqual(balance.fees_outstanding, Decimal("0.00"))
        self.assertEqual(balance.total_due, Decimal("8200.00"))
        self.assertEqual(balance.interest_method, InterestMethod.SIMPLE.value)
        self.assertEqual(balance.accounting_recognition, AccountingRecognition.CASH.value)
        self.assertTrue(balance.is_overdue)
        self.assertTrue(balance.posting_ready)

    def test_compound_accrual_policy_moves_capitalized_interest_into_principal(self):
        events = (
            self._event(1, TransactionKind.DISBURSAL, principal="10000"),
            self._event(2, TransactionKind.INTEREST_ACCRUAL, interest="1000"),
            self._event(3, TransactionKind.INTEREST_CAPITALIZATION, interest="600"),
            self._event(
                4,
                TransactionKind.REPAYMENT,
                principal="500",
                interest="200",
            ),
        )

        balance = calculate_pawn_loan_balance(
            self.loan,
            events=events,
            collateral_items=(self._collateral(CollateralCustodyState.IN_VAULT),),
            policy_snapshot=self._policy(
                InterestMethod.COMPOUND,
                AccountingRecognition.ACCRUAL,
            ),
            as_of_date=date(2026, 4, 1),
        )

        self.assertEqual(balance.principal_capitalized, Decimal("600.00"))
        self.assertEqual(balance.principal_outstanding, Decimal("10100.00"))
        self.assertEqual(balance.interest_capitalized, Decimal("600.00"))
        self.assertEqual(balance.interest_outstanding, Decimal("200.00"))
        self.assertEqual(balance.overdue_interest_outstanding, Decimal("0.00"))
        self.assertEqual(balance.current_interest_outstanding, Decimal("200.00"))
        self.assertEqual(balance.total_due, Decimal("10300.00"))
        self.assertEqual(balance.interest_method, InterestMethod.COMPOUND.value)
        self.assertEqual(balance.accounting_recognition, AccountingRecognition.ACCRUAL.value)

    def test_reversal_applies_exact_inverse_of_original_event_kind(self):
        events = (
            self._event(1, TransactionKind.DISBURSAL, principal="10000"),
            self._event(
                2,
                TransactionKind.REPAYMENT,
                principal="1000",
                interest="100",
            ),
            self._event(
                3,
                TransactionKind.REVERSAL,
                principal="1000",
                interest="100",
                reversal={"original_event_kind": TransactionKind.REPAYMENT.value},
            ),
        )

        balance = calculate_pawn_loan_balance(
            self.loan,
            events=events,
            collateral_items=(self._collateral(CollateralCustodyState.IN_VAULT),),
            policy_snapshot=self._policy(InterestMethod.SIMPLE, AccountingRecognition.CASH),
            as_of_date=date(2026, 3, 1),
        )

        self.assertEqual(balance.principal_paid, Decimal("0.00"))
        self.assertEqual(balance.interest_paid, Decimal("0.00"))
        self.assertEqual(balance.principal_outstanding, Decimal("10000.00"))

    def test_closure_requires_zero_due_and_completed_collateral_return(self):
        events = (
            self._event(1, TransactionKind.DISBURSAL, principal="1000"),
            self._event(2, TransactionKind.REPAYMENT, principal="1000"),
        )
        common = {
            "events": events,
            "policy_snapshot": self._policy(
                InterestMethod.SIMPLE,
                AccountingRecognition.CASH,
            ),
            "as_of_date": date(2026, 3, 1),
        }

        in_vault = calculate_pawn_loan_balance(
            self.loan,
            collateral_items=(self._collateral(CollateralCustodyState.IN_VAULT),),
            **common,
        )
        returned = calculate_pawn_loan_balance(
            self.loan,
            collateral_items=(
                self._collateral(CollateralCustodyState.WITH_CUSTOMER),
            ),
            **common,
        )

        self.assertTrue(in_vault.financially_settled)
        self.assertFalse(in_vault.closure_ready)
        self.assertTrue(returned.financially_settled)
        self.assertTrue(returned.closure_ready)

    def test_pending_failed_or_missing_delivery_is_actionable_and_future_events_are_ignored(self):
        events = (
            self._event(
                1,
                TransactionKind.DISBURSAL,
                principal="1000",
                status=LoanOutboxStatus.POSTED,
            ),
            self._event(
                2,
                TransactionKind.INTEREST_ACCRUAL,
                interest="100",
                status=LoanOutboxStatus.FAILED,
                error="DEA unavailable",
            ),
            self._event(
                3,
                TransactionKind.REPAYMENT,
                principal="100",
                effective_date=date(2026, 4, 1),
                status=LoanOutboxStatus.PENDING,
            ),
        )

        balance = calculate_pawn_loan_balance(
            self.loan,
            events=events,
            collateral_items=(self._collateral(CollateralCustodyState.IN_VAULT),),
            policy_snapshot=self._policy(InterestMethod.SIMPLE, AccountingRecognition.CASH),
            as_of_date=date(2026, 3, 1),
        )

        self.assertEqual(balance.principal_outstanding, Decimal("1000.00"))
        self.assertEqual(balance.interest_outstanding, Decimal("100.00"))
        self.assertFalse(balance.posting_ready)
        self.assertEqual(len(balance.posting_blockers), 1)
        self.assertEqual(balance.posting_blockers[0].status, LoanOutboxStatus.FAILED.value)
        self.assertEqual(balance.posting_blockers[0].message, "DEA unavailable")

    def test_impossible_overpayment_history_fails_closed(self):
        events = (
            self._event(1, TransactionKind.DISBURSAL, principal="1000"),
            self._event(2, TransactionKind.REPAYMENT, principal="1001"),
        )

        with self.assertRaisesMessage(
            PawnLoanBalanceSelectorError,
            "over-settles principal",
        ):
            calculate_pawn_loan_balance(
                self.loan,
                events=events,
                collateral_items=(
                    self._collateral(CollateralCustodyState.IN_VAULT),
                ),
                policy_snapshot=self._policy(
                    InterestMethod.SIMPLE,
                    AccountingRecognition.CASH,
                ),
                as_of_date=date(2026, 3, 1),
            )

    def _event(
        self,
        pk,
        kind,
        *,
        effective_date=date(2026, 2, 1),
        status=LoanOutboxStatus.POSTED,
        error="",
        reversal=None,
        **values,
    ):
        return SimpleNamespace(
            pk=pk,
            event_kind=kind.value,
            effective_date=effective_date,
            payload={"values": values, "reversal": reversal},
            outbox=SimpleNamespace(status=status.value, last_error=error),
        )

    def _policy(self, interest_method, recognition):
        return SimpleNamespace(
            interest_method=interest_method.value,
            accounting_recognition=recognition.value,
            currency_quantum=Decimal("0.01"),
        )

    def _collateral(self, state):
        return SimpleNamespace(custody_state=state.value)
