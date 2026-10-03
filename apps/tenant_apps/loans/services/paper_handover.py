"""Append confirmed customer handover to a financially closed paper loan."""
from datetime import date

from django.core import signing
from django.db import transaction
from django.utils import timezone

from apps.tenant_apps.loans import models as m
from .action_access import require_loan_action
from .pawn_release import _locked_loan
from .recorded_history import _digest, _text
from .storage_operations import remove_collateral_from_storage

PROFILE = "paper-handover-confirmation/1"
SALT = "loans.paper-handover.v1"


def _source(loan_id, actor, data):
    loan = _locked_loan(loan_id)
    require_loan_action(loan, actor, "loan.release")
    if not isinstance(data, dict) or set(data) != {"date", "recipient", "reference", "request_key"}:
        raise ValueError("Enter the actual handover date, recipient and supporting reference.")
    facts = dict(data)
    day = date.fromisoformat(facts["date"])
    for name, limit in (("recipient", 255), ("reference", 160), ("request_key", 120)):
        facts[name] = _text(facts[name], name, limit)
    releases = list(loan.releases.select_related("loan_event").order_by("pk"))
    if loan.state != "CLOSED" or len(releases) != 1:
        raise ValueError("Confirm handover for one financially closed paper loan.")
    release = releases[0]
    paper = release.loan_event.payload.get("release", {}).get("paper_closure", {})
    if paper.get("profile") != "recorded-history-closure/1" or paper.get("closure_basis") != "PAPER_SETTLEMENT" or hasattr(release, "reversal"):
        raise ValueError("This release does not have an unconfirmed paper handover.")
    from apps.tenant_apps.loans.selectors.recorded_settlements import current_settlement
    if not current_settlement(release.loan_event).effective_date <= day <= timezone.localdate():
        raise ValueError("Handover date must be between financial closure and today.")
    items = list(loan.collateral_items.select_for_update().order_by("pk"))
    return loan, release, items, facts


def confirmation_for(release):
    """Source evidence; original release bytes and returned_at remain unchanged."""
    paper = (getattr(release.loan_event, "payload", {}) or {}).get("release", {}).get("paper_closure", {})
    if paper.get("profile") != "recorded-history-closure/1" or paper.get("closure_basis") != "PAPER_SETTLEMENT":
        return None
    log = release.loan.change_log.filter(metadata__profile=PROFILE, metadata__release_id=release.pk).order_by("-pk").first()
    return log.metadata if log else None


def release_document_fingerprint(release):
    from apps.tenant_apps.loans.selectors.recorded_settlements import current_settlement
    fingerprint = current_settlement(release.loan_event).payload_fingerprint
    handover = confirmation_for(release)
    return _digest(dict(financial=fingerprint, handover=handover)) if handover else fingerprint


def _review(loan, release, items, facts):
    if not items or any(item.custody_state != "PAPER_CLOSED" for item in items):
        raise ValueError("Customer handover is already confirmed or custody needs reconciliation.")
    day = date.fromisoformat(facts["date"])
    from apps.tenant_apps.loans.selectors.recorded_custody import current_custody_history
    if any(row.effective_date > day for item in items for row in current_custody_history(item)):
        raise ValueError("Later custody activity needs reconciliation before this handover.")
    return dict(loan=loan.pk, workspace=loan.workspace_id, number=loan.loan_number,
        release=release.pk, facts=facts, items=[dict(id=i.pk, description=i.description,
        custody=i.custody_state, location=i.current_storage_location_id,
        history=list(i.custody_history.order_by("pk").values_list("pk", flat=True))) for i in items],
        financial=list(loan.loan_events.order_by("pk").values_list("pk", "payload_fingerprint")))


@transaction.atomic
def preview_paper_handover(loan_id, *, actor, data):
    loan, release, items, facts = _source(loan_id, actor, data)
    review = _review(loan, release, items, facts)
    return review, signing.dumps(dict(actor=actor.pk, review=review), salt=SALT, compress=True)


@transaction.atomic
def confirm_paper_handover(loan_id, *, actor, data, review_token, confirmed=False):
    loan, release, items, facts = _source(loan_id, actor, data)
    existing = loan.change_log.filter(metadata__profile=PROFILE, metadata__request_key=facts["request_key"]).first()
    if existing:
        if existing.metadata.get("facts_sha256") != _digest(facts) or existing.actor_id != actor.pk:
            raise ValueError("This submission already confirmed different handover facts.")
        return existing, False
    if confirmed is not True:
        raise ValueError("Confirm that you checked the customer handover evidence.")
    try:
        signed = signing.loads(review_token or "", salt=SALT, max_age=3600)
    except signing.BadSignature as exc:
        raise ValueError("Review this handover again.") from exc
    # Signing serializes tuples to lists. Canonical digest compares JSON meaning.
    review = _review(loan, release, items, facts)
    if signed.get("actor") != actor.pk or _digest(signed.get("review")) != _digest(review):
        raise ValueError("Loan or custody facts changed. Review again.")
    evidence = dict(profile=PROFILE, release_id=release.pk, request_key=facts["request_key"],
        facts_sha256=_digest(facts), facts=facts, custody_event_ids=[])
    for item in items:
        event = m.PawnCollateralCustodyEvent.objects.create(workspace_id=loan.workspace_id,
            collateral_item=item, release=release, from_state="PAPER_CLOSED", to_state="WITH_CUSTOMER",
            effective_date=date.fromisoformat(facts["date"]), actor=actor)
        evidence["custody_event_ids"].append(event.pk)
        item.custody_state = "WITH_CUSTOMER"
        item.save(update_fields=["custody_state", "updated_at"])
        remove_collateral_from_storage(item, workflow_source="PAPER_HANDOVER",
            source_reference=str(event.pk), actor=actor)
    result = m.LoanChangeLog.objects.create(workspace_id=loan.workspace_id, loan=loan,
        event_kind="RELEASE_COMPLETED", from_state="CLOSED", to_state="CLOSED", actor=actor,
        reason="Customer handover confirmed from supporting records.", metadata=evidence)
    return result, True
