"""Correct dated paper closure facts without rewriting money or custody evidence."""
from datetime import date
from decimal import Decimal
from django.core import signing
from django.db import transaction
from django.utils import timezone
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.integrations import reversal_payload
from .event_recording import record_loan_event
from .obligations import reverse_event_obligation_allocations, reverse_event_schedule_change
from .pawn_repayment import _locked_loan, _record_pawn_loan_repayment_at
from .recorded_collections import collection_balance, recognize_collection_interest
from .recorded_corrections import PROFILE, _authorize, _source_id, dependencies, _facts as receipt_facts
from .recorded_history import _amount, _digest, _text
from .recorded_settlement_corrections import dependent_state, terminal_for, restate_settlement

SALT = "loans.paper-settlement-facts.v1"


def compensate_collections(loan, active, *, actor, context):
    """Caller holds the aggregate and performs the complete replay atomically."""
    sources = [e for e in active if e.event_kind in ("REPAYMENT", "INTEREST_ACCRUAL", "RELEASE_RECEIPT", "RENEWAL_SETTLEMENT")]
    for event in reversed(sources):
        payload = reversal_payload(loan, effective_date=event.effective_date, original_event_id=event.pk,
            original_event_kind=event.event_kind, values=event.payload["values"], reason=context["reason"]).to_dict()
        payload["history_correction"] = dict(context, role="COMPENSATION", root_event_id=_source_id(event), source_event_id=event.pk)
        if event.event_kind == "RENEWAL_SETTLEMENT":
            payload["renewal"] = event.payload["renewal"]
        reverse, _ = record_loan_event(loan.pk, event_kind="REVERSAL", effective_date=event.effective_date,
            payload=payload, actor=actor, reversal_of=event)
        reverse_event_obligation_allocations(original_event=event, reversal_event=reverse, actor=actor)
        if event.event_kind in ("RELEASE_RECEIPT", "RENEWAL_SETTLEMENT"):
            reverse_event_schedule_change(original_event=event, reversal_event=reverse, actor=actor)


def replay_collections(loan, active, *, actor, context, through):
    rows = []
    for index, event in enumerate(active):
        key = f"settlement-facts:{loan.pk}:{context['request_key']}:{index}"
        meta = dict(context, role="REPLAY", root_event_id=_source_id(event), source_event_id=event.pk)
        if event.event_kind == "REPAYMENT":
            if event.effective_date > through:
                raise ValueError("The corrected settlement cannot precede a retained receipt.")
            receipt = receipt_facts(event)
            result = _record_pawn_loan_repayment_at(loan.pk, amount=receipt["amount"], request_key=key, actor=actor,
                effective_date=event.effective_date, recording_evidence=event.payload["repayment"].get("recording"),
                correction_evidence=meta, replay_closed=True)
            rows.append(dict(receipt, principal=str(result.allocation.principal), interest=str(result.allocation.interest)))
        elif event.event_kind == "INTEREST_ACCRUAL":
            recognize_collection_interest(loan, min(event.effective_date, through), actor=actor, request_key=key, correction_evidence=meta)
    return rows


def restate_custody_date(source, *, day, actor):
    """A fact revision supersedes retained rows; it does not repeat a handover."""
    previous = source.payload.get("history_correction", {}).get("custody_restatement", {})
    if day == source.effective_date:
        return previous or None
    root = _source_id(source)
    if source.event_kind == "RELEASE_RECEIPT":
        document = m.PawnLoanRelease.objects.get(loan_event_id=root)
        rows = list(document.custody_events.filter(from_state="IN_VAULT").exclude(pk__in=previous.get("superseded", [])))
        relation = {"release": document}
    else:
        document = m.PawnLoanRenewal.objects.get(settlement_event_id=root)
        rows = list(document.custody_events.all().exclude(pk__in=previous.get("superseded", [])))
        relation = {"renewal": document}
    if not rows or any(row.effective_date != source.effective_date for row in rows):
        raise ValueError("The retained custody dates do not reconcile to the settlement being corrected.")
    replacements = [m.PawnCollateralCustodyEvent.objects.create(workspace_id=row.workspace_id,
        collateral_item_id=row.collateral_item_id, from_state=row.from_state, to_state=row.to_state,
        effective_date=day, actor=actor, restatement_of=row, **relation).pk for row in rows]
    return dict(profile="paper-custody-restatement/1", superseded=previous.get("superseded", []) + [row.pk for row in rows],
        replacements=replacements, actual_movement=False)


def _facts(data):
    fields = {"date", "amount", "recipient", "reference", "reason", "request_key"}
    if not isinstance(data, dict) or set(data) != fields:
        raise ValueError("Enter corrected closing date, settlement, recipient and supporting source.")
    facts = dict(data)
    day = date.fromisoformat(facts["date"])
    if day > timezone.localdate():
        raise ValueError("A corrected historical closure cannot be in the future.")
    facts["amount"] = _amount(facts["amount"], "settlement")
    if not isinstance(facts["recipient"], str):
        raise ValueError("Enter a recipient or leave it blank for an unspecified handover.")
    facts["recipient"] = facts["recipient"].strip()
    if len(facts["recipient"]) > 255:
        raise ValueError("Recipient is too long.")
    for name, limit in (("reference", 255), ("reason", 500), ("request_key", 80)):
        facts[name] = _text(facts[name], name, limit)
    return facts


def _source(loan_id, actor, facts):
    loan = _locked_loan(loan_id)
    _authorize(loan, actor)
    from .action_access import require_loan_action
    require_loan_action(loan, actor, "loan.release")
    _, active, blockers = dependencies(loan)
    if blockers:
        raise ValueError(" ".join(blockers))
    terminal = terminal_for(loan, active)
    if terminal is None or terminal.event_kind != "RELEASE_RECEIPT":
        raise ValueError("Use the paired successor contract review for a renewal-date correction.")
    paper = terminal.payload.get("release", {}).get("paper_closure", {})
    if paper.get("profile") != "recorded-history-closure/1":
        raise ValueError("This correction requires a dated paper closure.")
    if bool(facts["recipient"]) != (paper.get("closure_basis") == "RETURNED"):
        raise ValueError("Preserve the confirmed or unspecified custody basis. Use later handover confirmation when evidence becomes available.")
    day = date.fromisoformat(facts["date"])
    if day < loan.loan_date or any(e.effective_date > day for e in active if e.event_kind == "REPAYMENT"):
        raise ValueError("The corrected closure cannot precede its original contract or retained receipts.")
    from .paper_handover import confirmation_for
    release = m.PawnLoanRelease.objects.get(loan_event_id=_source_id(terminal))
    handover = confirmation_for(release)
    if handover and day > date.fromisoformat(handover["facts"]["date"]):
        raise ValueError("The corrected closure cannot follow the separately confirmed customer handover.")
    lineage, downstream = dependent_state(loan, actor=actor)
    return loan, active, terminal, lineage


def _run(loan, active, terminal, facts, actor):
    context = dict(schema=PROFILE, operation="SETTLEMENT_FACTS", request_key=facts["request_key"], request_sha256=_digest(facts),
        reason=facts["reason"], recorder_id=actor.pk, restated=True)
    before = dict(date=terminal.effective_date.isoformat(), amount=str(sum((Decimal(terminal.payload["values"][name]) for name in ("principal", "interest", "fees")), Decimal("0"))),
        recipient=terminal.payload["release"]["paper_closure"]["collector_name"])
    compensate_collections(loan, active, actor=actor, context=context)
    day = date.fromisoformat(facts["date"])
    rows = replay_collections(loan, active, actor=actor, context=context, through=day)
    custody = restate_custody_date(terminal, day=day, actor=actor)
    rows.append(restate_settlement(loan, terminal, actor=actor, facts=dict(date=facts["date"], cash_received=facts["amount"],
        cash_paid="0", interest_offset="0", reference=facts["reference"], recipient=facts["recipient"]), context=context,
        custody_restatement=custody))
    review = dict(before=before, after=dict(date=facts["date"], amount=facts["amount"], recipient=facts["recipient"]), rows=rows,
        reference=facts["reference"], reason=facts["reason"], custody="Existing custody basis retained; dated evidence restated, no physical movement")
    m.LoanChangeLog.objects.create(loan=loan, workspace_id=loan.workspace_id, event_kind="REVERSAL_RECORDED",
        from_state=loan.state, to_state=loan.state, actor=actor, reason=facts["reason"], metadata=dict(history_correction=context, review=review))
    return review


@transaction.atomic
def preview_settlement_facts(loan_id, *, actor, data):
    facts = _facts(data)
    loan, active, terminal, lineage = _source(loan_id, actor, facts)
    with transaction.atomic():
        review = _run(loan, active, terminal, facts, actor)
        transaction.set_rollback(True)
    return review, signing.dumps(dict(loan=loan.pk, workspace=loan.workspace_id, actor=actor.pk,
        facts=_digest(facts), lineage=lineage, review=review), salt=SALT, compress=True)


@transaction.atomic
def record_settlement_facts(loan_id, *, actor, data, review_token, confirmed=False):
    facts = _facts(data)
    loan = _locked_loan(loan_id)
    _authorize(loan, actor)
    existing = loan.change_log.filter(metadata__history_correction__operation="SETTLEMENT_FACTS",
        metadata__history_correction__request_key=facts["request_key"]).first()
    if existing:
        if existing.actor_id != actor.pk or existing.metadata["history_correction"]["request_sha256"] != _digest(facts):
            raise ValueError("This request already records different closing facts.")
        return existing, False
    if confirmed is not True:
        raise ValueError("Confirm the complete corrected closing facts.")
    loan, active, terminal, lineage = _source(loan_id, actor, facts)
    try:
        signed = signing.loads(review_token or "", salt=SALT, max_age=3600)
    except signing.BadSignature as exc:
        raise ValueError("Review these closing facts again.") from exc
    if any(signed.get(k) != v for k, v in dict(loan=loan.pk, workspace=loan.workspace_id, actor=actor.pk,
            facts=_digest(facts), lineage=lineage).items()):
        raise ValueError("Loan or closing facts changed. Review again.")
    review = _run(loan, active, terminal, facts, actor)
    if _digest(review) != _digest(signed["review"]):
        raise ValueError("Closing calculation changed. Review again.")
    return loan.change_log.filter(metadata__history_correction__request_key=facts["request_key"]).latest("pk"), True
