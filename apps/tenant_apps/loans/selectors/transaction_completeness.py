"""Transaction coverage is independent of valuation freshness and calculated debt."""
import hashlib
import json
from dataclasses import dataclass, asdict
from datetime import date
from decimal import Decimal


def transaction_fingerprint(loan, *, events=None, state=None):
    rows = ([(e.pk, e.effective_date, e.payload_fingerprint) for e in sorted(events, key=lambda e: e.pk)]
            if events is not None else list(loan.loan_events.order_by("pk").values_list("pk", "effective_date", "payload_fingerprint")))
    material = dict(state=loan.state if state is None else state, events=rows, contract={key: str(getattr(loan, key)) for key in (
        "borrower_id", "loan_number", "loan_date", "principal_amount", "monthly_interest_rate", "tenure_months", "policy_snapshot_id")})
    for key in ("principal_amount", "monthly_interest_rate"):
        material["contract"][key] = format(Decimal(material["contract"][key]).normalize(), "f")
    return hashlib.sha256(json.dumps(material, sort_keys=True, default=str).encode()).hexdigest()


def capture_contract_fingerprint(loan, *, items=None):
    """Extra agreement/collateral bindings for a newly selected capture transition.

    Keep earlier coverage fingerprint meanings intact. Current appraisals, custody,
    storage and product availability are not changes to this agreement.
    """
    material = dict(bindings={key: getattr(loan, key) for key in
        ("product_version_id", "license_id", "license_revision_id", "series_id")},
        items=[{key: str(getattr(item, key)) for key in ("pk", "allocated_principal", "monthly_interest_rate",
            "description", "metal", "quantity", "gross_weight", "net_weight", "purity_percentage")}
            for item in (loan.collateral_items.order_by("pk") if items is None else sorted(items, key=lambda row:row.pk))])
    for item in material["items"]:
        for key in ("allocated_principal", "monthly_interest_rate", "gross_weight", "net_weight", "purity_percentage"):
            if item[key] != "None":
                item[key] = format(Decimal(item[key]).normalize(), "f")
    return hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()


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
    completed_paper = (any(e.payload.get("repayment", {}).get("recording") or e.payload.get("release", {}).get("paper_closure")
                           for e in events) if events is not None else
                       loan.loan_events.filter(payload__repayment__recording__isnull=False).exists()
                       or loan.loan_events.filter(payload__release__paper_closure__isnull=False).exists())
    required = bool(review or (loan.policy_snapshot_id and loan.policy_snapshot.basis == "RECORDED_CONTRACT")
                    or opening or completed_paper)
    if not required:
        return TransactionCompleteness("SYSTEM_RECORDED", False, True, None, None,
            "Recorded through ordinary system actions; no paper-history confirmation is assigned.")
    if review is None:
        return TransactionCompleteness("UNCONFIRMED", True, False, None, None,
            "Confirm this loan's entered transactions against the paper records before borrower reminders.")
    if review.future_capture == "ROKKAD_ONLY" and as_of_date >= review.through_date:
        return _continued_capture(loan, review, as_of_date, events)
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


def _continued_capture(loan, review, as_of_date, events):
    """The reviewed prefix stays exact; only supported current actions may follow.

    Origin never establishes this mode. A new book review replaces the choice.
    Unknown event graphs fail closed instead of silently certifying capture.
    """
    rows = tuple(events) if events is not None else tuple(loan.loan_events.order_by("pk"))
    baseline = [e for e in rows if review.capture_event_id and e.pk <= review.capture_event_id]
    following = [e for e in rows if e not in baseline]
    valid = (review.confirmed_complete and review.capture_state == "ACTIVE" and bool(baseline)
        and transaction_fingerprint(loan, events=baseline, state=review.capture_state) == review.source_fingerprint
        and capture_contract_fingerprint(loan) == review.capture_contract_fingerprint)
    suffix_ids = {e.pk for e in following}
    allowed = {"INTEREST_ACCRUAL", "REPAYMENT", "RELEASE_RECEIPT", "RENEWAL_SETTLEMENT", "AUCTION_RECOVERY", "REVERSAL"}
    for event in following:
        payload = event.payload
        # Imported/recorded replays and agreement revisions are not current capture.
        source = (payload.get("history_correction") or payload.get("recorded_admission")
            or payload.get("repayment", {}).get("recording") or payload.get("release", {}).get("paper_closure")
            or payload.get("recording"))
        derived_recognition = (event.event_kind == "INTEREST_ACCRUAL" and payload.get("accrual")
            and not source and loan.policy_snapshot and loan.policy_snapshot.policy_version == 2
            and loan.policy_snapshot.basis != "RECORDED_CONTRACT"
            and loan.interest_accruals.filter(loan_event=event).exists())
        if (event.event_kind not in allowed or source or (event.effective_date < review.through_date and not derived_recognition)
            or event.created_at < review.reviewed_at or (event.reversal_of_id and event.reversal_of_id not in suffix_ids)):
            valid = False
        if event.event_kind == "INTEREST_ACCRUAL":
            key = payload.get("recorded_collection", {}).get("request_key", "")
            if key.startswith(("admission:", "correction:")):
                valid = False
    reversed_ids = {e.reversal_of_id for e in rows if e.reversal_of_id}
    terminal = any(e.event_kind in {"RELEASE_RECEIPT", "RENEWAL_SETTLEMENT", "AUCTION_RECOVERY"}
        and e.pk not in reversed_ids for e in following)
    valid = valid and loan.state == ("CLOSED" if terminal else "ACTIVE")
    message = (f"Transactions checked through {review.through_date}; subsequent activity is captured in Rokkad."
        if valid else "Paper activity, historical correction or the reviewed contract changed after the Rokkad-only transition. Check the records again.")
    return TransactionCompleteness("ROKKAD_ONLY" if valid else "CHANGED", True, bool(valid),
        review.through_date, review.pk, message)
