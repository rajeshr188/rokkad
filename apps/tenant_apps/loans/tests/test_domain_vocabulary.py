from django.test import SimpleTestCase

from apps.tenant_apps.loans.domain import (
    ALLOWED_PAWN_LOAN_TRANSITIONS,
    DERIVED_PAWN_LOAN_STATES,
    FUNDING_LOAN_RUNTIME_SUPPORTED,
    LEGACY_AGGREGATE_NAME_MAP,
    STORED_PAWN_LOAN_STATES,
    CollateralCustodyState,
    LoanDocumentKind,
    PawnLoanDerivedState,
    PawnLoanState,
    PostingState,
    ReversalType,
    TransactionKind,
    can_transition,
)


class PawnLoanVocabularyTests(SimpleTestCase):
    def test_transition_matrix_covers_every_stored_state(self):
        self.assertEqual(
            set(ALLOWED_PAWN_LOAN_TRANSITIONS),
            set(PawnLoanState),
        )

    def test_transition_matrix_matches_mvp_lifecycle(self):
        expected = {
            PawnLoanState.DRAFT: {
                PawnLoanState.APPROVED,
                PawnLoanState.CANCELLED,
            },
            PawnLoanState.APPROVED: {
                PawnLoanState.DRAFT,
                PawnLoanState.ACTIVE,
                PawnLoanState.CANCELLED,
            },
            PawnLoanState.ACTIVE: {PawnLoanState.CLOSED},
            PawnLoanState.CANCELLED: set(),
            PawnLoanState.CLOSED: set(),
        }

        self.assertEqual(
            {state: set(targets) for state, targets in ALLOWED_PAWN_LOAN_TRANSITIONS.items()},
            expected,
        )

    def test_transition_helper_accepts_enum_or_stored_string(self):
        self.assertTrue(can_transition(PawnLoanState.DRAFT, PawnLoanState.APPROVED))
        self.assertTrue(can_transition("APPROVED", "ACTIVE"))
        self.assertFalse(can_transition("ACTIVE", "CANCELLED"))
        self.assertFalse(can_transition("OVERDUE", "CLOSED"))

    def test_derived_states_cannot_be_persisted_as_lifecycle_states(self):
        self.assertEqual(STORED_PAWN_LOAN_STATES, frozenset(PawnLoanState))
        self.assertEqual(DERIVED_PAWN_LOAN_STATES, frozenset(PawnLoanDerivedState))
        self.assertTrue(STORED_PAWN_LOAN_STATES.isdisjoint(DERIVED_PAWN_LOAN_STATES))

    def test_supporting_vocabularies_are_stable_string_enums(self):
        self.assertEqual(TransactionKind.REPAYMENT.value, "REPAYMENT")
        self.assertEqual(CollateralCustodyState.IN_VAULT.value, "IN_VAULT")
        self.assertEqual(LoanDocumentKind.PAWN_LOAN_RELEASE.value, "PAWN_LOAN_RELEASE")
        self.assertEqual(PostingState.FAILED.value, "FAILED")
        self.assertEqual(ReversalType.RELEASE.value, "RELEASE")

    def test_funding_loan_terms_are_compatibility_only(self):
        self.assertFalse(FUNDING_LOAN_RUNTIME_SUPPORTED)
        self.assertEqual(LEGACY_AGGREGATE_NAME_MAP["GivenLoan"], "PawnLoan")
        self.assertEqual(LEGACY_AGGREGATE_NAME_MAP["TakenLoan"], "FundingLoan")
