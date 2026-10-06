"""Policy-rounded continuation for explicitly reviewed version 3 openings."""
from datetime import date, timedelta
from decimal import Decimal
from apps.tenant_apps.loans.domain.monthly_contract import (
    RULE, charge_count, period_dates, anniversary, item_monthly_interest,
)

PROFILE = "loan-opening-review/3"


def calculation(review, on, actions=(), item_mapping=None):
    if review["profile"] in ("loan-opening-review/4", "loan-opening-review/5"):
        from .opening_checkpoint import calculation as checkpoint_calculation
        return checkpoint_calculation(review, on, actions, item_mapping)
    original = date.fromisoformat(review["terms"]["original_date"])
    count = charge_count(original, on)
    quantum = Decimal(review["terms"]["interest_quantum"])
    total = raw = Decimal("0")
    items = review["collateral"]
    for month in range(1, count + 1):
        start, _ = period_dates(original, month + 1)
        for item in items:
            principal = Decimal(item["original_principal"])
            for event, _ in actions:
                if event.event_kind == "REPAYMENT" and event.effective_date < start:
                    if item_mapping is None:
                        raise ValueError("Policy collection requires the retained item mapping.")
                    principal -= sum((Decimal(row["principal_applied"]) for row in
                        event.payload["repayment"]["item_principal_allocations"]
                        if row["collateral_item_id"] == item_mapping[item["id"]]), Decimal("0"))
            rate = Decimal(item["monthly_rate"])
            raw += principal * rate / 100
            total += item_monthly_interest(principal, rate, quantum)
    monthly = sum((Decimal(item["original_principal"]) * Decimal(item["monthly_rate"]) / 100
                   for item in items), Decimal("0"))
    return dict(rule=RULE, additional_months=count, additional_interest=str(total),
                additional_interest_unrounded=str(raw), monthly_interest_unrounded=str(monthly),
                next_increase_on=(anniversary(original, count + 1) + timedelta(days=1)).isoformat())


def reviewed_calculation(review, on):
    if review["profile"] in (PROFILE, "loan-opening-review/4", "loan-opening-review/5"):
        return calculation(review, on)
    from .legacy_interest import aggregate_collection_interest
    monthly = sum(Decimal(item["original_principal"]) * Decimal(item["monthly_rate"]) / 100
                  for item in review["collateral"])
    return aggregate_collection_interest(date.fromisoformat(review["terms"]["original_date"]), on, monthly)
