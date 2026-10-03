"""Restate mistaken original paper terms with retained snapshot revisions."""
from copy import deepcopy
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from django.core import signing
from django.db import transaction
from django.utils import timezone
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.integrations import disbursal_payload, reversal_payload
from .event_recording import record_loan_event
from .obligations import persist_disbursal_repayment_schedule, reverse_event_obligation_allocations, reverse_event_schedule_change
from .pawn_repayment import _locked_loan, _record_pawn_loan_repayment_at
from .recorded_collections import recording_for, collection_balance, recognize_collection_interest
from .recorded_corrections import PROFILE, _authorize, _facts as receipt_facts, _source_id, dependencies
from .recorded_history import _amount, _digest, _text
from .recorded_settlement_corrections import dependent_state, terminal_for, restate_settlement

SALT = "loans.recorded-contract-correction.v1"


def _facts(data):
    fields = {"date", "principal", "rate", "cash_paid", "reference", "reason", "request_key"}
    if not isinstance(data, dict) or not fields <= set(data) or set(data) - fields - {"settlement", "predecessor"}:
        raise ValueError("Enter corrected original date, principal, monthly rate and proceeds, with supporting reference.")
    value = deepcopy(data)
    try:
        day = date.fromisoformat(value["date"])
    except (ValueError, TypeError):
        raise ValueError("Enter the corrected original date.") from None
    if day > timezone.localdate():
        raise ValueError("The original transaction cannot be in the future.")
    value["date"] = day.isoformat()
    for name, places in (("principal", 2), ("rate", 6), ("cash_paid", 2)):
        value[name] = _amount(value[name], name, places=places, positive=name != "rate")
    if Decimal(value["rate"]) > 999:
        raise ValueError("Monthly rate exceeds the supported range.")
    for name, limit in (("reference", 160), ("reason", 500), ("request_key", 80)):
        value[name] = _text(value[name], name, limit)
    if "settlement" in value:
        from .recorded_corrections import correction_input
        check = correction_input(dict(operation="VOID", target=1, date="", amount="", reference="", before=None,
            reason=value["reason"], request_key=value["request_key"], settlement=value["settlement"]))
        value["settlement"] = check["settlement"]
    if "predecessor" in value:
        facts = value["predecessor"]
        if not isinstance(facts, dict) or set(facts) != {"cash_received", "cash_paid", "interest_offset", "reference", "confirmed_custody"} or facts["confirmed_custody"] is not True:
            raise ValueError("Confirm the predecessor's renewal date and custody and enter its actual cash after correcting the successor terms.")
        value["predecessor"] = dict(facts, **{name: _amount(facts[name], name) for name in ("cash_received", "cash_paid", "interest_offset")})
        value["predecessor"]["reference"] = _text(facts["reference"], "predecessor settlement source", 255)
    return value


def _lock(loan_id):
    # Acquire the predecessor before its successor, as ordinary renewal does.
    relation = m.PawnLoanRenewal.objects.filter(successor_loan_id=loan_id).first()
    predecessor = _locked_loan(relation.source_loan_id) if relation else None
    loan = _locked_loan(loan_id)
    return relation, predecessor, loan


def _source(loan_id, actor, facts):
    relation, predecessor, loan = _lock(loan_id)
    _authorize(loan, actor)
    events, active, blockers = dependencies(loan)
    if blockers:
        raise ValueError(" ".join(blockers))
    origins = [event for event in active if event.event_kind in ("DISBURSAL", "RENEWAL_OPENING")]
    paired = None
    if relation:
        if not recording_for(predecessor) or origins[0].event_kind != "RENEWAL_OPENING" or not facts.get("predecessor"):
            raise ValueError("A recorded successor requires the supported predecessor contract and explicit paired settlement facts.")
        _authorize(predecessor, actor)
        _, predecessor_active, predecessor_blockers = dependencies(predecessor)
        if predecessor_blockers:
            raise ValueError(" ".join(predecessor_blockers))
        predecessor_terminal = terminal_for(predecessor, predecessor_active)
        if not predecessor_terminal or predecessor_terminal.event_kind != "RENEWAL_SETTLEMENT":
            raise ValueError("The paired predecessor must retain its completed renewal settlement.")
        new_day = date.fromisoformat(facts["date"])
        if new_day < predecessor.loan_date or any(e.effective_date > new_day for e in predecessor_active if e.event_kind == "REPAYMENT"):
            raise ValueError("The corrected renewal cannot precede its predecessor's contract or retained receipts.")
        paired = (predecessor, predecessor_terminal)
    elif origins[0].event_kind != "DISBURSAL" or facts.get("predecessor"):
        raise ValueError("Predecessor settlement facts apply only to a linked recorded successor.")
    terminal = terminal_for(loan, active)
    if terminal and not facts.get("settlement"):
        raise ValueError("Supply the corrected settlement amount and confirm retained settlement/custody facts.")
    if not terminal and facts.get("settlement"):
        raise ValueError("This active loan has no financial settlement to restate.")
    if any(event.effective_date < date.fromisoformat(facts["date"]) for event in active if event is not origins[0]):
        raise ValueError("The corrected original date cannot follow a retained receipt or settlement.")
    lineage, downstream = dependent_state(predecessor or loan, actor=actor)
    return loan, events, active, origins[0], terminal, lineage, downstream, paired


def _run(loan, actor, facts, active, origin, terminal, paired=None):
    before = dict(date=loan.loan_date.isoformat(), principal=str(loan.principal_amount), rate=str(loan.monthly_interest_rate),
        balance=str(collection_balance(loan, timezone.localdate()).total_due))
    original = loan.disbursal_snapshot if origin.event_kind == "DISBURSAL" else None
    economics = origin.payload["renewal"]["successor_economics"] if original is None else {}
    advance_periods = original.advance_interest_periods if original else economics["advance_interest_periods"]
    deducted_fees = original.deducted_fees if original else Decimal(economics["deducted_fees"])
    principal, rate = Decimal(facts["principal"]), Decimal(facts["rate"])
    monthly = (principal * rate / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    advance = monthly * advance_periods
    if principal - advance - deducted_fees != Decimal(facts["cash_paid"]):
        raise ValueError("Corrected proceeds must equal principal less advance interest and the retained deducted document charge.")
    context = dict(schema=PROFILE, operation="CONTRACT", request_key=facts["request_key"], request_sha256=_digest(facts),
        reason=facts["reason"], recorder_id=actor.pk, restated=True)
    for event in sorted(active, key=lambda event: (event.effective_date, event.pk), reverse=True):
        payload = reversal_payload(loan, effective_date=event.effective_date, original_event_id=event.pk,
            original_event_kind=event.event_kind, values=event.payload["values"], reason=facts["reason"]).to_dict()
        payload["history_correction"] = dict(context, role="COMPENSATION", root_event_id=_source_id(event), source_event_id=event.pk)
        if event.event_kind == "RENEWAL_SETTLEMENT":
            payload["renewal"] = deepcopy(event.payload["renewal"])
        reverse, _ = record_loan_event(loan.pk, event_kind="REVERSAL", effective_date=event.effective_date,
            payload=payload, actor=actor, reversal_of=event)
        reverse_event_obligation_allocations(original_event=event, reversal_event=reverse, actor=actor)
        reverse_event_schedule_change(original_event=event, reversal_event=reverse, actor=actor)
    item = loan.collateral_items.select_for_update().get()
    item.allocated_principal, item.monthly_interest_rate = principal, rate
    item.save(update_fields=["allocated_principal", "monthly_interest_rate", "updated_at"])
    loan.loan_date, loan.principal_amount, loan.monthly_interest_rate = date.fromisoformat(facts["date"]), principal, rate
    previous_policy = original.policy_snapshot if original else loan.policy_snapshot
    policy_values = {field.name: getattr(previous_policy, field.name) for field in m.LoanPolicySnapshot._meta.fields
        if field.name not in ("id", "loan", "workspace", "created_at")}
    policy = m.LoanPolicySnapshot.objects.create(workspace_id=loan.workspace_id, loan=loan, **policy_values)
    loan.policy_snapshot = policy
    loan.save(update_fields=["loan_date", "principal_amount", "monthly_interest_rate", "policy_snapshot", "updated_at"])
    recording = deepcopy(origin.payload["recording"])
    recording.update(occurred_on=facts["date"], advance_interest=str(advance),
        contract_correction=dict(context, source_event_id=origin.pk, reference=facts["reference"]))
    recording["terms"].update(principal_amount=str(principal), monthly_interest_rate=str(rate))
    recording["terms"]["collateral"][0]["monthly_interest_rate"] = str(rate)
    if recording.get("funding"):
        recording["funding"].update(proceeds_after_deductions=facts["cash_paid"],
            actual_cash_paid=facts["cash_paid"] if recording["funding"]["basis"] == "CASH" else None)
    tranches = [dict(collateral_item_id=item.pk, allocated_principal=str(principal), monthly_interest_rate=str(rate),
        monthly_interest=str(monthly), advance_interest=str(advance))]
    if original:
        payload = disbursal_payload(loan, effective_date=loan.loan_date, principal_amount=principal,
            net_cash_amount=Decimal(facts["cash_paid"]), advance_interest_amount=advance, deducted_fee_amount=deducted_fees).to_dict()
        detail = deepcopy(origin.payload["disbursal"])
        detail.update(policy_snapshot_id=policy.pk, monthly_interest=str(monthly), tranches=tranches)
        payload["disbursal"] = detail
    else:
        from apps.tenant_apps.loans.integrations import renewal_opening_payload
        predecessor, settlement = paired
        from .recorded_settlement_facts import compensate_collections, replay_collections, restate_custody_date
        _, predecessor_active, _ = dependencies(predecessor)
        compensate_collections(predecessor, predecessor_active, actor=actor, context=context)
        replay_collections(predecessor, predecessor_active, actor=actor, context=context, through=loan.loan_date)
        custody = restate_custody_date(settlement, day=loan.loan_date, actor=actor)
        paired_review = restate_settlement(predecessor, settlement, actor=actor,
            facts=dict(facts["predecessor"], date=facts["date"]), context=context,
            successor_terms=dict(principal=principal, advance=advance, fees=deducted_fees), custody_restatement=custody)
        from apps.tenant_apps.loans.selectors.recorded_settlements import current_settlement
        replacement_settlement = current_settlement(settlement)
        recording["cash_evidence"] = deepcopy(replacement_settlement.payload["renewal"]["cash_evidence"])
        payload = renewal_opening_payload(loan, effective_date=loan.loan_date, principal_amount=principal,
            capitalized_interest_principal_amount=0).to_dict()
        detail = deepcopy(origin.payload["renewal"])
        detail["settlement_event_id"] = replacement_settlement.pk
        detail["successor_economics"].update(policy_snapshot_id=policy.pk, monthly_interest=str(monthly),
            advance_interest=str(advance), tranches=tranches)
        payload["renewal"] = detail
    payload.update(recording=recording, recorded_admission=origin.payload["recorded_admission"],
        history_correction=dict(context, role="CONTRACT", root_event_id=_source_id(origin), source_event_id=origin.pk))
    replacement, _ = record_loan_event(loan.pk, event_kind=origin.event_kind, effective_date=loan.loan_date, payload=payload, actor=actor)
    if original:
        snapshot = m.PawnLoanDisbursalSnapshot.objects.create(workspace_id=loan.workspace_id, loan=loan, basis="RECORDED",
            policy_snapshot=policy, loan_event=replacement, gross_principal=principal, monthly_interest=monthly,
            advance_interest_periods=advance_periods, advance_interest=advance,
            deducted_fees=deducted_fees, net_disbursed=Decimal(facts["cash_paid"]), created_by=actor,
            evidence=dict(recording=recording, tranches=tranches, fees=deepcopy(original.evidence["fees"])))
        loan.disbursal_snapshot = snapshot
        loan.save(update_fields=["disbursal_snapshot", "updated_at"])
    else:
        m.PawnLoanPrincipalOpeningLine.objects.create(loan_event=replacement, collateral_item=item,
            predecessor_collateral_item_id=item.renewed_from_id, allocation_order=1, monthly_interest_rate=rate, principal_opened=principal)
    persist_disbursal_repayment_schedule(loan, source_event=replacement, disbursed_on=loan.loan_date, actor=actor)
    rows = [paired_review] if paired else []
    for index, source in enumerate(active):
        key = f"contract-correction:{facts['request_key']}:{index}"
        meta = dict(context, role="REPLAY", root_event_id=_source_id(source), source_event_id=source.pk)
        if source.event_kind == "REPAYMENT":
            receipt = receipt_facts(source)
            result = _record_pawn_loan_repayment_at(loan.pk, amount=receipt["amount"], request_key=key, actor=actor,
                effective_date=source.effective_date, recording_evidence=source.payload["repayment"].get("recording"),
                correction_evidence=meta, replay_closed=terminal is not None)
            rows.append(dict(receipt, principal=str(result.allocation.principal), interest=str(result.allocation.interest)))
        elif source.event_kind == "INTEREST_ACCRUAL":
            recognize_collection_interest(loan, source.effective_date, actor=actor, request_key=key, correction_evidence=meta)
    if terminal:
        rows.append(restate_settlement(loan, terminal, actor=actor, facts=facts["settlement"], context=context))
    after = dict(date=loan.loan_date.isoformat(), principal=str(principal), rate=str(rate),
        balance=str(collection_balance(loan, timezone.localdate()).total_due))
    review = dict(before=before, after=after, rows=rows, proceeds=facts["cash_paid"], advance_interest=str(advance),
        reason=facts["reason"], reference=facts["reference"])
    m.LoanChangeLog.objects.create(workspace_id=loan.workspace_id, loan=loan, event_kind="REVERSAL_RECORDED",
        from_state=loan.state, to_state=loan.state, actor=actor, reason=facts["reason"], metadata=dict(history_correction=context, review=review))
    return review


@transaction.atomic
def preview_contract_correction(loan_id, *, actor, data):
    facts = _facts(data)
    loan, events, active, origin, terminal, lineage, downstream, paired = _source(loan_id, actor, facts)
    with transaction.atomic():
        review = _run(loan, actor, facts, active, origin, terminal, paired)
        transaction.set_rollback(True)
    review["downstream"] = downstream
    return review, signing.dumps(dict(loan=loan.pk, workspace=loan.workspace_id, actor=actor.pk, facts=_digest(facts),
        lineage=lineage, review=review), salt=SALT, compress=True)


@transaction.atomic
def record_contract_correction(loan_id, *, actor, data, review_token, confirmed=False):
    facts = _facts(data)
    _, _, loan = _lock(loan_id)
    _authorize(loan, actor)
    existing = loan.change_log.filter(metadata__history_correction__operation="CONTRACT",
        metadata__history_correction__request_key=facts["request_key"]).first()
    if existing:
        if existing.metadata["history_correction"]["request_sha256"] != _digest(facts) or existing.actor_id != actor.pk:
            raise ValueError("This correction request already records different contract facts.")
        return existing, False
    if confirmed is not True:
        raise ValueError("Confirm the complete contract correction review.")
    loan, events, active, origin, terminal, lineage, downstream, paired = _source(loan_id, actor, facts)
    try:
        signed = signing.loads(review_token or "", salt=SALT, max_age=3600)
    except signing.BadSignature as exc:
        raise ValueError("Preview this contract correction again.") from exc
    if (signed.get("loan"), signed.get("workspace"), signed.get("actor"), signed.get("facts"), signed.get("lineage")) != (
            loan.pk, loan.workspace_id, actor.pk, _digest(facts), lineage):
        raise ValueError("Loan or dependent facts changed. Preview this correction again.")
    review = _run(loan, actor, facts, active, origin, terminal, paired)
    review["downstream"] = downstream
    if _digest(review) != _digest(signed["review"]):
        raise ValueError("The correction calculation changed. Preview again.")
    return loan.change_log.filter(metadata__history_correction__request_key=facts["request_key"]).latest("pk"), True
