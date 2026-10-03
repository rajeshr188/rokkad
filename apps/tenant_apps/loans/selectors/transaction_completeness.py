"""Transaction coverage is independent of valuation freshness and calculated debt."""
import hashlib
import json
from dataclasses import dataclass, asdict
from datetime import date
from decimal import Decimal


def transaction_fingerprint(loan, *, events=None):
    rows = ([(e.pk, e.effective_date, e.payload_fingerprint) for e in sorted(events, key=lambda e: e.pk)]
            if events is not None else list(loan.loan_events.order_by("pk").values_list("pk", "effective_date", "payload_fingerprint")))
    material = dict(state=loan.state, events=rows, contract={key: str(getattr(loan, key)) for key in (
        "borrower_id", "loan_number", "loan_date", "principal_amount", "monthly_interest_rate", "tenure_months", "policy_snapshot_id")})
    for key in ("principal_amount", "monthly_interest_rate"):
        material["contract"][key] = format(Decimal(material["contract"][key]).normalize(), "f")
    return hashlib.sha256(json.dumps(material, sort_keys=True, default=str).encode()).hexdigest()


@dataclass(frozen=True)
class TransactionCompleteness:
    status: str
    required: bool
    complete: bool
    through_date: date | None
    review_id: int | None
    message: str

    def evidence(self):
        result = asdict(self)
        result["through_date"] = self.through_date.isoformat() if self.through_date else None
        return result


def transaction_completeness(loan, as_of_date):
    cached = getattr(loan, "_prefetched_objects_cache", {})
    reviews = cached.get("transaction_reviews")
    review = max(reviews, key=lambda r: r.pk, default=None) if reviews is not None else loan.transaction_reviews.order_by("-pk").first()
    events = cached.get("loan_events")
    opening = (any(e.event_kind == "MIGRATION_OPENING" for e in events) if events is not None
               else loan.loan_events.filter(event_kind="MIGRATION_OPENING").exists())
    required = bool(review or (loan.policy_snapshot_id and loan.policy_snapshot.basis == "RECORDED_CONTRACT")
                    or opening)
    if not required:
        return TransactionCompleteness("SYSTEM_RECORDED", False, True, None, None,
            "Recorded through ordinary system actions; no paper-history confirmation is assigned.")
    if review is None:
        return TransactionCompleteness("UNCONFIRMED", True, False, None, None,
            "Confirm this loan's entered transactions against the paper records before borrower reminders.")
    status = "CONFIRMED"
    message = f"Paper transactions confirmed entered through {review.through_date}."
    if not review.confirmed_complete:
        status, message = "INCOMPLETE", "Staff reported missing or unresolved paper activity. Balances are provisional."
    elif review.source_fingerprint != transaction_fingerprint(loan, events=events):
        status, message = "CHANGED", "Loan activity changed after the paper review. Recheck the paper records; balances are provisional."
    else:
        # A settled loan does not acquire missing transactions simply because time passes.
        end = (max((e.effective_date for e in events), default=None) if events is not None
               else loan.loan_events.order_by("-effective_date").values_list("effective_date", flat=True).first())
        required_through = min(as_of_date, end) if loan.state == "CLOSED" and end else as_of_date
        if review.through_date < required_through:
            status, message = "BEHIND", f"Paper transactions confirmed only through {review.through_date}; later activity may be missing. Balances are provisional."
    return TransactionCompleteness(status, True, status == "CONFIRMED", review.through_date, review.pk, message)
