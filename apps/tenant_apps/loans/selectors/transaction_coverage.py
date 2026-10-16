"""Usability of the represented position, independent of optional book assurance.

The older transaction_completeness selector retains its published book-review
meaning for immutable reviews and portable histories. Neither result posts money.
"""
from dataclasses import dataclass
from datetime import date

from apps.tenant_apps.loans.models import current_tenant_workspace_id


POSITION_COVERAGE_CONTRACT = "recorded-position-coverage/1"


@dataclass(frozen=True)
class RecordedPositionCoverage:
    status: str
    complete: bool
    message: str
    history_from: date | None
    principal_basis: str | None
    book_review: object

    @property
    def required(self):
        # Retain the existing enhanced notice/capability boundary. This is not a
        # requirement to obtain a book attestation before using this position.
        return self.book_review.required

    @property
    def review_id(self):
        return self.book_review.review_id if self.book_review.complete else None

    def evidence(self):
        return dict(contract=POSITION_COVERAGE_CONTRACT, status=self.status,
            complete=self.complete, capture_basis="RECORDED_POSITION",
            history_from=self.history_from.isoformat() if self.history_from else None,
            principal_basis=self.principal_basis, message=self.message,
            book_review=self.book_review.evidence())


def recorded_position_coverage(loan, as_of_date, *, financial_inputs=None, exposure=None,
                               book_review=None, servicing_position=None):
    """Accept supported opening/origination plus entered activity, not unseen cash.

    Missing/aged/changed book assurance is informational. An explicit unresolved
    activity report remains a blocker until superseded by a supported new review.
    Prepared reads remain scoped to this loan, date and Workspace.
    """
    if (current_tenant_workspace_id() is None or loan.workspace_id != current_tenant_workspace_id()
            or type(as_of_date) is not date):
        raise ValueError("Transaction coverage requires the loan's Workspace and a reporting date.")
    if financial_inputs is not None:
        financial_inputs.require(loan.pk, as_of_date)
    if exposure is not None and (exposure.loan_id != loan.pk or exposure.as_of_date != as_of_date):
        raise ValueError("Prepared exposure must match the loan and reporting date.")
    if servicing_position is not None and (
            servicing_position.balance.loan_id != loan.pk or servicing_position.balance.as_of_date != as_of_date):
        raise ValueError("Prepared servicing position must match the loan and reporting date.")
    from .transaction_completeness import transaction_completeness
    book = book_review if book_review is not None else transaction_completeness(loan, as_of_date)
    history_from = principal_basis = None
    try:
        if financial_inputs is not None:
            from .exposure import get_pawn_loan_exposure, require_consistent_exposure
            inputs = financial_inputs
            position = exposure or get_pawn_loan_exposure(loan.pk, as_of_date=as_of_date, financial_inputs=inputs)
            require_consistent_exposure(position)
            contract, balance = inputs.position.contract, inputs.position.collection_balance
            principal_basis = inputs.principal_history_basis
        else:
            # A supported collection position need not support every future
            # forecast. Keep the capability required by this read narrow.
            from .servicing_contract import get_servicing_position
            position = servicing_position or get_servicing_position(loan, as_of_date=as_of_date, operation="NOTICE")
            contract, balance = position.contract, position.balance
            principal_basis = ("VERIFIED_TERMINAL_POSITION" if contract.profile in
                {"loan-terminal-position/1", "loan-closed-position/1"} else
                "OPENING_CHECKPOINT" if contract.origin_kind == "MIGRATION_OPENING" else "ORIGINAL_PAYOUT")
        if loan.state not in {"ACTIVE", "CLOSED"} or contract.origin_event_id is None:
            raise ValueError("An accepted financial origin or opening position is required.")
        amounts = (balance.principal_outstanding, balance.interest_outstanding, balance.fees_outstanding)
        if (any(not amount.is_finite() or amount < 0 for amount in (*amounts, balance.total_due))
                or sum(amounts) != balance.total_due):
            raise ValueError("Recorded position amounts are inconsistent.")
        history_from = contract.financial_history_from
    except ValueError as exc:
        return RecordedPositionCoverage("UNAVAILABLE", False, str(exc), history_from, principal_basis, book)
    if book.status == "INCOMPLETE":
        return RecordedPositionCoverage("INCOMPLETE", False,
            "Staff reported missing or unresolved activity. The entered position remains provisional.",
            history_from, principal_basis, book)
    message = "Supported agreement and recorded transactions establish the represented position. This is not a check of unseen off-system transactions."
    if principal_basis in {"OPENING_CHECKPOINT", "VERIFIED_TERMINAL_POSITION"}:
        message = "Accepted position and subsequent recorded activity establish the represented position; earlier cash history remains unavailable."
    return RecordedPositionCoverage("RECORDED_POSITION", True, message,
        history_from, principal_basis, book)
