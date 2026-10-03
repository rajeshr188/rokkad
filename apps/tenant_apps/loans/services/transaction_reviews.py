"""Signed, aggregate-bound review; no change to money, dates, custody or quotes."""
from datetime import date
from django.core import signing
from django.db import transaction
from django.utils import timezone
from apps.tenant_apps.loans.models import LoanTransactionReview, PawnLoan, current_tenant_workspace_id
from apps.tenant_apps.loans.selectors.transaction_completeness import transaction_fingerprint
from .action_access import require_loan_action

SALT = "loans.transaction-review.v1"


def _loan(loan_id, actor):
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise ValueError("Transaction review requires an active Workspace.")
    loan = PawnLoan.objects.select_for_update(of=("self",)).select_related("workspace").get(pk=loan_id, workspace_id=workspace_id)
    require_loan_action(loan, actor, "data.edit")
    if loan.state not in ("ACTIVE", "CLOSED"):
        raise ValueError("Review an active or closed loan.")
    return loan


def _facts(loan, actor, *, through_date, confirmed_complete, source_reference, request_key):
    opening = loan.loan_events.filter(event_kind="MIGRATION_OPENING").first()
    first_day = opening.effective_date if opening else loan.loan_date
    if type(through_date) is not date or not first_day <= through_date <= timezone.localdate():
        raise ValueError("Review date must be between the loan's opening checkpoint (or original date) and today.")
    if type(confirmed_complete) is not bool:
        raise ValueError("Choose whether all paper transactions have been entered.")
    source_reference, request_key = str(source_reference or "").strip(), str(request_key or "").strip()
    if not source_reference or len(source_reference) > 500 or not request_key or len(request_key) > 120:
        raise ValueError("A checked source reference/reason and a review request key are required.")
    return dict(loan=loan.pk, workspace=loan.workspace_id, actor=actor.pk,
        through_date=through_date.isoformat(), confirmed_complete=confirmed_complete,
        source_reference=source_reference, request_key=request_key)


def _review(loan, facts):
    if loan.loan_events.count() > 1000:
        raise ValueError("This loan exceeds the 1,000-event interactive review limit.")
    return dict(**facts, source_fingerprint=transaction_fingerprint(loan),
        previous_review=loan.transaction_reviews.order_by("-pk").values_list("pk", flat=True).first(),
        state=loan.state, reviewed_on=timezone.localdate().isoformat(),
        events=[dict(id=e.pk, event_kind=e.event_kind, effective_date=e.effective_date,
            values=e.payload.get("values", {}), reference=e.payload.get("repayment", {}).get("recording", {}).get("receipt_reference", ""),
            recorded_at=timezone.localtime(e.created_at).strftime("%d %b %Y, %H:%M:%S")) for e in loan.loan_events.order_by("effective_date", "pk")])


@transaction.atomic
def preview_transaction_review(loan_id, *, actor, **data):
    loan = _loan(loan_id, actor)
    review = _review(loan, _facts(loan, actor, **data))
    review["events"] = [dict(row, effective_date=row["effective_date"].isoformat()) for row in review["events"]]
    return review, signing.dumps(review, salt=SALT, compress=True)


@transaction.atomic
def confirm_transaction_review(loan_id, *, actor, review_token, acknowledged, **data):
    loan = _loan(loan_id, actor)
    facts = _facts(loan, actor, **data)
    if acknowledged is not True:
        raise ValueError("Confirm that you checked the source records and the displayed loan activity.")
    try:
        signed = signing.loads(review_token, salt=SALT, max_age=3600)
    except signing.BadSignature as exc:
        raise ValueError("Review expired or changed; preview again.") from exc
    if any(signed.get(k) != v for k, v in facts.items()):
        raise ValueError("Review details changed; preview again.")
    existing = loan.transaction_reviews.filter(request_key=facts["request_key"]).first()
    if existing:
        if (existing.source_fingerprint != signed["source_fingerprint"] or existing.reviewed_by_id != actor.pk
            or existing.through_date.isoformat() != facts["through_date"]
            or existing.confirmed_complete != facts["confirmed_complete"] or existing.source_reference != facts["source_reference"]):
            raise ValueError("This request key belongs to another review.")
        return existing, False
    current, _ = preview_transaction_review(loan_id, actor=actor, **data)
    if signed != current:
        raise ValueError("Loan activity or the previous review changed; preview again.")
    return _store(loan, actor, **data), True


def _store(loan, actor, *, through_date, confirmed_complete, source_reference, request_key):
    """Internal: caller owns loan lock, authorization and aggregate reconciliation."""
    result = LoanTransactionReview.objects.create(workspace_id=loan.workspace_id, loan=loan,
        through_date=through_date, confirmed_complete=confirmed_complete, source_reference=source_reference,
        source_fingerprint=transaction_fingerprint(loan), request_key=request_key, reviewed_by=actor)
    from apps.tenant_apps.loans.models import LoanRiskSnapshot
    LoanRiskSnapshot.objects.filter(loan=loan).update(status="STALE", error_message="Transaction review changed; reassess monitoring.")
    return result
