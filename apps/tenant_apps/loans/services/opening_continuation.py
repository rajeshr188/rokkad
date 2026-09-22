"""Reviewed opening collection continuation, without financial posting."""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from dateutil.relativedelta import relativedelta

from .legacy_interest import AGGREGATE_RULE, aggregate_collection_interest
from .opening_evidence import OpeningEvidenceError, read_opening_evidence
from .opening_validation import COLLECTION_PROFILE


def opening_interest_breakdown(review, *, as_of_date, loan=None):
    """Explain a validated active opening's collection rule without posting."""
    original = date.fromisoformat(review["terms"]["original_date"])
    cutover = date.fromisoformat(review["cutover"]["date"])
    if review["profile"] != COLLECTION_PROFILE or as_of_date < cutover:
        raise OpeningEvidenceError("Interest breakdown requires a collection opening on or after cutover.")
    monthly = sum(Decimal(item["original_principal"]) * Decimal(item["monthly_rate"]) / 100
                  for item in review["collateral"])
    calculated = aggregate_collection_interest(original, as_of_date, monthly)
    elapsed = relativedelta(as_of_date, original)
    baseline = Decimal(review["continuation"]["recognized_interest"])
    unpaid = Decimal(review["balances"]["interest"])
    additional = Decimal(calculated["additional_interest"]) - baseline
    result = {
        "elapsed_months": elapsed.years * 12 + elapsed.months,
        "elapsed_days": elapsed.days,
        "charge_months": calculated["additional_months"],
        "cutover_months": review["continuation"]["additional_months"],
        "new_months": calculated["additional_months"] - review["continuation"]["additional_months"],
        "monthly_interest": monthly,
        "cumulative_interest": Decimal(calculated["additional_interest"]),
        "opening_unpaid_interest": unpaid,
        "additional_interest": additional,
        "total_interest": unpaid + additional,
        "next_increase_on": date.fromisoformat(calculated["next_increase_on"]),
    }
    if loan is not None and loan.loan_events.filter(event_kind="REPAYMENT").exists():
        from .opening_payment_evidence import collection_history
        events = tuple(loan.loan_events.all())
        origin = next(row for row in events if row.event_kind == "MIGRATION_OPENING")
        state, _ = collection_history(read_opening_evidence(loan, origin), origin, events, as_of_date)
        result.update(has_payments=True, monthly_interest=state["monthly"], cumulative_interest=state["baseline"],
                      additional_interest=state["additional"], total_interest=state["interest"])
    return result


@dataclass(frozen=True)
class OpeningCollectionPreview:
    opening_event_id: int
    cutover_date: date
    as_of_date: date
    monthly_interest_unrounded: Decimal
    baseline_at_cutover: Decimal
    baseline_as_of: Decimal
    additional_interest: Decimal
    next_increase_on: date
    rule: str = AGGREGATE_RULE


def preview_opening_collection(loan, *, events, as_of_date):
    """Continue the reviewed cumulative baseline without recharging cutover debt.

    No receipts or concessions are inferred from the difference between the
    recognized baseline and opening unpaid interest. Dedicated collection catch-up,
    repayment, full settlement and their coupled reversals are supported.
    """
    events = tuple(events)
    origins = [row for row in events if row.event_kind == "MIGRATION_OPENING"]
    if len(origins) != 1:
        raise OpeningEvidenceError("Opening collection preview requires one migration opening.")
    event = origins[0]
    opening = read_opening_evidence(loan, event)
    review = opening["review"]
    if review["profile"] != COLLECTION_PROFILE:
        raise OpeningEvidenceError("This opening does not have the supported collection continuation checkpoint.")
    if type(as_of_date) is not date or as_of_date < event.effective_date:
        raise OpeningEvidenceError("Collection history before the migration cutover is unavailable.")
    if any(row.event_kind == "REPAYMENT" for row in events):
        from .opening_payment_evidence import collection_history, RULE
        from .legacy_interest import collection_calendar
        state, _ = collection_history(opening, event, events, as_of_date)
        return OpeningCollectionPreview(
            opening_event_id=event.pk, cutover_date=event.effective_date, as_of_date=as_of_date,
            monthly_interest_unrounded=state["monthly"], baseline_at_cutover=Decimal(review["continuation"]["recognized_interest"]),
            baseline_as_of=state["baseline"], additional_interest=state["additional"],
            next_increase_on=date.fromisoformat(collection_calendar(loan.loan_date, state["calculation_date"])["next_increase_on"]), rule=RULE,
        )
    monthly = sum(Decimal(item["original_principal"]) * Decimal(item["monthly_rate"]) / 100
                  for item in review["collateral"])
    release_date = _settled_release_date(events, event, as_of_date, loan.loan_date, monthly, review)
    try:
        calculated = aggregate_collection_interest(loan.loan_date, release_date or as_of_date, monthly)
    except ValueError as exc:
        raise OpeningEvidenceError(str(exc)) from exc
    baseline = Decimal(calculated["additional_interest"])
    covered = Decimal(review["continuation"]["recognized_interest"])
    return OpeningCollectionPreview(
        opening_event_id=event.pk, cutover_date=event.effective_date, as_of_date=as_of_date,
        monthly_interest_unrounded=monthly, baseline_at_cutover=covered,
        baseline_as_of=baseline, additional_interest=Decimal("0") if release_date else baseline - covered,
        next_increase_on=date.fromisoformat(calculated["next_increase_on"]),
    )


def _settled_release_date(events, origin, as_of, original_date, monthly, review):
    by_id = {row.pk: row for row in events}
    releases, accruals, reversed_dates = {}, {}, {}
    for row in sorted(events, key=lambda value: (value.effective_date, value.pk)):
        if row.pk == origin.pk:
            continue
        if row.effective_date <= origin.effective_date:
            raise OpeningEvidenceError("Servicing must be strictly after cutover.")
        if row.event_kind == "REVERSAL":
            target = by_id.get(getattr(row, "reversal_of_id", None))
            detail = row.payload.get("reversal") or {}
            if (target is None or target.event_kind not in {"RELEASE_RECEIPT", "INTEREST_ACCRUAL"} or
                    (target.effective_date, target.pk) >= (row.effective_date, row.pk) or target.pk in reversed_dates or
                    detail.get("original_event_kind") != target.event_kind or
                    row.payload.get("values") != target.payload.get("values")):
                raise OpeningEvidenceError("Unsupported opening servicing reversal evidence.")
            reversed_dates[target.pk] = row.effective_date
            continue
        detail = row.payload.get("opening_collection") or {}
        if detail.get("opening_event_id") != origin.pk or detail.get("profile") != "opening-release/1":
            raise OpeningEvidenceError("Unsupported subsequent servicing evidence for this opening.")
        request_key = (row.payload.get("release") or {}).get("request_key") if row.event_kind == "RELEASE_RECEIPT" else detail.get("request_key")
        if not isinstance(request_key, str) or not request_key:
            raise OpeningEvidenceError("Opening servicing requires its release request identity.")
        if row.event_kind == "RELEASE_RECEIPT" and (row.payload.get("release") or {}).get("is_full_release") is True:
            if request_key in releases:
                raise OpeningEvidenceError("Duplicate opening release request.")
            releases[request_key] = row
        elif row.event_kind == "INTEREST_ACCRUAL":
            expected = Decimal(aggregate_collection_interest(original_date, row.effective_date, monthly)["additional_interest"]) - Decimal(review["continuation"]["recognized_interest"])
            if (request_key in accruals or expected <= 0 or row.payload.get("values", {}).get("interest") != str(expected) or
                    detail.get("baseline_at_cutover") != review["continuation"]["recognized_interest"] or
                    detail.get("rule") != review["terms"]["rule_id"] or
                    detail.get("baseline_as_of") != str(expected + Decimal(review["continuation"]["recognized_interest"])) or
                    not (row.payload.get("accrual") or {}).get("release_catch_up")):
                raise OpeningEvidenceError("Opening release interest does not reconcile to its cumulative checkpoint.")
            accruals[request_key] = row
        else:
            raise OpeningEvidenceError("Unsupported subsequent servicing for this opening.")
    active_releases = []
    for key, release in releases.items():
        expected = Decimal(aggregate_collection_interest(original_date, release.effective_date, monthly)["additional_interest"]) - Decimal(review["continuation"]["recognized_interest"])
        values = release.payload.get("values") or {}
        try:
            paid = {k: Decimal(str(values.get(k, "0"))) for k in ("principal", "interest", "fees", "interest_concession")}
            valid = (all(v.is_finite() and v >= 0 for v in paid.values()) and
                paid["principal"] == Decimal(review["balances"]["principal"]) and paid["fees"] == Decimal(review["balances"]["fees"]) and
                paid["interest"] + paid["interest_concession"] == Decimal(review["balances"]["interest"]) + expected)
        except (ArithmeticError, ValueError, TypeError):
            valid = False
        if not valid:
            raise OpeningEvidenceError("Opening release does not settle its reviewed principal, fees and collection interest.")
        accrual = accruals.pop(key, None)
        if bool(expected) != bool(accrual) or (accrual and (accrual.effective_date != release.effective_date or
                accrual.pk >= release.pk or reversed_dates.get(accrual.pk) != reversed_dates.get(release.pk))):
            raise OpeningEvidenceError("Opening release and catch-up must be recorded and reversed together.")
        if release.effective_date <= as_of and (release.pk not in reversed_dates or reversed_dates[release.pk] > as_of):
            active_releases.append(release)
    if accruals or len(active_releases) > 1:
        raise OpeningEvidenceError("Opening servicing contains an unpaired catch-up or overlapping releases.")
    return active_releases[0].effective_date if active_releases else None
