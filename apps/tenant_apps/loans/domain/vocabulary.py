"""Database-free vocabulary for the PawnLoan MVP.

Only :class:`PawnLoanState` values are candidates for aggregate persistence.
Operational conditions such as overdue or partially paid are derived from
transactions, dates, custody, and accounting delivery state.
"""

from enum import Enum


class StringEnum(str, Enum):
    """Small string enum compatible with model choices in later slices."""

    def __str__(self):
        return self.value


class PawnLoanState(StringEnum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"
    CLOSED = "CLOSED"


class PawnLoanDerivedState(StringEnum):
    PARTIALLY_PAID = "PARTIALLY_PAID"
    OVERDUE = "OVERDUE"
    CLOSURE_READY = "CLOSURE_READY"
    PARTIALLY_RELEASED = "PARTIALLY_RELEASED"
    ACCOUNTING_PENDING = "ACCOUNTING_PENDING"
    ACCOUNTING_FAILED = "ACCOUNTING_FAILED"


class TransactionKind(StringEnum):
    DISBURSAL = "DISBURSAL"
    REPAYMENT = "REPAYMENT"
    INTEREST_ACCRUAL = "INTEREST_ACCRUAL"
    INTEREST_CAPITALIZATION = "INTEREST_CAPITALIZATION"
    RELEASE_RECEIPT = "RELEASE_RECEIPT"
    REVERSAL = "REVERSAL"


class PawnLoanEventKind(StringEnum):
    DRAFT_CREATED = "DRAFT_CREATED"
    DRAFT_UPDATED = "DRAFT_UPDATED"
    LICENSE_TRANSFERRED = "LICENSE_TRANSFERRED"
    APPROVED = "APPROVED"
    RETURNED_TO_DRAFT = "RETURNED_TO_DRAFT"
    CANCELLED = "CANCELLED"
    DISBURSED = "DISBURSED"
    REPAYMENT_RECORDED = "REPAYMENT_RECORDED"
    ACCRUAL_FINALIZED = "ACCRUAL_FINALIZED"
    INTEREST_CAPITALIZED = "INTEREST_CAPITALIZED"
    RELEASE_COMPLETED = "RELEASE_COMPLETED"
    CLOSED = "CLOSED"
    REVERSAL_RECORDED = "REVERSAL_RECORDED"


class CollateralCustodyState(StringEnum):
    IN_VAULT = "IN_VAULT"
    WITH_CUSTOMER = "WITH_CUSTOMER"
    WITH_FUNDING_LENDER = "WITH_FUNDING_LENDER"


class CollateralMetal(StringEnum):
    GOLD = "GOLD"
    SILVER = "SILVER"
    OTHER = "OTHER"


class LoanDocumentKind(StringEnum):
    PAWN_LOAN = "PAWN_LOAN"
    PAWN_LOAN_RELEASE = "PAWN_LOAN_RELEASE"


class PostingState(StringEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    POSTED = "POSTED"
    FAILED = "FAILED"
    REVERSED = "REVERSED"


class LoanOutboxStatus(StringEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    POSTED = "POSTED"
    FAILED = "FAILED"


class ReversalType(StringEnum):
    DISBURSAL = "DISBURSAL"
    REPAYMENT = "REPAYMENT"
    INTEREST_ACCRUAL = "INTEREST_ACCRUAL"
    INTEREST_CAPITALIZATION = "INTEREST_CAPITALIZATION"
    RELEASE = "RELEASE"


STORED_PAWN_LOAN_STATES = frozenset(PawnLoanState)
DERIVED_PAWN_LOAN_STATES = frozenset(PawnLoanDerivedState)

ALLOWED_PAWN_LOAN_TRANSITIONS = {
    PawnLoanState.DRAFT: frozenset(
        {PawnLoanState.APPROVED, PawnLoanState.CANCELLED}
    ),
    PawnLoanState.APPROVED: frozenset(
        {
            PawnLoanState.DRAFT,
            PawnLoanState.ACTIVE,
            PawnLoanState.CANCELLED,
        }
    ),
    PawnLoanState.ACTIVE: frozenset({PawnLoanState.CLOSED}),
    PawnLoanState.CANCELLED: frozenset(),
    PawnLoanState.CLOSED: frozenset(),
}


def can_transition(source, target):
    """Return whether a stored PawnLoan lifecycle transition is allowed."""

    try:
        source_state = PawnLoanState(source)
        target_state = PawnLoanState(target)
    except ValueError:
        return False
    return target_state in ALLOWED_PAWN_LOAN_TRANSITIONS[source_state]
