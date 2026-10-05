"""Explicit shared-monthly cutover facts; no reconstruction of earlier activity."""
from datetime import date, timedelta
from decimal import Decimal

from apps.tenant_apps.loans.domain.monthly_contract import (
    RULE, charge_count, period_dates, anniversary, item_monthly_interest,
)

PROFILE = "loan-opening-review/4"


def validate_checkpoint(check, doc, items, amounts, original, cutoff, result):
    terms = doc["terms"]
    required = dict(rule_id=RULE, period_rule="ORIGINAL_ANNIVERSARY", interest_basis="OUTSTANDING_AT_PERIOD_START",
        partial_rule="FULL_MONTH", rounding_scope="PER_ITEM", rounding_mode="HALF_UP")
    if not isinstance(terms, dict) or any(terms.get(k) != v for k, v in required.items()):
        check.issue("COLLECTION_RULE", "terms", "Use the shared monthly period-start basis and captured policy rounding.")
    carry = check.object(doc["continuation"], "covered_through additional_months period_number period_start period_end bases expected_period_interest recognized_interest recognized_unpaid_interest current_period_recognized_interest current_period_unpaid_interest advance_coverage next_increase_on evidence_reference", "continuation")
    if not carry:
        return
    check.text(carry["evidence_reference"], "continuation.evidence_reference")
    through = check.day(carry["covered_through"], "continuation.covered_through")
    number = check.integer(carry["period_number"], "continuation.period_number", 1, 1200)
    count = check.integer(carry["additional_months"], "continuation.additional_months", 0, 1199)
    start = check.day(carry["period_start"], "continuation.period_start")
    end = check.day(carry["period_end"], "continuation.period_end")
    next_day = check.day(carry["next_increase_on"], "continuation.next_increase_on")
    if original and cutoff:
        try:
            expected_number = charge_count(original, cutoff) + 1
            expected_start, expected_end = period_dates(original, expected_number)
            if (through, number, count, start, end, next_day) != (
                    cutoff, expected_number, expected_number - 1, expected_start, expected_end, expected_end + timedelta(days=1)):
                check.issue("PERIOD_CUTOVER", "continuation", "Preserve the actual cutover and original inclusive monthly boundaries.")
        except (ValueError, OverflowError):
            check.issue("COLLECTION_RANGE", "continuation", "Checkpoint dates exceed the supported monthly calendar.")
    expected = check.amount(carry["expected_period_interest"], "continuation.expected_period_interest")
    recognized = check.amount(carry["recognized_interest"], "continuation.recognized_interest")
    unpaid = check.amount(carry["recognized_unpaid_interest"], "continuation.recognized_unpaid_interest")
    current = check.amount(carry["current_period_recognized_interest"], "continuation.current_period_recognized_interest")
    current_unpaid = check.amount(carry["current_period_unpaid_interest"], "continuation.current_period_unpaid_interest")
    bases = {}
    for n, raw in enumerate(check.rows(carry["bases"], "continuation.bases", 20)):
        path = f"continuation.bases[{n}]"
        row = check.object(raw, "item_id principal_base", path)
        if not row:
            continue
        key = check.text(row["item_id"], path + ".item_id")
        base = check.amount(row["principal_base"], path + ".principal_base")
        if key not in items or key in bases:
            check.issue("BASIS_ITEM", path, "Supply each retained item's period basis exactly once.")
            continue
        item = items[key]
        if base is not None and item["remaining"] is not None and item["original"] is not None:
            if not item["remaining"] <= base <= item["original"] or (number == 1 and base != item["original"]):
                check.issue("PERIOD_BASIS", path, "Current-period basis must preserve the original first month and evidenced reductions.")
        bases[key] = base
    if set(bases) != set(items):
        check.issue("BASIS_ITEM_SET", "continuation.bases", "Supply the complete retained item basis set.")
    quantum = Decimal(terms["interest_quantum"]) if isinstance(terms, dict) and terms.get("interest_quantum") in ("1", "0.01") else None
    if quantum and set(bases) == set(items) and all(bases[k] is not None and items[k]["rate"] is not None for k in bases):
        full = sum((item_monthly_interest(bases[k], items[k]["rate"], quantum) for k in bases), Decimal("0"))
        if expected is not None and expected != full:
            check.issue("PERIOD_INTEREST_MISMATCH", "continuation.expected_period_interest", "The period charge must reconcile to actual bases, rates and rounding.")
    advances = {}
    rows = carry["advance_coverage"]
    if type(rows) is not list or len(rows) > 1200:
        check.issue("ROWS_REQUIRED", "continuation.advance_coverage", "Supply explicit current/future advance coverage, or an empty list when none exists.")
        rows = []
    for n, raw in enumerate(rows):
        path = f"continuation.advance_coverage[{n}]"
        row = check.object(raw, "period_number interest evidence_reference", path)
        if not row:
            continue
        period = check.integer(row["period_number"], path + ".period_number", 1, 1200)
        amount = check.amount(row["interest"], path + ".interest", True)
        check.text(row["evidence_reference"], path + ".evidence_reference")
        if period is not None:
            if period in advances or number is None or period < number:
                check.issue("CARRY_OVER_COVERED", path, "Advance coverage must identify distinct current/future periods.")
            elif amount is not None and quantum and all(i["remaining"] is not None and i["rate"] is not None for i in items.values()):
                maximum = expected if period == number else sum((item_monthly_interest(i["remaining"], i["rate"], quantum) for i in items.values()), Decimal("0"))
                if maximum is not None and amount > maximum:
                    check.issue("CARRY_OVER_COVERED", path, "Advance exceeds the evidenced monthly charge; reconcile that agreement explicitly.")
            advances[period] = amount
    if all(v is not None for v in (expected, current, recognized, unpaid, current_unpaid)):
        advance = advances.get(number, Decimal("0"))
        if advance is not None and current != expected - advance:
            check.issue("COLLECTION_RECOGNITION", "continuation.current_period_recognized_interest", "The full eligible current charge, less separate advance coverage, must already be recognized at cutover.")
        if (unpaid != amounts.get("interest") or not 0 <= current_unpaid <= current <= recognized
                or not current_unpaid <= unpaid <= recognized or unpaid - current_unpaid > recognized - current):
            check.issue("COLLECTION_BALANCE", "continuation", "Current and earlier recognized/unpaid amounts must reconcile separately to opening interest.")
    result["reconciliation"]["additional_full_period_interest"] = "0"


def calculation(review, on, actions=(), item_mapping=None):
    original = date.fromisoformat(review["terms"]["original_date"])
    cutoff = date.fromisoformat(review["cutover"]["date"])
    if on < cutoff:
        raise ValueError("Financial history before the opening checkpoint is unavailable.")
    carry = review["continuation"]
    quantum = Decimal(review["terms"]["interest_quantum"])
    total = raw = Decimal(carry["recognized_interest"])
    count = charge_count(original, on)
    advances = {row["period_number"]: Decimal(row["interest"]) for row in carry["advance_coverage"]}
    for period in range(carry["period_number"] + 1, count + 2):
        start, _ = period_dates(original, period)
        charge = unrounded = Decimal("0")
        for item in review["collateral"]:
            principal = Decimal(item["remaining_principal"])
            for event, _ in actions:
                if event.event_kind == "REPAYMENT" and event.effective_date < start:
                    if item_mapping is None:
                        raise ValueError("Checkpoint continuation needs its retained item mapping.")
                    principal -= sum((Decimal(row["principal_applied"]) for row in event.payload["repayment"]["item_principal_allocations"]
                        if row["collateral_item_id"] == item_mapping[item["id"]]), Decimal("0"))
            if principal < 0:
                raise ValueError("Checkpoint principal allocations exceed the retained balance.")
            rate = Decimal(item["monthly_rate"])
            charge += item_monthly_interest(principal, rate, quantum)
            unrounded += principal * rate / 100
        advance = advances.get(period, Decimal("0"))
        if advance > charge:
            raise ValueError("Recorded future advance exceeds the reduced period charge. Review advance coverage before this action.")
        total += charge - advance
        # An actual rounded advance cannot create negative raw accrual evidence.
        raw += max(Decimal("0"), unrounded - advance)
    monthly = sum((Decimal(i["remaining_principal"]) * Decimal(i["monthly_rate"]) / 100 for i in review["collateral"]), Decimal("0"))
    return dict(rule=RULE, additional_months=count, additional_interest=str(total),
        additional_interest_unrounded=str(raw), monthly_interest_unrounded=str(monthly),
        next_increase_on=(anniversary(original, count + 1) + timedelta(days=1)).isoformat())


def validate_future_payment(review, *, on, allocations):
    """Do not invent a refund/reallocation of an over-covered future period."""
    if review["profile"] != PROFILE or not allocations:
        return
    original = date.fromisoformat(review["terms"]["original_date"])
    quantum = Decimal(review["terms"]["interest_quantum"])
    charge_after = sum((item_monthly_interest(Decimal(row["balance_after"]), Decimal(row["monthly_interest_rate"]), quantum)
        for row in allocations), Decimal("0"))
    for row in review["continuation"]["advance_coverage"]:
        if period_dates(original, row["period_number"])[0] > on and Decimal(row["interest"]) > charge_after:
            raise ValueError("Recorded future advance exceeds the reduced period charge. Review advance coverage before this action.")
