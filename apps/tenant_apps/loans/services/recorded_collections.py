"""Anniversary collection for explicitly agreed, recorded simple-monthly contracts."""
from dataclasses import replace
from decimal import Decimal, ROUND_HALF_UP
from dateutil.relativedelta import relativedelta

from apps.tenant_apps.loans.integrations import accrual_payload
from apps.tenant_apps.loans.selectors.balances import get_pawn_loan_balance
from .event_recording import record_loan_event

PROFILE = "recorded-anniversary/1"
ZERO = Decimal("0")


def recording_for(loan):
    if loan.policy_snapshot_id is None or loan.policy_snapshot.basis != "RECORDED_CONTRACT":
        return None
    event = loan.loan_events.filter(event_kind__in=("DISBURSAL", "RENEWAL_OPENING"), reversed_by_event__isnull=True).order_by("-pk").first()
    recording = event.payload.get("recording", {}) if event else {}
    return recording if recording.get("collection_profile") == PROFILE else None


def collection_state(loan, day, *, known_through=None):
    recording = recording_for(loan)
    if recording is None or day < loan.loan_date:
        raise ValueError("Recorded collection requires its agreed contract on or after the original date.")
    if (day - loan.loan_date).days > 36600:
        raise ValueError("This collection history exceeds the supported 100-year calculation bound.")
    from apps.tenant_apps.loans.selectors.balances import calculate_pawn_loan_balance
    from datetime import timedelta
    known_through = min(day, known_through or day)
    balance = get_pawn_loan_balance(loan, as_of_date=known_through)
    events = tuple(loan.loan_events.filter(effective_date__lte=known_through).order_by("effective_date", "pk"))
    items = tuple(loan.collateral_items.all())
    reversed_ids = {e.reversal_of_id for e in events if e.reversal_of_id}
    end = min((e.effective_date for e in events if e.event_kind in ("RELEASE_RECEIPT", "RENEWAL_SETTLEMENT", "AUCTION_RECOVERY")
               and e.pk not in reversed_ids), default=day)
    charges, total, month = [], ZERO, 0
    while True:
        start = loan.loan_date + relativedelta(months=month)
        if start > end:
            break
        if month == 0:
            principal = Decimal(recording["terms"]["principal_amount"])
        else:
            principal = calculate_pawn_loan_balance(loan, events=events, collateral_items=items,
                policy_snapshot=loan.policy_snapshot, as_of_date=min(start - timedelta(days=1), known_through),
                pending_delivery_blocks=False).principal_outstanding
        charge = (principal * loan.monthly_interest_rate / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total += charge
        charges.append(dict(start=start.isoformat(), principal=str(principal), interest=str(charge)))
        month += 1
    advance = Decimal(recording["advance_interest"])
    recognized = balance.interest_accrued
    additional = max(ZERO, total - advance) - recognized
    if additional < 0:
        raise ValueError("Recorded interest exceeds the agreed anniversary calculation; review corrections first.")
    return dict(profile=PROFILE, as_of=day.isoformat(), months=charges, calculated=str(total),
                advance=str(advance), already_recognized=str(recognized), additional=str(additional))


def collection_balance(loan, day):
    balance = get_pawn_loan_balance(loan, as_of_date=day)
    extra = Decimal(collection_state(loan, day)["additional"])
    return replace(balance, interest_outstanding=balance.interest_outstanding + extra,
        current_interest_outstanding=balance.current_interest_outstanding + (ZERO if day > balance.due_date else extra),
        overdue_interest_outstanding=balance.overdue_interest_outstanding + (extra if day > balance.due_date else ZERO),
        total_due=balance.total_due + extra, financially_settled=balance.financially_settled and not extra)


def recognize_collection_interest(loan, day, *, actor, request_key, correction_evidence=None):
    """Caller owns authorization, aggregate lock and atomic collection transaction.

    A collection recognition is a cumulative delta, not a fabricated completed
    calendar period. Its source event freezes each anniversary's base and charge.
    """
    state = collection_state(loan, day)
    extra = Decimal(state["additional"])
    if not extra:
        return None
    payload = accrual_payload(loan, effective_date=day, interest_amount=extra).to_dict()
    payload["recorded_collection"] = dict(state, request_key=request_key)
    if correction_evidence:
        payload["history_correction"] = correction_evidence
    event, _ = record_loan_event(loan.pk, event_kind="INTEREST_ACCRUAL", effective_date=day,
                               payload=payload, actor=actor)
    return event


def scheduled_interest(loan, day, amount):
    from apps.tenant_apps.loans.selectors.obligation_state import get_active_repayment_schedule_as_of, calculate_obligation_state_as_of
    schedule = get_active_repayment_schedule_as_of(loan, day)
    state = calculate_obligation_state_as_of(schedule, day, adjust_recorded=False)
    return min(amount, state.remaining.interest)


def recorded_obligation_state(schedule, day, raw):
    """Read the agreed variable-principal bullet debt without rewriting its schedule.

    The ordinary immutable schedule retains the original maturity and allocation
    capacity. Its original fixed interest projection is not a debt after receipts.
    Future projections may use only transactions known at the requested date.
    """
    loan = schedule.loan
    if not recording_for(loan):
        return raw
    from apps.tenant_apps.loans.selectors.obligation_state import ObligationAmount, UnpaidObligationState
    balance = get_pawn_loan_balance(loan, as_of_date=day)
    horizon = max(day, schedule.maturity_date)
    extra = Decimal(collection_state(loan, horizon, known_through=day)["additional"])
    remaining = ObligationAmount(balance.principal_outstanding, balance.interest_outstanding + extra)
    zero = ObligationAmount(ZERO, ZERO)
    row = UnpaidObligationState(raw.obligations[0].obligation_id, schedule.maturity_date,
                               remaining.principal, remaining.interest)
    return replace(raw, obligations=(row,), remaining=remaining,
        due_now=remaining if schedule.maturity_date <= day else zero,
        overdue=remaining if schedule.maturity_date < day else zero)
