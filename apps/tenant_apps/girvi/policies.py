"""Business policy helpers for Girvi workflows."""

from django.core.exceptions import ValidationError

from apps.tenant_apps.girvi.lifecycle import (
    CANONICAL_APPROVED,
    CANONICAL_DRAFT,
    CANONICAL_PENDING_APPROVAL,
    LEGACY_APPROVED,
    LEGACY_DRAFT,
    canonical_status,
    lifecycle_status_label,
)


EDITABLE_GIVEN_LOAN_HEADER_STATUSES = {
    LEGACY_DRAFT,
    CANONICAL_DRAFT,
    CANONICAL_PENDING_APPROVAL,
    LEGACY_APPROVED,
    CANONICAL_APPROVED,
}


def can_edit_loan_header(loan) -> bool:
    """Return whether core commercial loan header fields may be edited directly."""
    status = canonical_status(getattr(loan, "status", None))
    return status in EDITABLE_GIVEN_LOAN_HEADER_STATUSES


def assert_loan_header_editable(loan) -> None:
    if can_edit_loan_header(loan):
        return

    label = lifecycle_status_label(getattr(loan, "status", None))
    loan_id = getattr(loan, "loan_id", "this loan")
    raise ValidationError(
        f"Loan {loan_id} cannot be edited in status {label}. "
        "Use the appropriate correction, renewal, release, or reversal workflow."
    )
