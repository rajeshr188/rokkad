"""Bounded collections on reviewed migration openings; no opening importer."""
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
    precise = any(row.event_kind == "MIGRATION_OPENING" and row.payload["opening"]["review"]["profile"] == "loan-opening-review/5" for row in events)
    if as_of_date < preview.cutover_date or as_of_date == preview.cutover_date and not precise or any(row.effective_date > as_of_date for row in events):
        raise OpeningEvidenceError("Opening servicing must be after cutover and cannot precede recorded activity.")
    if loan.policy_snapshot.interest_method != "SIMPLE" or loan.product_version.repayment_structure != "FLEXIBLE_PARTIAL_PAYMENT":
        raise OpeningEvidenceError("Opening collections require simple interest and a flexible repayment product.")
    balance = get_pawn_loan_balance(loan, as_of_date=as_of_date)
    if reversing:
        if not loan.repayment_schedules.filter(source_event_id=preview.opening_event_id).exists():
            raise OpeningEvidenceError("Opening servicing requires its frozen remaining obligations.")
        return preview, None
    schedule = get_active_repayment_schedule_as_of(loan, as_of_date)
    if schedule is None or schedule.source_event_id != preview.opening_event_id:
        raise OpeningEvidenceError("Opening servicing requires its active remaining obligations.")
    # Collection allocates against immutable capacity, not LC-02's dynamic risk forecast.
    state = calculate_obligation_state_as_of(schedule, as_of_date, adjust_recorded=False)
    if state.integrity_findings or state.remaining.principal != balance.principal_outstanding:
        raise OpeningEvidenceError("Opening principal and remaining obligations do not reconcile.")
    return preview, state


def opening_release_accrual_preview(loan, *, as_of_date):
    collection, _ = opening_release_context(loan, as_of_date=as_of_date)
    return _opening_accrual_from_collection(loan, collection=collection, as_of_date=as_of_date)


def _opening_accrual_from_collection(loan, *, collection, as_of_date):
    """Map validated checkpoint continuation to the retained paired-accrual format."""
    from .pawn_interest import AccrualPeriodPreview
    from .legacy_interest import collection_calendar
    from .opening_evidence import read_opening_evidence
    if collection.additional_interest == 0:
        return None
    number = (loan.interest_accruals.aggregate(last=Max("period_number"))["last"] or 0) + 1
    origin = loan.loan_events.get(pk=collection.opening_event_id)
    review = read_opening_evidence(loan, origin)["review"]
    months = collection_calendar(loan.loan_date, as_of_date)["additional_months"] - review["continuation"]["additional_months"]
    unrounded = collection.monthly_interest_unrounded * months
    start = collection.cutover_date + timedelta(days=1)
    if review["profile"] in ("loan-opening-review/4", "loan-opening-review/5"):
        from .opening_checkpoint import calculation
        unrounded = Decimal(calculation(review, as_of_date)["additional_interest_unrounded"]) - Decimal(calculation(review, collection.cutover_date)["additional_interest_unrounded"])
    if loan.loan_events.filter(event_kind="REPAYMENT").exists():
        from .opening_payment_evidence import collection_history, baseline
        opening = read_opening_evidence(loan, origin)
        state, actions = collection_history(opening, origin, tuple(loan.loan_events.all()), as_of_date)
        accrued_actions = [(e, a) for e, a in actions if a]
        previous_date = accrued_actions[-1][0].effective_date if accrued_actions else collection.cutover_date
        unrounded = state["raw"] - baseline(review, actions, previous_date, item_mapping=opening["item_mapping"])[1]
        start = min(previous_date + timedelta(days=1), as_of_date)
    return AccrualPeriodPreview(
        period_number=number, period_start=start, period_end=as_of_date,
        period_fraction=Decimal("1"), calculation_base=sum(Decimal(item["remaining_principal"] if review["profile"] in ("loan-opening-review/4", "loan-opening-review/5") else item["original_principal"]) for item in review["collateral"]),
        unrounded_interest=unrounded, recognized_interest=collection.additional_interest,
        calculated_interest=collection.additional_interest, is_partial=True,
    )


@transaction.atomic
def _record_opening_servicing_event(loan_id, *, event_kind, effective_date, payload, actor, reversal_of=None):
    """Internal storage for an already validated collection/reversal transaction.

    Ordinary record_loan_event stays closed to migration-origin loans. This helper
    is not a financial command; repayment and release workflows own validation.
    """
    from .event_recording import _locked_loan, _persist_locked_event
    from apps.tenant_apps.loans.domain import TransactionKind
    loan = _locked_loan(loan_id)
    kind = TransactionKind(event_kind).value
    detail = payload.get("opening_collection", {})
    operation = detail.get("operation", "RELEASE_RECEIPT") if kind == "INTEREST_ACCRUAL" else kind
    if kind in {"REPAYMENT", "RENEWAL_SETTLEMENT", "AUCTION_RECOVERY"} or (kind == "INTEREST_ACCRUAL" and operation in {"REPAYMENT", "RENEWAL_SETTLEMENT", "AUCTION_RECOVERY"}):
        from .opening_payment_evidence import PAYMENT_PROFILES, AUCTION_PROFILE, RULE
        profiles = {AUCTION_PROFILE} if operation == "AUCTION_RECOVERY" else PAYMENT_PROFILES
        if detail.get("profile") not in profiles or detail.get("rule") != RULE or detail.get("operation") != operation:
            raise OpeningEvidenceError("Unsupported opening repayment evidence.")
    require_loan_action(loan, actor, "workspace.settings.manage" if kind == "REVERSAL" else
                       "loan.repay" if operation == "REPAYMENT" else "workspace.settings.manage" if operation == "AUCTION_RECOVERY" else "loan.release")
    origin = loan.loan_events.get(event_kind="MIGRATION_OPENING")
    if effective_date <= origin.effective_date:
        from types import SimpleNamespace
        from django.utils import timezone
        from .opening_precision import validate_event_order
        if kind == "REVERSAL":
            previous = loan.loan_events.filter(event_kind="REVERSAL", effective_date=effective_date).order_by("-pk").first()
            paired_time = previous.payload.get("reversal", {}).get("occurred_at") if previous and reversal_of and reversal_of.event_kind == "INTEREST_ACCRUAL" else None
            payload.setdefault("reversal", {}).setdefault("occurred_at", paired_time or timezone.now().isoformat())
        validate_event_order(origin.payload["opening"]["review"], SimpleNamespace(event_kind=kind, effective_date=effective_date, payload=payload))
    if kind == "REVERSAL":
        if (reversal_of is None or reversal_of.loan_id != loan.pk or
                reversal_of.event_kind not in {"INTEREST_ACCRUAL", "RELEASE_RECEIPT", "REPAYMENT", "RENEWAL_SETTLEMENT", "AUCTION_RECOVERY"} or
                payload.get("values") != reversal_of.payload.get("values")):
            raise OpeningEvidenceError("Unsupported opening reversal.")
    elif kind not in {"INTEREST_ACCRUAL", "RELEASE_RECEIPT", "REPAYMENT", "RENEWAL_SETTLEMENT", "AUCTION_RECOVERY"} or payload.get("opening_collection", {}).get("opening_event_id") != origin.pk:
        raise OpeningEvidenceError("Unsupported opening servicing event.")
    return _persist_locked_event(loan, kind=kind, effective_date=effective_date, payload=payload, actor=actor, reversal_of=reversal_of)


def payment_collection_detail(loan, *, as_of_date, request_key, operation, recording=None, occurred_at=None):
    from .opening_payment_evidence import PROFILE, EXPLICIT_PROFILE, AUCTION_PROFILE, RULE
    preview, _ = opening_release_context(loan, as_of_date=as_of_date)
    timed = as_of_date == preview.cutover_date
    profile = EXPLICIT_PROFILE if timed or recording and ("fees_paid" in recording or "item_principal_split" in recording) else PROFILE
    result = {"profile": AUCTION_PROFILE if operation == "AUCTION_RECOVERY" else profile, "rule": RULE, "opening_event_id": preview.opening_event_id,
            "operation": operation, "request_key": request_key,
            "baseline_at_cutover": str(preview.baseline_at_cutover), "baseline_as_of": str(preview.baseline_as_of),
            "recognized_since_cutover": str(preview.baseline_as_of - preview.baseline_at_cutover - preview.additional_interest),
            "calculation": "ANNIVERSARY_BASELINE_LESS_RECORDED"}
    if timed:
        from django.utils import timezone
        result["occurred_at"] = (recording or {}).get("received_at") if recording else occurred_at or timezone.now().isoformat()
    return result


def opening_payment_balance(loan, *, as_of_date):
    """Preview with collection catch-up included, without posting a receipt."""
    from dataclasses import replace
    from apps.tenant_apps.loans.selectors.balances import get_pawn_loan_balance
    preview, state = opening_release_context(loan, as_of_date=as_of_date)
    balance = get_pawn_loan_balance(loan, as_of_date=as_of_date)
    extra = preview.additional_interest
    interest = balance.interest_outstanding + extra
    return replace(balance, interest_outstanding=interest, total_due=balance.total_due + extra,
                   overdue_interest_outstanding=interest if balance.is_overdue else Decimal("0"),
                   current_interest_outstanding=Decimal("0") if balance.is_overdue else interest), state
