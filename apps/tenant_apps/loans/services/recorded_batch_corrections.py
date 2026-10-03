"""Atomically reconcile receipt corrections with a retained release batch."""
from decimal import Decimal

from django.core import signing
from django.db import transaction
from django.utils import timezone

from apps.tenancy.context import current_workspace_id
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.access import LOANS_ADMIN_ACTION
from apps.tenant_apps.loans.selectors.balances import get_pawn_loan_balance
from apps.tenant_apps.loans.selectors.recorded_settlements import restated_release
from .action_access import require_workspace_action
from .recorded_history import _amount, _digest, _text
from .recorded_corrections import correction_input, dependencies, _authorize, _run
from .recorded_collections import recording_for, collection_balance
from .recorded_settlement_corrections import dependent_state
from .paper_closures import MAX_PAPER_LOANS

PROFILE = "recorded-batch-correction/1"
SALT = "loans.recorded-batch-correction.review.v1"


def batch_input(data):
    fields = {"total_received", "reference", "reason", "request_key", "confirmed_unchanged", "loans"}
    if not isinstance(data, dict) or set(data) != fields:
        raise ValueError("Review the complete batch and its actual collection total.")
    if data["confirmed_unchanged"] is not True:
        raise ValueError("Confirm the batch membership, dates, payer and collateral handovers remain correct.")
    value = dict(data, total_received=_amount(data["total_received"], "actual batch collection"),
        reference=_text(data["reference"], "the checked batch source", 255),
        reason=_text(data["reason"], "the correction reason", 500),
        request_key=_text(data["request_key"], "the batch correction request reference", 40))
    rows = value["loans"]
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_PAPER_LOANS:
        raise ValueError(f"A batch correction requires 1–{MAX_PAPER_LOANS} loans.")
    cleaned, ids = [], set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"loan_id", "correction"}:
            raise ValueError("Every batch loan needs an explicit changed or unchanged selection.")
        pk = row["loan_id"]
        if type(pk) is not int or pk <= 0 or pk in ids:
            raise ValueError("Select each batch loan exactly once.")
        ids.add(pk)
        change = row["correction"]
        if change is not None:
            if not isinstance(change, dict):
                raise ValueError("Supply valid receipt correction facts.")
            change = correction_input(dict(change, reason=value["reason"], request_key=f"batch:{value['request_key']}:{pk}"))
            if "settlement" not in change or Decimal(change["settlement"]["cash_paid"]) or Decimal(change["settlement"]["interest_offset"]):
                raise ValueError("A batch full release requires actual cash received, with zero payout and interest offset.")
        cleaned.append(dict(loan_id=pk, correction=change))
    if not any(row["correction"] for row in cleaned):
        raise ValueError("Select at least one loan receipt to correct.")
    value["loans"] = sorted(cleaned, key=lambda row: row["loan_id"])
    return value


def _locked_batch(batch_id, actor):
    workspace_id = current_workspace_id()
    try:
        batch = m.PawnReleaseBatch.objects.select_for_update().get(pk=batch_id, workspace_id=workspace_id)
    except m.PawnReleaseBatch.DoesNotExist:
        raise ValueError("Release batch was not found in the active workspace.") from None
    require_workspace_action(batch.workspace, actor, LOANS_ADMIN_ACTION, "loan.release", "loan.repay", "loan.accrue")
    return batch


def _snapshot(batch, actor, data):
    lines = list(batch.lines.select_related("release__loan", "release__loan_event", "release__reversal").order_by("release__loan_id"))
    ids = [line.release.loan_id for line in lines]
    if ids != [row["loan_id"] for row in data["loans"]]:
        raise ValueError("Batch membership changed or a loan was omitted. Review every included loan.")
    loans = list(m.PawnLoan.objects.select_for_update().filter(workspace_id=batch.workspace_id, pk__in=ids).order_by("pk"))
    if len(loans) != len(ids):
        raise ValueError("A batch loan is unavailable in this workspace.")
    changes = {row["loan_id"]: row["correction"] for row in data["loans"]}
    states, sources, before = [], [], []
    for loan, line in zip(loans, lines):
        release = restated_release(line.release)
        if loan.state != "CLOSED" or hasattr(line.release, "reversal") or not release.is_full_release:
            raise ValueError(f"Loan {loan.loan_number}: reversed or incomplete releases require separate reconciliation.")
        if release.effective_date != batch.effective_date:
            raise ValueError("Release dates do not match the retained batch.")
        _authorize(loan, actor)
        events = list(loan.loan_events.order_by("pk")[:1001])
        if len(events) > 1000:
            raise ValueError("Batch loan history exceeds the supported 1,000-event review limit.")
        items = list(loan.collateral_items.select_for_update().order_by("pk"))
        if not items or any(item.custody_state != "WITH_CUSTOMER" for item in items):
            raise ValueError(f"Loan {loan.loan_number}: collateral handover is no longer unchanged.")
        balance = collection_balance(loan, timezone.localdate()) if recording_for(loan) else get_pawn_loan_balance(loan, as_of_date=timezone.localdate())
        if balance.total_due:
            raise ValueError(f"Loan {loan.loan_number}: the retained release no longer reconciles to zero.")
        states.append(dict(loan=loan.pk, state=loan.state, policy=loan.policy_snapshot_id,
            principal=str(loan.principal_amount), rate=str(loan.monthly_interest_rate), date=loan.loan_date.isoformat(), tenure=loan.tenure_months,
            events=[[e.pk, e.payload_fingerprint] for e in events],
            items=[[i.pk, i.custody_state] for i in items],
            custody=list(m.PawnCollateralCustodyEvent.objects.filter(collateral_item__loan=loan).order_by("pk").values_list("pk", flat=True))))
        change = changes[loan.pk]
        if change is not None:
            all_events, active, blockers = dependencies(loan, batch_id=batch.pk)
            if blockers:
                raise ValueError(f"Loan {loan.loan_number}: " + " ".join(blockers))
            # A full-release batch has no outgoing renewal. This also validates
            # the supported contract/custody evidence under the existing command.
            lineage, _ = dependent_state(loan, actor=actor, batch_id=batch.pk)
            if len(lineage) != 1:
                raise ValueError("A released batch member cannot have a successor renewal.")
            sources.append((loan, change, all_events, active))
        before.append(dict(loan=loan.pk, number=loan.loan_number, release=line.release_id,
            amount=str(release.settlement_amount), changed=change is not None,
            collector=line.collector_name))
    return states, sources, before


def _run_batch(batch, actor, data, sources, before):
    context = dict(schema=PROFILE, id=batch.pk, request_key=data["request_key"], request_sha256=_digest(data),
        total_received=data["total_received"], reference=data["reference"],
        before_total=str(sum((Decimal(row["amount"]) for row in before), Decimal("0"))),
        loan_ids=[row["loan_id"] for row in data["loans"]],
        corrected_loan_ids=[loan.pk for loan, *_ in sources])
    corrections = []
    for loan, change, events, active in sources:
        review = _run(loan, actor, change, events, active, batch_context=context)
        corrections.append(dict(loan=loan.pk, number=loan.loan_number, review=review))
    final = {loan.pk: change["settlement"]["cash_received"] for loan, change, *_ in sources}
    rows = [dict(row, after=final.get(row["loan"], row["amount"])) for row in before]
    calculated = sum((Decimal(row["after"]) for row in rows), Decimal("0"))
    if calculated != Decimal(data["total_received"]):
        raise ValueError(f"Combined collection does not reconcile: actual {data['total_received']}, "
                         f"sum of individual settlements {calculated}. Check every receipt; no balancing payment is inferred.")
    return dict(rows=rows, corrections=corrections, total=str(calculated), before_total=context["before_total"],
        original_total=str(batch.total_amount), reference=data["reference"], reason=data["reason"])


@transaction.atomic
def preview_batch_correction(batch_id, *, actor, data):
    data = batch_input(data)
    batch = _locked_batch(batch_id, actor)
    state, sources, before = _snapshot(batch, actor, data)
    with transaction.atomic():
        review = _run_batch(batch, actor, data, sources, before)
        transaction.set_rollback(True)
    token = signing.dumps(dict(workspace=batch.workspace_id, batch=batch.pk, actor=actor.pk,
        date=timezone.localdate().isoformat(), data=_digest(data), state=state, review=review), salt=SALT, compress=True)
    return review, token


@transaction.atomic
def record_batch_correction(batch_id, *, actor, data, review_token, confirmed=False):
    data = batch_input(data)
    batch = _locked_batch(batch_id, actor)
    if confirmed is not True:
        raise ValueError("Confirm the complete batch correction review.")
    existing = m.PawnLoanEvent.objects.filter(workspace_id=batch.workspace_id,
        payload__history_correction__batch_correction__id=batch.pk,
        payload__history_correction__batch_correction__request_key=data["request_key"]).first()
    if existing:
        if existing.payload["history_correction"]["batch_correction"]["request_sha256"] != _digest(data):
            raise ValueError("This batch correction request already records different facts.")
        return False
    state, sources, before = _snapshot(batch, actor, data)
    try:
        signed = signing.loads(review_token or "", salt=SALT, max_age=3600)
    except (signing.BadSignature, TypeError, ValueError):
        raise ValueError("Preview the batch correction again; its review is missing or expired.") from None
    if (signed.get("workspace"), signed.get("batch"), signed.get("actor"), signed.get("date"), signed.get("data"), signed.get("state")) != (
            batch.workspace_id, batch.pk, actor.pk, timezone.localdate().isoformat(), _digest(data), state):
        raise ValueError("The batch, a member loan or recording context changed. Preview again.")
    review = _run_batch(batch, actor, data, sources, before)
    if review != signed.get("review"):
        raise ValueError("Calculated batch results changed. Preview again.")
    return True
