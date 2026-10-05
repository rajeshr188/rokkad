"""Reviewed historical restatement of receipts on recorded anniversary loans.

Original events survive. Compensation has the original business date; its creation
time records when the correction became known. Replay preserves actual cash facts.
"""
from datetime import date
from decimal import Decimal

from django.core import signing
from django.db import transaction
from django.utils import timezone

from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.access import LOANS_ADMIN_ACTION
from apps.tenant_apps.loans.integrations import reversal_payload
from .action_access import require_loan_action
from .event_recording import record_loan_event
from .obligations import reverse_event_obligation_allocations, reverse_event_schedule_change
from .paper_repayments import _evidence
from .pawn_repayment import _locked_loan, _record_pawn_loan_repayment_at
from .recorded_collections import recording_for, collection_balance, recognize_collection_interest
from .recorded_history import _amount, _digest, _text
from .recorded_numbers import identity
from .recorded_settlement_corrections import terminal_for, dependent_state, restate_settlement

PROFILE = "recorded-history-correction/1"
SALT = "loans.recorded-correction.review.v1"


def correction_input(data):
    fields = {"operation", "target", "date", "amount", "reference", "before", "reason", "request_key"}
    if not isinstance(data, dict) or not fields <= set(data) or set(data) - fields - {"settlement", "item_principal_split", "replay_item_splits"}:
        raise ValueError("Correction fields are incomplete or unsupported.")
    value = dict(data)
    from .paper_repayments import normalize_item_split
    if "item_principal_split" in value:
        value["item_principal_split"] = normalize_item_split(value["item_principal_split"])
    if "replay_item_splits" in value:
        if not isinstance(value["replay_item_splits"], dict) or len(value["replay_item_splits"]) > 120:
            raise ValueError("Enter reviewed item splits for retained receipts.")
        value["replay_item_splits"] = {str(key): normalize_item_split(split) for key, split in value["replay_item_splits"].items()}
    if value["operation"] not in ("ADD", "REPLACE", "VOID"):
        raise ValueError("Choose a missing receipt, replacement or void.")
    for key in ("target", "before"):
        if value[key] is not None and (type(value[key]) is not int or value[key] <= 0):
            raise ValueError("Select a valid receipt from this loan.")
    if (value["operation"] == "ADD") != (value["target"] is None):
        raise ValueError("Select a receipt only for replacement or void.")
    value["reason"] = _text(value["reason"], "the correction reason", 500)
    value["request_key"] = _text(value["request_key"], "the correction request reference", 80)
    if "settlement" in value:
        facts = value["settlement"]
        if not isinstance(facts, dict) or set(facts) != {"cash_received", "cash_paid", "interest_offset", "reference", "confirmed_unchanged"}:
            raise ValueError("Supply the actual settlement cash and confirm unchanged agreement and custody.")
        if facts["confirmed_unchanged"] is not True:
            raise ValueError("Confirm that the settlement date, successor agreement and physical custody facts remain correct.")
        value["settlement"] = dict(facts, **{key: _amount(facts[key], key.replace("_", " "))
            for key in ("cash_received", "cash_paid", "interest_offset")})
        value["settlement"]["reference"] = _text(facts["reference"], "the settlement source reference", 255)
    if value["operation"] == "VOID":
        if any(value[key] not in (None, "") for key in ("date", "amount", "reference", "before")):
            raise ValueError("For a void, leave the new receipt fields and ordering blank.")
    else:
        try:
            day = date.fromisoformat(value["date"])
        except (ValueError, TypeError):
            raise ValueError("Enter the actual receipt date.") from None
        if day > timezone.localdate():
            raise ValueError("The receipt date cannot be in the future.")
        value["date"] = day.isoformat()
        value["amount"] = _amount(value["amount"], "cash received", positive=True)
        value["reference"] = _text(value["reference"], "the paper receipt reference", 255)
    return value


def _authorize(loan, actor):
    require_loan_action(loan, actor, LOANS_ADMIN_ACTION, "loan.repay", "loan.accrue")


def dependencies(loan, *, batch_id=None):
    """List source evidence and blockers without pretending lifecycle replay is safe."""
    events = list(loan.loan_events.select_related("reversed_by_event").order_by("effective_date", "pk")[:1001])
    reversed_ids = {e.reversal_of_id for e in events if e.reversal_of_id}
    active = [e for e in events if e.event_kind != "REVERSAL" and e.pk not in reversed_ids]
    blockers = []
    if not recording_for(loan):
        blockers.append("This correction profile requires an admitted paper anniversary contract; native and migration-opening corrections use their own supported workflows.")
    terminal = None
    try:
        terminal = terminal_for(loan, active, batch_id=batch_id)
    except (ValueError, m.PawnLoanRelease.DoesNotExist, m.PawnLoanRenewal.DoesNotExist) as exc:
        blockers.append(str(exc))
    if loan.state != "ACTIVE" and terminal is None:
        blockers.append("The loan needs a supported full closure or renewal settlement to reconcile its history.")
    origins = [e for e in active if e.event_kind in ("DISBURSAL", "RENEWAL_OPENING")]
    if len(origins) != 1:
        blockers.append("Exactly one unchanged origination or renewal opening is required.")
    for event in active:
        if event in origins or event is terminal:
            continue
        if event.event_kind not in ("REPAYMENT", "INTEREST_ACCRUAL"):
            blockers.append(f"Event #{event.pk} ({event.event_kind}) needs a lifecycle correction beyond this receipt review.")
        elif event.event_kind == "INTEREST_ACCRUAL" and not event.payload.get("recorded_collection"):
            blockers.append(f"Accrual #{event.pk} does not use the recorded anniversary calculation.")
    if any(e.event_kind == "REVERSAL" and e.payload.get("history_correction", {}).get("schema") != PROFILE for e in events):
        blockers.append("Existing corrections outside this historical-restatement profile require separate reconciliation.")
    if len(events) > 1000 or len(active) > 121:
        blockers.append("This history exceeds the supported review limit of 120 collection events and 1,000 retained events.")
    if terminal is None and loan.collateral_items.exclude(custody_state="IN_VAULT").exists():
        blockers.append("Collateral is not currently held in the vault; review its custody dependencies first.")
    return events, active, blockers


def _source_id(event):
    return event.payload.get("history_correction", {}).get("root_event_id") or event.pk


def _facts(event):
    receipt = event.payload["repayment"]
    recording = receipt.get("recording")
    return dict(date=event.effective_date.isoformat(), amount=receipt["amount_received"],
                reference=recording["receipt_reference"] if recording else f"Recorded receipt #{event.pk}")


def _plan(loan, data, events, active):
    receipts = {e.pk: e for e in active if e.event_kind == "REPAYMENT"}
    if set(data.get("replay_item_splits", {})) - {str(key) for key in receipts}:
        raise ValueError("A replay item split references a receipt outside this active history.")
    target = receipts.get(data["target"])
    if data["target"] is not None and target is None:
        raise ValueError("The selected receipt is not an active receipt on this loan. Reload the correction review.")
    if data["operation"] != "VOID":
        if date.fromisoformat(data["date"]) < loan.loan_date:
            raise ValueError("The receipt cannot precede this contract's original date.")
        key = identity(data["reference"])
        for event in events:
            recording = event.payload.get("repayment", {}).get("recording")
            if recording and identity(recording["receipt_reference"]) == key:
                if target is None or _source_id(event) != _source_id(target):
                    raise ValueError("This paper reference already belongs to another receipt, including its retained corrections.")
    anchor = receipts.get(data["before"])
    if data["before"] is not None and (anchor is None or anchor is target or anchor.effective_date.isoformat() != data["date"]):
        raise ValueError("The ordering reference must be another active receipt on the same actual date.")
    ordered = [(e.effective_date.isoformat(), e.pk * 2, e) for e in active
               if e.event_kind in ("REPAYMENT", "INTEREST_ACCRUAL") and e is not target]
    if data["operation"] != "VOID":
        position = anchor.pk * 2 - 1 if anchor else (
            target.pk * 2 if target and target.effective_date.isoformat() == data["date"] else max((e.pk for e in events), default=0) * 2 + 1)
        ordered.append((data["date"], position, None))
    return target, sorted(ordered, key=lambda row: row[:2])


def _balance(loan):
    balance = collection_balance(loan, timezone.localdate())
    return dict(principal=str(balance.principal_outstanding), interest=str(balance.interest_outstanding), total=str(balance.total_due))


def _run(loan, actor, data, events, active, *, batch_context=None):
    target, ordered = _plan(loan, data, events, active)
    terminal = terminal_for(loan, active, batch_id=batch_context["id"] if batch_context else None)
    if terminal:
        require_loan_action(loan, actor, "loan.release")
        if data["operation"] != "VOID" and date.fromisoformat(data["date"]) > terminal.effective_date:
            raise ValueError("The corrected receipt cannot be after the recorded settlement date.")
    elif data.get("settlement"):
        raise ValueError("This loan has no settlement to correct. Leave settlement fields blank.")
    before = _balance(loan)
    context = dict(schema=PROFILE, request_key=data["request_key"], request_sha256=_digest(data),
                   reason=data["reason"], operation=data["operation"], target_event_id=data["target"],
                   recorder_id=actor.pk, restated=True)
    if batch_context:
        context["batch_correction"] = batch_context
    # Reverse all supported collections newest first, including their obligation
    # allocations. Same-date compensation makes corrected business-date reads exact.
    sources = [e for e in active if e.event_kind in ("REPAYMENT", "INTEREST_ACCRUAL") or e is terminal]
    for event in reversed(sources):
        payload = reversal_payload(loan, effective_date=event.effective_date, original_event_id=event.pk,
            original_event_kind=event.event_kind, values=event.payload["values"], reason=data["reason"]).to_dict()
        payload["history_correction"] = dict(context, role="COMPENSATION", description="Compensation of prior recorded calculation",
            root_event_id=_source_id(event), source_event_id=event.pk)
        if event.event_kind == "RENEWAL_SETTLEMENT":
            # Cash reports must negate the actual original movement, not carried debt.
            payload["renewal"] = event.payload["renewal"]
        reverse, _ = record_loan_event(loan.pk, event_kind="REVERSAL", effective_date=event.effective_date,
                                      payload=payload, actor=actor, reversal_of=event)
        reverse_event_obligation_allocations(original_event=event, reversal_event=reverse, actor=actor)
        if event is terminal:
            reverse_event_schedule_change(original_event=event, reversal_event=reverse, actor=actor)
    rows = []
    if data["operation"] == "VOID":
        rows.append(dict(source=target.pk, action="Void mistaken receipt (no refund)", **_facts(target),
            old_principal=target.payload["values"]["principal"], old_interest=target.payload["values"]["interest"], principal="0", interest="0", new_amount="0"))
    for index, (day, _, source) in enumerate(ordered):
        key = f"correction:{data['request_key']}:{index}"
        original = source or target
        meta = dict(context, role="REPLAY" if source else "REPLACEMENT" if target else "MISSING_RECEIPT",
            description="Recalculated existing event" if source else "Corrected receipt facts" if target else "Previously missing paper receipt",
            source_event_id=original.pk if original else None, root_event_id=_source_id(original) if original else None)
        if source and source.event_kind == "INTEREST_ACCRUAL":
            accrual = recognize_collection_interest(loan, source.effective_date, actor=actor, request_key=key, correction_evidence=meta)
            rows.append(dict(source=source.pk, action="Recalculate interest", date=day, reference="Anniversary interest", amount="0", new_amount="0",
                old_principal="0", old_interest=source.payload["values"]["interest"], principal="0",
                interest=accrual.payload["values"]["interest"] if accrual else "0"))
            continue
        facts = _facts(source) if source else data
        evidence = source.payload["repayment"].get("recording") if source else _evidence(
            received_on=date.fromisoformat(day), receipt_reference=data["reference"], amount=Decimal(data["amount"]),
            item_principal_split=data.get("item_principal_split"))
        if source and str(source.pk) in data.get("replay_item_splits", {}):
            evidence = _evidence(received_on=source.effective_date, receipt_reference=facts["reference"],
                amount=Decimal(facts["amount"]), item_principal_split=data["replay_item_splits"][str(source.pk)])
        result = _record_pawn_loan_repayment_at(loan.pk, amount=facts["amount"], request_key=key, actor=actor,
            effective_date=date.fromisoformat(day), recording_evidence=evidence, correction_evidence=meta,
            replay_closed=terminal is not None)
        values = original.payload["values"] if original else {}
        rows.append(dict(source=original.pk if original else None, action="Reallocate existing receipt" if source else "Replace mistaken receipt" if target else "Add missing receipt",
            date=day, reference=facts["reference"], amount=_facts(original)["amount"] if original else "0", new_amount=facts["amount"],
            old_date=original.effective_date.isoformat() if original else None, old_reference=_facts(original)["reference"] if original else None,
            old_principal=values.get("principal", "0"), old_interest=values.get("interest", "0"),
            principal=str(result.allocation.principal), interest=str(result.allocation.interest)))
    if terminal:
        rows.append(restate_settlement(loan, terminal, actor=actor, facts=data["settlement"], context=context))
    after = _balance(loan)
    review = dict(rows=rows, before=before, after=after, reversed_count=len(sources), reason=data["reason"],
                  effective_basis="RESTATED_BUSINESS_DATES", complete_through=recording_for(loan)["admission"]["complete_through"])
    m.LoanChangeLog.objects.create(loan=loan, event_kind="REVERSAL_RECORDED", from_state=loan.state, to_state=loan.state,
        actor=actor, reason=data["reason"], metadata=dict(history_correction=context, review=review))
    return review


def _state(events):
    return [[e.pk, e.payload_fingerprint, e.effective_date.isoformat()] for e in events]


def _settlement_blockers(loan, active, data):
    terminal = terminal_for(loan, active)
    if terminal and "settlement" not in data:
        return [f"{terminal.event_kind} #{terminal.pk}: supply actual settlement cash and confirm its agreement and custody before reviewing this correction."]
    return []


@transaction.atomic
def preview_correction(loan_id, *, actor, data):
    data = correction_input(data)
    loan = _locked_loan(loan_id)
    _authorize(loan, actor)
    events, active, blockers = dependencies(loan)
    from apps.tenant_apps.loans.selectors.servicing_dependencies import servicing_dependencies
    dependency_snapshot = servicing_dependencies(loan, effective_date=loan.loan_date).evidence()
    dependency_rows = [dict(id=e.pk, kind=e.event_kind, date=e.effective_date.isoformat()) for e in active]
    if blockers:
        return dict(blockers=blockers, dependencies=dependency_rows), ""
    blockers = _settlement_blockers(loan, active, data)
    if blockers:
        return dict(blockers=blockers, dependencies=dependency_rows), ""
    lineage, downstream = dependent_state(loan, actor=actor)
    with transaction.atomic():
        review = _run(loan, actor, data, events, active)
        transaction.set_rollback(True)
    review.update(blockers=[], dependencies=dependency_rows, downstream=downstream)
    token = signing.dumps(dict(workspace=loan.workspace_id, loan=loan.pk, actor=actor.pk, data=_digest(data),
                               state=_state(events), lineage=lineage, dependency_snapshot=dependency_snapshot, review=review), salt=SALT, compress=True)
    return review, token


@transaction.atomic
def record_correction(loan_id, *, actor, data, review_token, confirmed=False):
    data = correction_input(data)
    loan = _locked_loan(loan_id)
    _authorize(loan, actor)
    if confirmed is not True:
        raise ValueError("Confirm the complete correction review before recording it.")
    existing = loan.loan_events.filter(payload__history_correction__request_key=data["request_key"]).first()
    if existing:
        if existing.payload["history_correction"]["request_sha256"] != _digest(data):
            raise ValueError("This correction request already records different facts.")
        return False
    events, active, blockers = dependencies(loan)
    if blockers:
        raise ValueError(" ".join(blockers))
    blockers = _settlement_blockers(loan, active, data)
    if blockers:
        raise ValueError(" ".join(blockers))
    lineage, _ = dependent_state(loan, actor=actor)
    try:
        signed = signing.loads(review_token or "", salt=SALT, max_age=3600)
    except (signing.BadSignature, TypeError, ValueError):
        raise ValueError("Preview the correction again; its review is missing or expired.") from None
    if (signed.get("workspace"), signed.get("loan"), signed.get("actor"), signed.get("data"), signed.get("state")) != (
            loan.workspace_id, loan.pk, actor.pk, _digest(data), _state(events)):
        raise ValueError("The loan, receipt or recording context changed. Preview the correction again.")
    from apps.tenant_apps.loans.selectors.servicing_dependencies import servicing_dependencies
    if signed.get("dependency_snapshot") != servicing_dependencies(loan, effective_date=loan.loan_date).evidence():
        raise ValueError("Financial, accrual or collateral dependencies changed. Preview the correction again.")
    if signed.get("lineage") != lineage:
        raise ValueError("Dependent loan activity or custody changed. Preview the correction again.")
    review = _run(loan, actor, data, events, active)
    if any(signed["review"].get(key) != value for key, value in review.items()):
        raise ValueError("Calculated results changed. Preview the correction again.")
    return True
