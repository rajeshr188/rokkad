from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase

from apps.tenant_apps.loans.domain.future_funding import (
    ALLOWED_FUNDING_LOAN_TRANSITIONS,
    FundingCollateralCandidate,
    FundingCustodyEvent,
    FundingLoanEvent,
    FundingLoanEventKind,
    FundingLoanPolicyError,
    FundingLoanState,
    FundingLoanTerms,
    FundingPledgePolicyError,
    allocate_funding_repayment,
    assess_funding_closure,
    calculate_funding_interest,
    calculate_funding_loan_balance,
    can_transition_funding_loan,
    plan_funding_pledge,
    plan_funding_custody_reversal,
    plan_funding_return,
    plan_funding_reversal,
)
from apps.tenant_apps.loans.domain.vocabulary import (
    CollateralCustodyState,
    PawnLoanState,
)


class FundingCollateralPolicyTests(SimpleTestCase):
    def test_plans_one_funding_pledge_across_multiple_active_pawn_loans(self):
        plan = plan_funding_pledge(
            (
                self._candidate(11, 101, collateral_value="500"),
                self._candidate(12, 102, collateral_value="500"),
                self._candidate(13, 101, collateral_value="500"),
            ),
            terms=self._terms(principal="1000"),
        )

        self.assertEqual(plan.collateral_item_ids, (11, 12, 13))
        self.assertEqual(plan.source_pawn_loan_ids, (101, 102))
        self.assertTrue(
            all(
                transition.to_state
                == CollateralCustodyState.WITH_FUNDING_LENDER
                for transition in plan.custody_transitions
            )
        )

    def test_rejects_duplicate_or_already_pledged_collateral(self):
        duplicate = self._candidate(11, 101)
        with self.assertRaisesRegex(FundingPledgePolicyError, "more than once"):
            plan_funding_pledge((duplicate, duplicate))

        with self.assertRaisesRegex(FundingPledgePolicyError, "pledged again"):
            plan_funding_pledge(
                (self._candidate(11, 101, active_funding_pledge_id=44),)
            )

    def test_rejects_inactive_loan_or_non_vault_custody(self):
        with self.assertRaisesRegex(FundingPledgePolicyError, "active PawnLoan"):
            plan_funding_pledge(
                (self._candidate(11, 101, pawn_loan_state=PawnLoanState.CLOSED),)
            )

    def test_pledge_rejects_missing_value_or_principal_above_ltv(self):
        with self.assertRaisesRegex(FundingPledgePolicyError, "positive valuation"):
            plan_funding_pledge(
                (self._candidate(11, 101),),
                terms=self._terms(principal="100"),
            )

        with self.assertRaisesRegex(FundingPledgePolicyError, "LTV limit"):
            plan_funding_pledge(
                (self._candidate(11, 101, collateral_value="1000"),),
                terms=self._terms(principal="800.01"),
            )

        with self.assertRaisesRegex(FundingPledgePolicyError, "branch vault"):
            plan_funding_pledge(
                (
                    self._candidate(
                        11,
                        101,
                        custody_state=CollateralCustodyState.WITH_CUSTOMER,
                    ),
                )
            )

    def test_return_moves_lender_held_items_back_to_vault(self):
        transitions = plan_funding_return(
            (
                self._candidate(
                    11,
                    101,
                    custody_state=CollateralCustodyState.WITH_FUNDING_LENDER,
                ),
                self._candidate(
                    12,
                    102,
                    custody_state=CollateralCustodyState.WITH_FUNDING_LENDER,
                ),
            ),
            funding_loan_state=FundingLoanState.SETTLEMENT_PENDING,
        )

        self.assertEqual(len(transitions), 2)
        self.assertTrue(
            all(
                transition.to_state == CollateralCustodyState.IN_VAULT
                for transition in transitions
            )
        )

    def test_return_rejects_closed_funding_loan_or_non_lender_custody(self):
        lender_held = self._candidate(
            11,
            101,
            custody_state=CollateralCustodyState.WITH_FUNDING_LENDER,
        )
        with self.assertRaisesRegex(FundingPledgePolicyError, "open FundingLoan"):
            plan_funding_return(
                (lender_held,),
                funding_loan_state=FundingLoanState.CLOSED,
            )

        with self.assertRaisesRegex(FundingPledgePolicyError, "funding lender"):
            plan_funding_return(
                (self._candidate(11, 101),),
                funding_loan_state=FundingLoanState.ACTIVE,
            )

    def test_partial_return_requires_retained_collateral_to_cover_principal(self):
        returning = self._candidate(
            11,
            101,
            custody_state=CollateralCustodyState.WITH_FUNDING_LENDER,
        )
        retained = self._candidate(
            12,
            102,
            custody_state=CollateralCustodyState.WITH_FUNDING_LENDER,
            collateral_value="1000",
        )

        transitions = plan_funding_return(
            (returning,),
            funding_loan_state=FundingLoanState.ACTIVE,
            principal_outstanding="800",
            retained_candidates=(retained,),
        )
        self.assertEqual(len(transitions), 1)

        with self.assertRaisesRegex(FundingPledgePolicyError, "LTV limit"):
            plan_funding_return(
                (returning,),
                funding_loan_state=FundingLoanState.ACTIVE,
                principal_outstanding="800.01",
                retained_candidates=(retained,),
            )

        with self.assertRaisesRegex(FundingPledgePolicyError, "principal is settled"):
            plan_funding_return(
                (returning, retained),
                funding_loan_state=FundingLoanState.SETTLEMENT_PENDING,
                principal_outstanding="1",
            )

    @staticmethod
    def _candidate(
        item_id,
        pawn_loan_id,
        *,
        pawn_loan_state=PawnLoanState.ACTIVE,
        custody_state=CollateralCustodyState.IN_VAULT,
        active_funding_pledge_id=None,
        collateral_value=None,
    ):
        return FundingCollateralCandidate(
            collateral_item_id=item_id,
            pawn_loan_id=pawn_loan_id,
            pawn_loan_state=pawn_loan_state,
            custody_state=custody_state,
            active_funding_pledge_id=active_funding_pledge_id,
            collateral_value=(
                Decimal(collateral_value) if collateral_value is not None else None
            ),
        )

    @staticmethod
    def _terms(*, principal="1000"):
        return FundingLoanTerms(
            principal_amount=Decimal(principal),
            monthly_interest_rate=Decimal("2"),
            activated_on=date(2026, 8, 8),
            maturity_on=date(2027, 8, 8),
        )


class FundingLoanLifecycleAndTermsTests(SimpleTestCase):
    def test_transition_matrix_covers_every_state_and_settlement_reopen(self):
        self.assertEqual(set(ALLOWED_FUNDING_LOAN_TRANSITIONS), set(FundingLoanState))
        self.assertTrue(
            can_transition_funding_loan("ACTIVE", "SETTLEMENT_PENDING")
        )
        self.assertTrue(
            can_transition_funding_loan("SETTLEMENT_PENDING", "ACTIVE")
        )
        self.assertTrue(
            can_transition_funding_loan("SETTLEMENT_PENDING", "CLOSED")
        )
        self.assertFalse(can_transition_funding_loan("ACTIVE", "CLOSED"))

    def test_terms_validate_and_normalize_immutable_economics(self):
        terms = FundingLoanTerms(
            principal_amount=Decimal("1000.129"),
            monthly_interest_rate=Decimal("1.5"),
            activated_on=date(2026, 8, 8),
            maturity_on=date(2027, 8, 8),
        )
        self.assertEqual(terms.principal_amount, Decimal("1000.13"))
        self.assertEqual(terms.maximum_funding_ltv_ratio, Decimal("0.80"))

        with self.assertRaises(FundingLoanPolicyError):
            FundingLoanTerms(
                principal_amount=Decimal("0"),
                monthly_interest_rate=Decimal("1"),
                activated_on=date(2026, 8, 8),
                maturity_on=date(2027, 8, 8),
            )

    def test_terms_drive_deterministic_simple_monthly_interest(self):
        terms = FundingCollateralPolicyTests._terms(principal="1000")
        self.assertEqual(
            calculate_funding_interest(
                terms,
                principal_outstanding=Decimal("750"),
                periods=2,
            ),
            Decimal("30.00"),
        )
        with self.assertRaisesRegex(FundingLoanPolicyError, "positive integer"):
            calculate_funding_interest(
                terms,
                principal_outstanding=Decimal("750"),
                periods=0,
            )
        with self.assertRaises(FundingLoanPolicyError):
            FundingLoanTerms(
                principal_amount=Decimal("100"),
                monthly_interest_rate=Decimal("1"),
                activated_on=date(2026, 8, 8),
                maturity_on=date(2026, 8, 7),
            )


class FundingLoanBalanceAndCorrectionTests(SimpleTestCase):
    def test_folds_activation_accrual_fee_and_repayment_independently(self):
        events = (
            self._event(1, FundingLoanEventKind.ACTIVATION, principal="1000"),
            self._event(2, FundingLoanEventKind.INTEREST_ACCRUAL, interest="100"),
            self._event(3, FundingLoanEventKind.FEE_ASSESSMENT, fee="20"),
        )
        before = calculate_funding_loan_balance(events)
        allocation = allocate_funding_repayment(before, Decimal("370"))
        self.assertEqual(allocation.fees, Decimal("20"))
        self.assertEqual(allocation.interest, Decimal("100"))
        self.assertEqual(allocation.principal, Decimal("250"))

        repayment = self._event(
            4,
            FundingLoanEventKind.REPAYMENT,
            principal=allocation.principal,
            interest=allocation.interest,
            fee=allocation.fees,
        )
        after = calculate_funding_loan_balance(events + (repayment,))
        self.assertEqual(after.principal_outstanding, Decimal("750.00"))
        self.assertEqual(after.interest_outstanding, Decimal("0.00"))
        self.assertEqual(after.fees_outstanding, Decimal("0.00"))
        self.assertEqual(after.total_due, Decimal("750.00"))

    def test_rejects_overpayment_and_invalid_event_history(self):
        balance = calculate_funding_loan_balance(
            (self._event(1, FundingLoanEventKind.ACTIVATION, principal="100"),)
        )
        with self.assertRaisesRegex(FundingLoanPolicyError, "exceeds total due"):
            allocate_funding_repayment(balance, Decimal("100.01"))
        with self.assertRaisesRegex(FundingLoanPolicyError, "exactly one activation"):
            calculate_funding_loan_balance(
                (self._event(1, FundingLoanEventKind.INTEREST_ACCRUAL, interest="1"),)
            )

    def test_reversal_is_exact_and_newest_first(self):
        events = (
            self._event(1, FundingLoanEventKind.ACTIVATION, principal="1000"),
            self._event(2, FundingLoanEventKind.INTEREST_ACCRUAL, interest="50"),
            self._event(3, FundingLoanEventKind.REPAYMENT, interest="50"),
        )
        with self.assertRaisesRegex(FundingLoanPolicyError, "reversed first"):
            plan_funding_reversal(events, original_sequence=2)

        repayment_reversal = plan_funding_reversal(events, original_sequence=3)
        self.assertEqual(repayment_reversal.reversal_of_sequence, 3)
        restored = calculate_funding_loan_balance(events + (repayment_reversal,))
        self.assertEqual(restored.interest_outstanding, Decimal("50.00"))

        bad_reversal = FundingLoanEvent(
            sequence=4,
            kind=FundingLoanEventKind.REVERSAL,
            interest_amount=Decimal("49"),
            reversal_of_sequence=3,
        )
        with self.assertRaisesRegex(FundingLoanPolicyError, "exactly compensate"):
            calculate_funding_loan_balance(events + (bad_reversal,))

    def test_closure_requires_zero_balance_and_returned_collateral(self):
        settled = calculate_funding_loan_balance(
            (
                self._event(1, FundingLoanEventKind.ACTIVATION, principal="100"),
                self._event(2, FundingLoanEventKind.REPAYMENT, principal="100"),
            )
        )
        lender_held = FundingCollateralCandidate(
            collateral_item_id=11,
            pawn_loan_id=101,
            pawn_loan_state=PawnLoanState.ACTIVE,
            custody_state=CollateralCustodyState.WITH_FUNDING_LENDER,
            active_funding_pledge_id=44,
        )
        self.assertFalse(assess_funding_closure(settled, (lender_held,)).ready)

        returned = FundingCollateralCandidate(
            collateral_item_id=11,
            pawn_loan_id=101,
            pawn_loan_state=PawnLoanState.ACTIVE,
            custody_state=CollateralCustodyState.IN_VAULT,
        )
        self.assertTrue(assess_funding_closure(settled, (returned,)).ready)

    def test_custody_reversal_is_exact_and_newest_first_per_item(self):
        pledge = FundingCustodyEvent(
            sequence=1,
            collateral_item_id=11,
            from_state=CollateralCustodyState.IN_VAULT,
            to_state=CollateralCustodyState.WITH_FUNDING_LENDER,
        )
        returned = FundingCustodyEvent(
            sequence=2,
            collateral_item_id=11,
            from_state=CollateralCustodyState.WITH_FUNDING_LENDER,
            to_state=CollateralCustodyState.IN_VAULT,
        )
        other_item = FundingCustodyEvent(
            sequence=3,
            collateral_item_id=12,
            from_state=CollateralCustodyState.IN_VAULT,
            to_state=CollateralCustodyState.WITH_FUNDING_LENDER,
        )

        with self.assertRaisesRegex(FundingPledgePolicyError, "reversed first"):
            plan_funding_custody_reversal(
                (pledge, returned, other_item),
                original_sequence=1,
            )

        reversal = plan_funding_custody_reversal(
            (pledge, returned, other_item),
            original_sequence=2,
        )
        self.assertEqual(reversal.collateral_item_id, 11)
        self.assertEqual(reversal.from_state, CollateralCustodyState.IN_VAULT)
        self.assertEqual(
            reversal.to_state,
            CollateralCustodyState.WITH_FUNDING_LENDER,
        )
        self.assertEqual(reversal.reversal_of_sequence, 2)

    @staticmethod
    def _event(
        sequence,
        kind,
        *,
        principal="0",
        interest="0",
        fee="0",
    ):
        return FundingLoanEvent(
            sequence=sequence,
            kind=kind,
            principal_amount=Decimal(principal),
            interest_amount=Decimal(interest),
            fee_amount=Decimal(fee),
        )
