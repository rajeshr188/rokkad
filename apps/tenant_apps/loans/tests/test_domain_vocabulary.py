from django.test import SimpleTestCase

from apps.tenant_apps.loans.domain import (
    ALLOWED_PAWN_LOAN_TRANSITIONS,
    STORED_PAWN_LOAN_STATES,
    CollateralCustodyState,
    LoanDocumentKind,
    PawnLoanState,
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

    def test_only_lifecycle_states_are_persisted(self):
        self.assertEqual(STORED_PAWN_LOAN_STATES, frozenset(PawnLoanState))

    def test_supporting_vocabularies_are_stable_string_enums(self):
        self.assertEqual(TransactionKind.REPAYMENT.value, "REPAYMENT")
        self.assertEqual(CollateralCustodyState.IN_VAULT.value, "IN_VAULT")
        self.assertEqual(LoanDocumentKind.PAWN_LOAN_RELEASE.value, "PAWN_LOAN_RELEASE")
