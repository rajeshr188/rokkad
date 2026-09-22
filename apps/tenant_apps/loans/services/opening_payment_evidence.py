"""Replay the bounded opening collection history, including principal reductions.

Pure evidence validation shared by projections and portable restoration. Writers
remain responsible for authorization, locking and atomic supporting records.
"""
from datetime import date
from decimal import Decimal

from .legacy_interest import collection_calendar, round_rupees
from .opening_evidence import OpeningEvidenceError

PROFILE = "opening-payments/1"
RULE = "reduced-principal-next-anniversary/1"
ZERO = Decimal("0")


def require(condition, message):
    if not condition:
        raise OpeningEvidenceError(message)


def money(value):
    try:
        result = Decimal(str(value))
        require(result.is_finite() and 0 <= result < Decimal("1e16"), "Invalid opening collection amount.")
        return result
    except (ArithmeticError, ValueError, TypeError) as exc:
        raise OpeningEvidenceError("Invalid opening collection amount.") from exc


def baseline(review, actions, on):
    original = date.fromisoformat(review["terms"]["original_date"])
    count = collection_calendar(original, on)["additional_months"]
    monthly = sum(money(i["original_principal"]) * money(i["monthly_rate"]) / 100 for i in review["collateral"])
    raw = monthly * count
    for action, _ in actions:
        if action.event_kind != "REPAYMENT":
            continue
        periods = count - collection_calendar(original, action.effective_date)["additional_months"]
        reduction = sum(money(i["principal_applied"]) * money(i["monthly_interest_rate"]) / 100
                        for i in action.payload["repayment"]["item_principal_allocations"])
        raw -= reduction * max(0, periods)
        monthly -= reduction
    return round_rupees(raw), raw, monthly


def position(review, actions, on):
    settled = bool(actions and actions[-1][0].event_kind == "RELEASE_RECEIPT")
    calculation_date = actions[-1][0].effective_date if settled else on
    rounded, raw, monthly = baseline(review, actions, calculation_date)
    covered = money(review["continuation"]["recognized_interest"])
    posted = sum(money(a.payload["values"]["interest"]) for _, a in actions if a)
    paid = {k: sum(money(e.payload["values"].get(k, "0")) for e, _ in actions)
            for k in ("principal", "interest", "fees", "interest_concession")}
    return dict(baseline=rounded, raw=raw, monthly=monthly, posted=posted,
                additional=ZERO if settled else rounded - covered - posted,
                principal=money(review["balances"]["principal"]) - paid["principal"],
                interest=money(review["balances"]["interest"]) + rounded - covered - paid["interest"] - paid["interest_concession"],
                fees=money(review["balances"]["fees"]) - paid["fees"], settled=settled,
                calculation_date=calculation_date)


def _items(opening, actions):
    items = {opening["item_mapping"][i["id"]]: [money(i["remaining_principal"]), money(i["monthly_rate"])]
             for i in opening["review"]["collateral"]}
    for action, _ in actions:
        if action.event_kind == "REPAYMENT":
            for line in action.payload["repayment"]["item_principal_allocations"]:
                items[line["collateral_item_id"]][0] -= money(line["principal_applied"])
    return items


def _validate_payment(opening, actions, row, state):
    detail, values = row.payload["repayment"], row.payload["values"]
    amount = money(detail["amount_received"])
    require(0 < amount <= state["principal"] + state["interest"] + state["fees"], "Opening payment exceeds the amount due.")
    fees = min(amount, state["fees"])
    interest = min(amount - fees, state["interest"])
    principal = amount - fees - interest
    require(all(money(values.get(k, "0")) == v for k, v in
                (("fees", fees), ("interest", interest), ("principal", principal),
                 ("original_principal", principal), ("capitalized_interest_principal", ZERO), ("interest_concession", ZERO))),
            "Opening payment allocation does not reconcile.")
    require(money(values.get("overdue_interest", "0")) + money(values.get("current_interest", "0")) == interest,
            "Opening payment interest allocation does not reconcile.")
    items = _items(opening, actions)
    expected = []
    remaining = principal
    for pk, (before, rate) in sorted(items.items(), key=lambda pair: (-pair[1][1], pair[0])):
        applied = min(before, remaining)
        if principal:
            expected.append((pk, len(expected) + 1, rate, before, applied, before - applied))
            remaining -= applied
    lines = detail.get("item_principal_allocations", [])
    actual = [(i["collateral_item_id"], i["allocation_order"], money(i["monthly_interest_rate"]),
               money(i["balance_before"]), money(i["principal_applied"]), money(i["balance_after"])) for i in lines]
    require(not remaining and actual == expected, "Opening payment item allocations do not reconcile.")


def collection_history(opening, origin, events, as_of):
    """Validate all events; return the active financial history at the requested date."""
    review = opening["review"]
    actions, snapshot, pending, reversing = [], [], None, None
    seen = set()
    ordered = sorted(events, key=lambda e: (e.effective_date, e.pk))
    for row in ordered:
        if row.pk == origin.pk:
            continue
        require(row.effective_date > origin.effective_date, "Servicing must be strictly after cutover.")
        if reversing:
            receipt_reversal, accrual = reversing
            require(row.event_kind == "REVERSAL" and row.reversal_of_id == accrual.pk and
                    row.effective_date == receipt_reversal.effective_date and row.payload.get("values") == accrual.payload["values"] and
                    row.payload.get("reversal", {}).get("original_event_kind") == "INTEREST_ACCRUAL",
                    "Opening collection and catch-up must be reversed together.")
            reversing = None
        elif row.event_kind == "REVERSAL":
            require(pending is None and bool(actions), "Unsupported opening reversal.")
            target, accrual = actions[-1]
            require(row.reversal_of_id == target.pk and row.payload.get("values") == target.payload["values"] and
                    row.payload.get("reversal", {}).get("original_event_kind") == target.event_kind,
                    "Opening collections must be reversed newest first.")
            actions.pop()
            if accrual:
                reversing = (row, accrual)
        else:
            detail = row.payload.get("opening_collection", {})
            require(detail.get("opening_event_id") == origin.pk and detail.get("profile") in {PROFILE, "opening-release/1"},
                    "Unsupported subsequent servicing evidence for this opening.")
            if row.event_kind == "INTEREST_ACCRUAL":
                require(pending is None, "Opening collection has an unpaired catch-up.")
                pending = row
                continue
            require(row.event_kind in {"REPAYMENT", "RELEASE_RECEIPT"}, "Unsupported opening collection event.")
            kind = "repayment" if row.event_kind == "REPAYMENT" else "release"
            key = row.payload.get(kind, {}).get("request_key")
            require(isinstance(key, str) and key and (kind, key) not in seen, "Duplicate or missing opening collection request.")
            seen.add((kind, key))
            if detail["profile"] == "opening-release/1":
                require(not any(k == "repayment" for k, _ in seen), "Legacy release cannot follow payments.")
            state = position(review, actions, row.effective_date)
            require(not state["settled"], "Opening collection follows an active full release.")
            if detail["profile"] == PROFILE:
                require(detail.get("rule") == RULE and detail.get("operation") == row.event_kind and
                        detail.get("request_key") == key and money(detail.get("baseline_as_of")) == state["baseline"] and
                        money(detail.get("baseline_at_cutover")) == money(review["continuation"]["recognized_interest"]) and
                        money(detail.get("recognized_since_cutover")) == state["posted"],
                        "Opening collection checkpoint does not reconcile.")
            expected = state["additional"]
            require(expected >= 0 and bool(expected) == bool(pending), "Opening catch-up does not reconcile.")
            if pending:
                evidence = pending.payload.get("opening_collection", {})
                require(pending.effective_date == row.effective_date and evidence.get("request_key") == key and
                        money(pending.payload["values"]["interest"]) == expected and
                        money(evidence.get("baseline_at_cutover")) == money(review["continuation"]["recognized_interest"]) and
                        money(evidence.get("baseline_as_of")) == state["baseline"], "Opening catch-up checkpoint does not reconcile.")
                if detail["profile"] == PROFILE:
                    require(evidence.get("profile") == PROFILE and evidence.get("operation") == row.event_kind and
                            evidence.get("rule") == RULE and money(evidence.get("recognized_since_cutover")) == state["posted"],
                            "Opening payment catch-up rule does not reconcile.")
                else:
                    require(evidence.get("rule") == review["terms"]["rule_id"] and not any(e.event_kind == "REPAYMENT" for e, _ in actions),
                            "Legacy release cannot follow payments.")
            if row.event_kind == "REPAYMENT":
                require(detail.get("profile") == PROFILE and detail.get("rule") == RULE, "Unsupported opening payment rule.")
                _validate_payment(opening, actions, row, state)
            else:
                values = row.payload["values"]
                require(row.payload["release"].get("is_full_release") is True and
                        money(values.get("principal", "0")) == state["principal"] and
                        money(values.get("fees", "0")) == state["fees"] and
                        money(values.get("interest", "0")) + money(values.get("interest_concession", "0")) == state["interest"],
                        "Opening release does not settle the remaining debt.")
            actions.append((row, pending))
            pending = None
        if row.effective_date <= as_of:
            snapshot = list(actions)
    require(pending is None and reversing is None, "Opening servicing contains an unpaired catch-up or reversal.")
    return position(review, snapshot, as_of), snapshot
