"""Reviewed identity correction on an active ordinary loan; no financial replay."""
from django.core import signing
from django.db import transaction
from django.db.models import Q

from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.access import LOANS_ADMIN_ACTION
from apps.tenant_apps.loans.selectors.transaction_completeness import transaction_fingerprint
from apps.tenant_apps.party.models import Party
from .action_access import require_loan_action
from django.utils import timezone
from apps.tenant_apps.loans.selectors.servicing_contract import resolve_servicing_contract
from apps.tenant_apps.loans.selectors.exposure import get_pawn_loan_exposure, require_consistent_exposure
from .recorded_history import _digest, _text

PROFILE = "recorded-borrower-correction/1"
SALT = "loans.recorded-borrower-correction.v1"


def borrower_notice_identity(loan):
    return dict(party_id=loan.borrower_id, correction_id=loan.change_log.filter(
        event_kind='BORROWER_CORRECTED').order_by('pk').values_list('pk', flat=True).last())


def borrower_document_fingerprint(loan, source_fingerprint):
    """Keep original issues addressable and bind new copies to the correction."""
    from .collateral_corrections import collateral_document_fingerprint
    from .agreement_corrections import agreement_document_fingerprint
    source_fingerprint = agreement_document_fingerprint(loan, source_fingerprint)
    source_fingerprint = collateral_document_fingerprint(loan, source_fingerprint)
    correction = loan.change_log.filter(event_kind="BORROWER_CORRECTED").order_by("pk").last()
    if correction is None:
        return source_fingerprint
    return _digest(dict(source=source_fingerprint, borrower_correction=correction.pk,
        request_sha256=correction.metadata["borrower_correction"]["request_sha256"]))


def corrected_ticket_source(loan, source):
    """Project current identity while preserving the genuine approval snapshot."""
    rows = list(loan.change_log.filter(event_kind="BORROWER_CORRECTED").order_by("pk"))
    if not rows:
        if source["borrower_id"] != loan.borrower_id:
            raise ValueError("Approved borrower does not match this loan.")
        return source, None
    prior = rows[0].metadata["borrower_correction"]["before"]["id"]
    # A draft/returned approval may have been issued after an identity merge.
    # Accept a source after a prefix of same-person merges, while still requiring
    # the complete immutable chain and preserving mistaken-borrower safeguards.
    source_identities, merge_prefix = {prior}, True
    for row in rows:
        evidence = row.metadata["borrower_correction"]
        if evidence["before"]["id"] != prior:
            raise ValueError("Borrower correction history needs reconciliation.")
        prior = evidence["after"]["id"]
        merge_prefix = merge_prefix and evidence.get("party_merge") is True
        if merge_prefix:
            source_identities.add(prior)
    if source["borrower_id"] not in source_identities:
        raise ValueError("Borrower correction does not match the original approval identity.")
    if prior != loan.borrower_id:
        raise ValueError("Current borrower differs from the reviewed correction.")
    return dict(source, borrower_id=loan.borrower_id), rows[-1]


def borrower_correction_blockers(loan):
    blockers = []
    try:
        resolve_servicing_contract(loan, as_of_date=timezone.localdate())
        require_consistent_exposure(get_pawn_loan_exposure(loan.pk, as_of_date=timezone.localdate()))
    except ValueError as exc:
        blockers.append(str(exc))
    if loan.collateral_items.exclude(custody_state="IN_VAULT").exists():
        blockers.append("Review collateral custody before correcting this loan's borrower.")
    if loan.state != "ACTIVE":
        blockers.append("Borrower correction requires an active loan.")
    if m.PawnLoanRenewal.objects.filter(Q(source_loan=loan) | Q(successor_loan=loan)).exists():
        blockers.append("Linked renewals require a review of both borrowers; this loan cannot be corrected separately.")
    if loan.auctions.exists() or m.FundingPledgeItem.objects.filter(collateral_item__loan=loan).exists():
        blockers.append("Auction or funding evidence requires a separate borrower reconciliation.")
    return blockers


def _facts(data):
    if not isinstance(data, dict) or set(data) != {"borrower_id", "reference", "reason", "request_key"}:
        raise ValueError("Select the correct borrower and provide the supporting reference and correction reason.")
    if type(data["borrower_id"]) is not int or data["borrower_id"] <= 0:
        raise ValueError("Select a customer from this Workspace.")
    return dict(borrower_id=data["borrower_id"],
        reference=_text(data["reference"], "the supporting agreement or book reference", 160),
        reason=_text(data["reason"], "the correction reason", 500),
        request_key=_text(data["request_key"], "the correction request reference", 80))


def _authorize(loan, actor):
    require_loan_action(loan, actor, LOANS_ADMIN_ACTION, "data.edit")


def _locked_source(loan_id):
    workspace_id = m.current_tenant_workspace_id()
    if workspace_id is None:
        raise ValueError("Borrower correction requires an active Workspace context.")
    try:
        # Lock Parties separately in sorted order; two different loans may have
        # opposite mistaken customer selections.
        return m.PawnLoan.objects.select_for_update(of=("self",)).get(
            pk=loan_id, workspace_id=workspace_id)
    except m.PawnLoan.DoesNotExist as exc:
        raise ValueError("Loan was not found in the active Workspace.") from exc


def _party_facts(party):
    return dict(id=party.pk, name=party.display_name, code=party.party_code, status=party.status)


def _review(loan, facts):
    blockers = borrower_correction_blockers(loan)
    if blockers:
        raise ValueError(" ".join(blockers))
    parties = {party.pk: party for party in Party.objects.select_for_update().filter(
        workspace_id=loan.workspace_id, pk__in=(loan.borrower_id, facts["borrower_id"])).order_by("pk")}
    target = parties.get(facts["borrower_id"])
    if target is None or target.status != Party.PartyStatus.ACTIVE:
        raise ValueError("Select an active customer from this Workspace.")
    if target.pk == loan.borrower_id:
        raise ValueError("This customer is already the loan's borrower.")
    review = dict(before=_party_facts(parties[loan.borrower_id]), after=_party_facts(target),
        loan_number=loan.loan_number, reference=facts["reference"], reason=facts["reason"],
        receipt_count=loan.loan_events.filter(event_kind="REPAYMENT").count())
    source = _digest(dict(transactions=transaction_fingerprint(loan), updated_at=loan.updated_at.isoformat(),
        latest_correction=loan.change_log.filter(event_kind="BORROWER_CORRECTED").values_list("pk", flat=True).last(),
        review=review))
    return review, source, target


@transaction.atomic
def preview_borrower_correction(loan_id, *, actor, data):
    facts = _facts(data)
    loan = _locked_source(loan_id)
    _authorize(loan, actor)
    review, source, _ = _review(loan, facts)
    token = signing.dumps(dict(loan=loan.pk, workspace=loan.workspace_id, actor=actor.pk,
        facts=_digest(facts), source=source), salt=SALT, compress=True)
    return review, token


@transaction.atomic
def record_borrower_correction(loan_id, *, actor, data, review_token, confirmed=False):
    facts = _facts(data)
    loan = _locked_source(loan_id)
    _authorize(loan, actor)
    if confirmed is not True:
        raise ValueError("Confirm the reviewed borrower correction.")
    existing = loan.change_log.filter(event_kind="BORROWER_CORRECTED",
        metadata__borrower_correction__request_key=facts["request_key"]).first()
    if existing:
        if existing.actor_id != actor.pk or existing.metadata["borrower_correction"]["request_sha256"] != _digest(facts):
            raise ValueError("This correction request already records different borrower facts.")
        return existing, False
    review, source, target = _review(loan, facts)
    try:
        signed = signing.loads(review_token or "", salt=SALT, max_age=3600)
    except signing.BadSignature as exc:
        raise ValueError("Review this borrower correction again.") from exc
    if signed != dict(loan=loan.pk, workspace=loan.workspace_id, actor=actor.pk, facts=_digest(facts), source=source):
        raise ValueError("Loan or customer facts changed. Review this borrower correction again.")
    correction = m.LoanChangeLog.objects.create(workspace_id=loan.workspace_id, loan=loan,
        event_kind="BORROWER_CORRECTED", from_state=loan.state, to_state=loan.state,
        actor=actor, reason=facts["reason"], metadata=dict(borrower_correction=dict(
            schema=PROFILE, request_key=facts["request_key"], request_sha256=_digest(facts),
            source_fingerprint=source, **review)))
    loan.borrower = target
    loan.updated_by = actor
    loan.save(update_fields=["borrower", "updated_by", "updated_at"])
    return correction, True
