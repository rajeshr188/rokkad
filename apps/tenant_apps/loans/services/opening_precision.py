"""Actual timestamp evidence for the explicitly precise opening contract."""
from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from django.utils import timezone

PROFILE = "loan-opening-review/5"


def timestamp(value, *, day, zone=None):
    try:
        result = datetime.fromisoformat(value) if isinstance(value, str) else value
        if not isinstance(result, datetime) or timezone.is_naive(result):
            raise ValueError
        local = result.astimezone(ZoneInfo(zone)) if zone else timezone.localtime(result)
        if local.date() != day or result > timezone.now():
            raise ValueError
        return result
    except (ValueError, TypeError, OverflowError, ZoneInfoNotFoundError) as exc:
        raise ValueError("Supply the actual aware timestamp on this transaction's business date, no later than now.") from exc


def validate_event_order(review, event):
    cutover = date.fromisoformat(review["cutover"]["date"])
    if event.effective_date < cutover:
        raise ValueError("Servicing cannot precede the opening checkpoint.")
    if event.effective_date > cutover:
        return None
    if review["profile"] != PROFILE:
        raise ValueError("Date-only opening servicing must be strictly after cutover.")
    if event.event_kind not in {"REPAYMENT", "RELEASE_RECEIPT", "RENEWAL_SETTLEMENT", "AUCTION_RECOVERY", "INTEREST_ACCRUAL", "REVERSAL"}:
        raise ValueError("Same-day cutover requires a supported explicitly timed action.")
    zone = review["cutover"]["timezone"]
    cutoff = timestamp(review["cutover"]["occurred_at"], day=cutover, zone=zone)
    detail = event.payload.get("reversal" if event.event_kind == "REVERSAL" else "opening_collection", {})
    occurred = timestamp(detail.get("occurred_at"), day=cutover, zone=zone)
    if occurred <= cutoff:
        raise ValueError("Same-day activity must occur strictly after the verified checkpoint timestamp.")
    if event.event_kind == "REPAYMENT" and event.payload["repayment"].get("recording"):
        recorded = event.payload["repayment"]["recording"].get("received_at")
        if timestamp(recorded, day=cutover, zone=zone) != occurred:
            raise ValueError("The opening action timestamp must match the actual paper receipt.")
    return occurred


def require_receipt_order(loan, *, on, received_at=None, paper=False, event_kind="REPAYMENT"):
    """Command gate, including dependencies on another receipt entered today."""
    origin = loan.loan_events.filter(event_kind="MIGRATION_OPENING").first()
    if origin is None or on != origin.effective_date:
        return
    review = origin.payload.get("opening", {}).get("review", {})
    occurred = received_at if paper else (received_at or timezone.now().isoformat())
    from types import SimpleNamespace
    event = SimpleNamespace(effective_date=on, event_kind=event_kind, payload={
        "opening_collection": {"occurred_at": occurred}, "repayment": {}})
    actual = validate_event_order(review, event)
    for prior in loan.loan_events.exclude(pk=origin.pk).filter(effective_date=on).order_by("pk"):
        previous = validate_event_order(review, prior)
        if previous >= actual:
            raise ValueError("Later or simultaneous checkpoint-day activity exists; reconcile its actual order before entering this receipt.")
