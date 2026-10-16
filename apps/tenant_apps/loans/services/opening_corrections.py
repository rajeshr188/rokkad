"""Explicit checkpoint restatement; never reconstruct unavailable earlier cash."""
from copy import deepcopy
from datetime import date
from decimal import Decimal, ROUND_HALF_EVEN
from types import SimpleNamespace

from django.core import signing
from django.db import transaction
from django.utils import timezone

from apps.tenant_apps.loans import models as m
from .agreement_corrections import PROFILE, locked_agreement, correction_state, balance_facts
from .recorded_history import _digest, _text
from .opening_validation import validate_opening

SALT = "loans.opening-correction.v1"


def effective_opening(loan, origin):
    """An explicit compensation changes the checkpoint, never its source event."""
    if not getattr(origin, "pk", None) or not hasattr(loan, "loan_events"):
        return origin
    corrections = list(loan.loan_events.filter(event_kind="OPENING_CORRECTION").order_by("pk"))
    previous, opening = origin, origin.payload["opening"]
    for revision, event in enumerate(corrections, 1):
        evidence = event.payload.get("agreement_correction", {})
        if (event.workspace_id != loan.workspace_id or event.loan_id != loan.pk
                or event.effective_date != origin.effective_date or not event.created_by_id
                or evidence.get("schema") != PROFILE or evidence.get("operation") != "CHECKPOINT"
                or evidence.get("revision") != revision or evidence.get("original_event_id") != origin.pk
                or evidence.get("source_event_id") != previous.pk
                or evidence.get("before_sha256") != _digest(opening)
                or evidence.get("before_values") != {k: opening["review"]["balances"][k] for k in ("principal", "interest", "fees")}
                or event.payload.get("opening", {}).get("item_mapping") != opening["item_mapping"]):
            raise ValueError("Opening correction chain does not reconcile to its retained checkpoint.")
        opening = event.payload["opening"]
        _validate_change(previous.payload["opening"]["review"], opening["review"])
        if event.payload.get("values") != {k: opening["review"]["balances"][k] for k in ("principal", "interest", "fees")}:
            raise ValueError("Corrected opening values differ from its reviewed checkpoint.")
        previous = event
    if not corrections:
        return origin
    payload = deepcopy(previous.payload)
    payload["event_kind"] = "MIGRATION_OPENING"
    return SimpleNamespace(pk=origin.pk, loan_id=origin.loan_id, workspace_id=origin.workspace_id,
        effective_date=origin.effective_date, payload=payload, correction_event_id=previous.pk)


def opening_schedule_source(loan, origin):
    current = effective_opening(loan, origin)
    return getattr(current, "correction_event_id", origin.pk)


def _facts(data):
    if not isinstance(data, dict) or set(data) != {"checkpoint", "reference", "reason", "request_key"}:
        raise ValueError("Review the original agreement, checkpoint balances, period bases and remaining obligations explicitly.")
    if not isinstance(data["checkpoint"], dict):
        raise ValueError("Supply the complete reviewed checkpoint.")
    return dict(checkpoint=deepcopy(data["checkpoint"]), reference=_text(data["reference"], "the supporting source", 160),
        reason=_text(data["reason"], "the correction reason", 500), request_key=_text(data["request_key"], "the correction request", 80))


def _validate_change(before, after):
    if after.get("profile") not in {"loan-opening-review/4", "loan-opening-review/5"} or before.get("profile") != after.get("profile"):
        raise ValueError("Checkpoint correction requires its retained shared monthly opening profile.")
    result = validate_opening(after)
    if not result["document_reconciled"]:
        raise ValueError("Corrected checkpoint does not reconcile: " + "; ".join(r["message"] for r in result["issues"][:8]))
    unchanged = deepcopy(after)
    for group in ("balances", "continuation", "obligations"):
        unchanged[group] = before[group]
    if len(after["collateral"]) != len(before["collateral"]):
        raise ValueError("A financial correction cannot add or remove collateral items.")
    by_id = {r["id"]: r for r in before["collateral"]}
    for row in unchanged["collateral"]:
        if row["id"] not in by_id:
            raise ValueError("A financial correction must retain the original item identities.")
        for name in ("original_principal", "remaining_principal", "monthly_rate"):
            row[name] = by_id[row["id"]][name]
    if unchanged != before:
        raise ValueError("This correction preserves original dates, source identities, physical facts and the frozen economic rule.")


def _source(loan, facts):
    events = list(loan.loan_events.order_by("pk"))
    origins = [e for e in events if e.event_kind == "MIGRATION_OPENING"]
    if loan.state != "ACTIVE" or len(origins) != 1 or any(e.event_kind not in {"MIGRATION_OPENING", "OPENING_CORRECTION"} for e in events):
        raise ValueError("A serviced or settled checkpoint requires connected reconciliation before its baseline can change.")
    if (loan.auctions.exists() or m.PawnLoanRenewal.objects.filter(source_loan=loan).exists()
            or m.FundingPledgeItem.objects.filter(collateral_item__loan=loan).exists()
            or m.FundingLoanDraftCollateral.objects.filter(collateral_item__loan=loan).exists()
            or loan.collateral_items.exclude(custody_state="IN_VAULT").exists()):
        raise ValueError("Connected custody, renewal, funding or auction evidence requires reconciliation.")
    origin = origins[0]
    from .opening_evidence import read_opening_evidence
    opening = read_opening_evidence(loan, origin)
    source_items = {opening["item_mapping"][r["id"]]: r for r in opening["review"]["collateral"]}
    items = list(loan.collateral_items.select_for_update().order_by("pk"))
    if (loan.principal_amount != Decimal(opening["review"]["balances"]["principal"])
            or set(source_items) != {i.pk for i in items}
            or any(i.allocated_principal != Decimal(source_items[i.pk]["remaining_principal"])
                or i.monthly_interest_rate != Decimal(source_items[i.pk]["monthly_rate"]) for i in items)):
        raise ValueError("Current opening facts do not match their retained financial source. Reconcile that evidence first.")
    _validate_change(opening["review"], facts["checkpoint"])
    if _financial_facts(opening["review"]) == _financial_facts(facts["checkpoint"]):
        raise ValueError("No checkpoint facts have changed.")
    return origin, opening, events[-1]


def _financial_facts(review):
    carry = review["continuation"]
    return dict(items=[(r["id"], *(Decimal(r[k]) for k in ("original_principal", "remaining_principal", "monthly_rate"))) for r in review["collateral"]],
        balances=[Decimal(review["balances"][k]) for k in ("principal", "interest", "fees")],
        bases=[(r["item_id"], Decimal(r["principal_base"])) for r in carry["bases"]],
        interest=[Decimal(carry[k]) for k in ("recognized_interest", "recognized_unpaid_interest", "current_period_recognized_interest", "current_period_unpaid_interest")],
        advances=[(r["period_number"], Decimal(r["interest"])) for r in carry["advance_coverage"]],
        obligations=[(r["id"], r["due"], *(Decimal(r[k]) for k in ("principal", "interest", "recognized_interest"))) for r in review["obligations"]])


def _run(loan, actor, facts, origin, opening, previous):
    from .event_recording import _persist_locked_event
    from .opening_obligations import persist_opening_repayment_schedule
    before = dict(position=balance_facts(loan), original_principal=str(sum(
        Decimal(r["original_principal"]) for r in opening["review"]["collateral"])))
    corrected = deepcopy(opening)
    corrected["review"] = facts["checkpoint"]
    values = {k: facts["checkpoint"]["balances"][k] for k in ("principal", "interest", "fees")}
    evidence = dict(schema=PROFILE, operation="CHECKPOINT", role="CHECKPOINT", revision=loan.loan_events.filter(event_kind="OPENING_CORRECTION").count() + 1,
        original_event_id=origin.pk, source_event_id=previous.pk, before_sha256=_digest(opening),
        before_values={k: opening["review"]["balances"][k] for k in values}, request_key=facts["request_key"], request_sha256=_digest(facts),
        reference=facts["reference"], reason=facts["reason"])
    payload = dict(contract_version=1, event_kind="OPENING_CORRECTION", effective_date=origin.effective_date.isoformat(), currency="INR",
        source_identity=dict(app="loans", model="PawnLoan", loan_id=loan.pk), values=values, opening=corrected, agreement_correction=evidence)
    event, _ = _persist_locked_event(loan, kind="OPENING_CORRECTION", effective_date=origin.effective_date, payload=payload, actor=actor)
    principal = Decimal(values["principal"])
    monthly = sum(Decimal(r["remaining_principal"]) * Decimal(r["monthly_rate"]) / 100 for r in corrected["review"]["collateral"])
    loan.principal_amount = principal
    loan.monthly_interest_rate = (monthly / principal * 100).quantize(Decimal(".000001"), rounding=ROUND_HALF_EVEN)
    loan.save(update_fields=["principal_amount", "monthly_interest_rate", "updated_at"])
    for row in corrected["review"]["collateral"]:
        m.PawnCollateralItem.objects.filter(pk=corrected["item_mapping"][row["id"]], loan=loan).update(
            allocated_principal=Decimal(row["remaining_principal"]), monthly_interest_rate=Decimal(row["monthly_rate"]))
    persist_opening_repayment_schedule(loan.pk, actor=actor, correction_event=event)
    return dict(before=before, after=dict(position=balance_facts(loan), original_principal=str(sum(
        Decimal(r["original_principal"]) for r in corrected["review"]["collateral"]))),
        history_basis="VERIFIED_CHECKPOINT", cutover=origin.effective_date.isoformat(), reference=facts["reference"], reason=facts["reason"])


@transaction.atomic
def preview_opening_correction(loan_id, *, actor, data):
    facts = _facts(data)
    loan = locked_agreement(loan_id, actor)
    origin, opening, previous = _source(loan, facts)
    source = correction_state(loan)
    with transaction.atomic():
        review = _run(loan, actor, facts, origin, opening, previous)
        transaction.set_rollback(True)
    return review, signing.dumps(dict(loan=loan.pk, workspace=loan.workspace_id, actor=actor.pk,
        facts=_digest(facts), source=source, review=review), salt=SALT, compress=True)


@transaction.atomic
def record_opening_correction(loan_id, *, actor, data, review_token, confirmed=False):
    facts = _facts(data)
    loan = locked_agreement(loan_id, actor)
    if confirmed is not True:
        raise ValueError("Confirm the complete checkpoint correction review.")
    existing = loan.change_log.filter(metadata__agreement_correction__request_key=facts["request_key"]).first()
    if existing:
        if existing.actor_id != actor.pk or existing.metadata["agreement_correction"]["request_sha256"] != _digest(facts):
            raise ValueError("This correction request already records different checkpoint facts.")
        return existing, False
    origin, opening, previous = _source(loan, facts)
    try:
        signed = signing.loads(review_token or "", salt=SALT, max_age=3600)
    except signing.BadSignature:
        raise ValueError("Preview this checkpoint correction again.") from None
    if (signed.get("loan"), signed.get("workspace"), signed.get("actor"), signed.get("facts"), signed.get("source")) != (
            loan.pk, loan.workspace_id, actor.pk, _digest(facts), correction_state(loan)):
        raise ValueError("Loan or dependent facts changed. Preview this checkpoint correction again.")
    review = _run(loan, actor, facts, origin, opening, previous)
    if _digest(review) != _digest(signed.get("review")):
        raise ValueError("Checkpoint correction calculation changed. Preview again.")
    log = m.LoanChangeLog.objects.create(workspace_id=loan.workspace_id, loan=loan, event_kind="REVERSAL_RECORDED",
        from_state=loan.state, to_state=loan.state, actor=actor, reason=facts["reason"],
        metadata=dict(agreement_correction=dict(schema=PROFILE, operation="CHECKPOINT", request_key=facts["request_key"],
            request_sha256=_digest(facts), review=review)))
    loan.updated_by = actor
    loan.save(update_fields=["updated_by", "updated_at"])
    m.LoanRiskSnapshot.objects.filter(loan=loan).exclude(status="ERROR").update(status="STALE", error_message="Checkpoint corrected; reassessment required.")
    return log, True
