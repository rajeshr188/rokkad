"""Bounded full release of reviewed migration openings; no opening importer."""
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Max

from .action_access import require_loan_action
from .opening_continuation import preview_opening_collection
from .opening_evidence import OpeningEvidenceError


def opening_release_context(loan, *, as_of_date, reversing=False):
    from apps.tenant_apps.loans.selectors.balances import get_pawn_loan_balance
    from apps.tenant_apps.loans.selectors.obligation_state import (
        calculate_obligation_state_as_of, get_active_repayment_schedule_as_of,
    )
    events = tuple(loan.loan_events.all())
    preview = preview_opening_collection(loan, events=events, as_of_date=as_of_date)
    if as_of_date <= preview.cutover_date or any(row.effective_date > as_of_date for row in events):
        raise OpeningEvidenceError("Opening servicing must be after cutover and cannot precede recorded activity.")
    if loan.policy_snapshot.interest_method != "SIMPLE" or loan.product_version.repayment_structure != "FLEXIBLE_PARTIAL_PAYMENT":
        raise OpeningEvidenceError("Opening full release requires simple interest and a flexible repayment product.")
    balance = get_pawn_loan_balance(loan, as_of_date=as_of_date)
    if reversing:
        if not loan.repayment_schedules.filter(source_event_id=preview.opening_event_id).exists():
            raise OpeningEvidenceError("Opening servicing requires its frozen remaining obligations.")
        return preview, None
    schedule = get_active_repayment_schedule_as_of(loan, as_of_date)
    if schedule is None or schedule.source_event_id != preview.opening_event_id:
        raise OpeningEvidenceError("Opening servicing requires its active remaining obligations.")
    state = calculate_obligation_state_as_of(schedule, as_of_date)
    if state.integrity_findings or state.remaining.principal != balance.principal_outstanding:
        raise OpeningEvidenceError("Opening principal and remaining obligations do not reconcile.")
    return preview, state


def opening_release_accrual_preview(loan, *, as_of_date):
    from .pawn_interest import AccrualPeriodPreview
    from .legacy_interest import collection_calendar
    from .opening_evidence import read_opening_evidence
    collection, _ = opening_release_context(loan, as_of_date=as_of_date)
    if collection.additional_interest == 0:
        return None
    number = (loan.interest_accruals.aggregate(last=Max("period_number"))["last"] or 0) + 1
    origin = loan.loan_events.get(pk=collection.opening_event_id)
    review = read_opening_evidence(loan, origin)["review"]
    months = collection_calendar(loan.loan_date, as_of_date)["additional_months"] - review["continuation"]["additional_months"]
    return AccrualPeriodPreview(
        period_number=number, period_start=collection.cutover_date + timedelta(days=1), period_end=as_of_date,
        period_fraction=Decimal("1"), calculation_base=sum(Decimal(item["original_principal"]) for item in review["collateral"]),
        unrounded_interest=collection.monthly_interest_unrounded * months, recognized_interest=collection.additional_interest,
        calculated_interest=collection.additional_interest, is_partial=True,
    )


@transaction.atomic
def _record_opening_servicing_event(loan_id, *, event_kind, effective_date, payload, actor, reversal_of=None):
    """Internal storage for the already validated release/reversal transaction.

    Ordinary record_loan_event stays closed to migration-origin loans. This helper
    is not a financial command and must only be called by full release/reversal.
    """
    from .event_recording import _locked_loan, _persist_locked_event
    from apps.tenant_apps.loans.domain import TransactionKind
    loan = _locked_loan(loan_id)
    kind = TransactionKind(event_kind).value
    require_loan_action(loan, actor, "workspace.settings.manage" if kind == "REVERSAL" else "loan.release")
    origin = loan.loan_events.get(event_kind="MIGRATION_OPENING")
    if effective_date <= origin.effective_date:
        raise OpeningEvidenceError("Opening servicing must be strictly after cutover.")
    if kind == "REVERSAL":
        if (reversal_of is None or reversal_of.loan_id != loan.pk or
                reversal_of.event_kind not in {"INTEREST_ACCRUAL", "RELEASE_RECEIPT"} or
                payload.get("values") != reversal_of.payload.get("values")):
            raise OpeningEvidenceError("Unsupported opening reversal.")
    elif kind not in {"INTEREST_ACCRUAL", "RELEASE_RECEIPT"} or payload.get("opening_collection", {}).get("opening_event_id") != origin.pk:
        raise OpeningEvidenceError("Unsupported opening servicing event.")
    return _persist_locked_event(loan, kind=kind, effective_date=effective_date, payload=payload, actor=actor, reversal_of=reversal_of)
