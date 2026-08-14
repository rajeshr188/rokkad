"""Business policy helpers for Girvi workflows."""

from django.core.exceptions import ValidationError

from apps.tenant_apps.girvi.lifecycle import (
    CANONICAL_ACTIVE_CURRENT,
    CANONICAL_ACTIVE_NPA,
    CANONICAL_ACTIVE_OVERDUE,
    CANONICAL_APPROVED,
    CANONICAL_AUCTION_COMPLETE,
    CANONICAL_CANCELLED,
    CANONICAL_CLOSED,
    CANONICAL_DRAFT,
    CANONICAL_PENDING_APPROVAL,
    CANONICAL_CLOSURE_PENDING,
    CANONICAL_RENEWAL_PENDING,
    CANONICAL_RENEWED,
    CANONICAL_REJECTED,
    CANONICAL_WRITTEN_OFF,
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


REPAYMENT_ALLOWED_GIVEN_LOAN_STATUSES = {
    CANONICAL_ACTIVE_CURRENT,
    CANONICAL_ACTIVE_OVERDUE,
    CANONICAL_ACTIVE_NPA,
    CANONICAL_CLOSURE_PENDING,
    CANONICAL_RENEWAL_PENDING,
}

REPAYMENT_BLOCKED_GIVEN_LOAN_STATUSES = {
    CANONICAL_DRAFT,
    CANONICAL_PENDING_APPROVAL,
    CANONICAL_APPROVED,
    CANONICAL_REJECTED,
    CANONICAL_CANCELLED,
    CANONICAL_CLOSED,
    CANONICAL_RENEWED,
    CANONICAL_WRITTEN_OFF,
    CANONICAL_AUCTION_COMPLETE,
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


def can_create_release(loan, *, checklist=None):
    """Return `(can_release, blockers)` using the centralized release readiness policy."""
    if checklist is None:
        from apps.tenant_apps.girvi.service_modules.custody import (
            build_release_readiness_checklist,
        )

        checklist = build_release_readiness_checklist(loan)
    return bool(checklist.get("can_release")), list(checklist.get("blockers", []))


def assert_can_create_release(loan, *, checklist=None) -> None:
    can_release, blockers = can_create_release(loan, checklist=checklist)
    if can_release:
        return
    blocker_text = "; ".join(blockers) if blockers else "Release checklist is not ready."
    raise ValidationError(blocker_text)


def can_record_repayment(loan, *, loan_kind="given") -> bool:
    """Return whether repayment capture is allowed under the current lifecycle policy."""
    is_released = getattr(loan, "is_released", False) is True

    if loan_kind != "given":
        return not is_released

    state = canonical_status(getattr(loan, "status", None))
    if state in REPAYMENT_ALLOWED_GIVEN_LOAN_STATUSES:
        return True
    if state in REPAYMENT_BLOCKED_GIVEN_LOAN_STATUSES:
        return False
    return not is_released


def assert_can_record_repayment(loan, *, loan_kind="given") -> None:
    if can_record_repayment(loan, loan_kind=loan_kind):
        return
    label = lifecycle_status_label(getattr(loan, "status", None))
    loan_id = getattr(loan, "loan_id", "this loan")
    raise ValidationError(
        f"Cannot record repayment for loan {loan_id} in status {label}."
    )


def can_execute_transition(loan, transition_name, *, user=None, workspace=None):
    """Return `(allowed, message)` for transition action policy checks."""
    from apps.tenant_apps.girvi.flows import build_runtime_loan_flow

    try:
        flow = build_runtime_loan_flow(loan, user, workspace)
    except Exception as exc:
        return False, str(exc)

    transition = getattr(flow, transition_name, None)
    if transition is None:
        return False, f"Transition '{transition_name}' is not available for this loan."

    can_proceed = getattr(transition, "can_proceed", None)
    if callable(can_proceed):
        try:
            return bool(can_proceed()), ""
        except Exception as exc:
            return False, str(exc)

    return True, ""


def assert_loan_transition_allowed(loan, transition_name, *, user=None, workspace=None):
    allowed, message = can_execute_transition(
        loan,
        transition_name,
        user=user,
        workspace=workspace,
    )
    if allowed:
        return
    raise ValidationError(message or "Transition cannot proceed in the current state.")
