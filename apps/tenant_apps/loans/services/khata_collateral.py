"""Reviewed collateral reservations and actual physical handover."""
from decimal import Decimal, ROUND_DOWN

from django.db.models import Max
from django.utils import timezone

from apps.tenant_apps.loans.models import KhataCollateralSelection, KhataOperation, KhataPolicyRevision
from apps.tenant_apps.loans.selectors.khata import eligible_items, held_items, account_position, effective_agreement, account_balances
from apps.tenant_apps.loans.selectors.origination_rates import get_origination_quote_rows, require_fresh_quotes
from .action_access import require_workspace_action
from .khata_accounts import KhataDraftError, _hash, _key, _today
from .khata_opening import _locked, _operation, _retry, _photo_evidence, _save_valuations
from .khata_servicing import _active
from .origination_settings import collateral_photos_required


def _ids(values):
    try:
        result = [int(v) for v in values]
    except (ValueError, TypeError) as exc:
        raise KhataDraftError("Select valid collateral items.") from exc
    if len(result) != len(set(result)) or any(v <= 0 for v in result):
        raise KhataDraftError("Select each collateral item once.")
    return sorted(result)


def _values(account, workspace, day, items):
    rows = get_origination_quote_rows(workspace_id=workspace.pk, loan_date=day, metals=[i.metal for i in items]) if items else []
    require_fresh_quotes(rows)
    prices = {r["metal"]: r for r in rows}
    required = collateral_photos_required(workspace.pk)
    return [dict(item_id=i.pk, rate_id=prices[i.metal]["rate"].pk,
        value=str((prices[i.metal]["rate"].buying_rate*i.net_weight*i.purity/100).quantize(Decimal("0.01"), rounding=ROUND_DOWN)),
        rate_evidence=prices[i.metal]["evidence"], photo=_photo_evidence(i, required)) for i in items]


def _selected(items, ids):
    result = [i for i in items if i.pk in ids]
    if len(result) != len(ids):
        raise KhataDraftError("Selected collateral is foreign, returned or reserved for another operation.")
    return result


def _reserve(op, outgoing, incoming=()):
    for role, ids in (("OUT", outgoing), ("IN", incoming)):
        for item_id in ids:
            KhataCollateralSelection.objects.create(workspace_id=op.workspace_id, operation=op, item_id=item_id, role=role)


def _exchange_review(account, workspace, actor, day, outgoing, incoming):
    _active(account, day)
    if not outgoing or not incoming or set(outgoing) & set(incoming):
        raise KhataDraftError("Choose distinct outgoing and replacement collateral items.")
    items = list(eligible_items(account))
    outs, ins = _selected(items, outgoing), _selected(items, incoming)
    if KhataCollateralSelection.objects.filter(item_id__in=incoming, role="IN", operation__corrected_by__isnull=True).exists():
        raise KhataDraftError("Replacement collateral was already used in an exchange.")
    if {i.metal for i in outs} != {i.metal for i in ins}:
        raise KhataDraftError("Replacement must use the same metals; one metal cannot replace another.")
    values = _values(account, workspace, day, items)
    amounts = {v["item_id"]: Decimal(v["value"]) for v in values}
    shortfalls = {metal: str(max(Decimal(0), sum((amounts[i.pk] for i in outs if i.metal == metal), Decimal(0))
        - sum((amounts[i.pk] for i in ins if i.metal == metal), Decimal(0)))) for metal in sorted({i.metal for i in outs})}
    position, terms = account_position(account), effective_agreement(account)
    retained = sum((amounts[i.pk] for i in items if i.pk not in outgoing), Decimal(0))
    backing = (retained*terms.ltv).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    policy = KhataPolicyRevision.objects.filter(workspace=workspace).order_by("-number").first()
    exchange_policy, overdue_policy = (policy.exchange, policy.overdue) if policy else ("WARN", "WARN")
    overdue = account_balances(workspace=workspace, actor=actor, account_id=account.pk)["overdue_interest"]
    warnings = []
    if any(Decimal(v) > 0 for v in shortfalls.values()) or backing < position.principal:
        if exchange_policy == "BLOCK":
            raise KhataDraftError("Workspace policy blocks exchange value or account-LTV shortfalls.")
        warnings.append("Exchange replacement value or account coverage falls short.")
    if overdue:
        if overdue_policy == "BLOCK":
            raise KhataDraftError("Workspace policy blocks exchanges while interest is overdue.")
        warnings.append("Interest is overdue.")
    return terms, dict(schema="khata-custody/1", account_id=account.pk, date=day.isoformat(),
        last_sequence=account.operations.aggregate(last=Max("sequence"))["last"], outgoing_ids=outgoing, incoming_ids=incoming,
        valuations=values, shortfalls=shortfalls, retained_value=str(retained), backing=str(backing),
        principal=str(position.principal), policy_id=policy.pk if policy else None,
        exchange_policy=exchange_policy, overdue_policy=overdue_policy, overdue_interest=str(overdue), warnings=warnings,
        groups=[dict(metal=metal.title(), outgoing_count=sum(i.metal == metal for i in outs),
            incoming_count=sum(i.metal == metal for i in ins),
            outgoing_net=str(sum((i.net_weight for i in outs if i.metal == metal), Decimal(0))),
            incoming_net=str(sum((i.net_weight for i in ins if i.metal == metal), Decimal(0))),
            outgoing_value=str(sum((amounts[i.pk] for i in outs if i.metal == metal), Decimal(0))),
            incoming_value=str(sum((amounts[i.pk] for i in ins if i.metal == metal), Decimal(0))))
            for metal in sorted({i.metal for i in outs})])


def preview_exchange(*, workspace, actor, account_id, outgoing_ids, incoming_ids):
    outgoing, incoming = _ids(outgoing_ids), _ids(incoming_ids)
    with _locked(workspace, actor, account_id, "data.view") as account:
        _, snapshot = _exchange_review(account, workspace, actor, timezone.localdate(), outgoing, incoming)
        return {"snapshot": snapshot, "review_hash": _hash(snapshot)}


def record_exchange(*, workspace, actor, account_id, outgoing_ids, incoming_ids, request_key, business_date, review_hash, reason):
    outgoing, incoming = _ids(outgoing_ids), _ids(incoming_ids)
    if not reason.strip():
        raise KhataDraftError("Record the collateral exchange reason.")
    key = _key(request_key)
    fingerprint = _hash(dict(kind="EXCHANGE", actor=actor.pk, date=business_date, outgoing=outgoing, incoming=incoming,
        review=review_hash, reason=reason.strip()))
    with _locked(workspace, actor, account_id, "loan.release") as account:
        require_workspace_action(workspace, actor, "data.edit")
        if op := _retry(account, key, fingerprint):
            return op
        terms, snapshot = _exchange_review(account, workspace, actor, business_date, outgoing, incoming)
        if _hash(snapshot) != review_hash:
            raise KhataDraftError("Khata changed after review; refresh before exchange.")
        snapshot["reason"] = reason.strip()
        op = _operation(account, actor, key, fingerprint, "EXCHANGE", business_date, snapshot,
            agreement=terms, policy_id=snapshot["policy_id"])
        _save_valuations(op, snapshot)
        _reserve(op, outgoing, incoming)
        return op


def reduction_snapshot(account, workspace, actor, day, outgoing, principal, ltv):
    items = list(eligible_items(account))
    _selected(items, outgoing)
    balances = account_balances(workspace=workspace, actor=actor, account_id=account.pk)
    if balances["due_interest"]:
        raise KhataDraftError("Clear all due interest before a reduction return.")
    values = _values(account, workspace, day, items)
    retained = sum((Decimal(v["value"]) for v in values if v["item_id"] not in outgoing), Decimal(0))
    backing = (retained*ltv).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    if backing < principal:
        raise KhataDraftError("Retained collateral does not meet the agreed LTV after repayment.")
    return dict(outgoing_ids=outgoing, valuations=values, retained_value=str(retained), backing=str(backing), due_interest="0.00")


def _handover_review(account, workspace, actor, item_id, parent_id, day):
    _today(day)
    item = held_items(account).filter(pk=item_id).first()
    source = KhataOperation.objects.filter(workspace=workspace, account=account, pk=parent_id, corrected_by__isnull=True).first()
    if not item or not source or not source.collateral_selections.filter(item=item, role="OUT").exists():
        raise KhataDraftError("This item has no matching pending return reservation.")
    snapshot = dict(schema="khata-custody/1", account_id=account.pk, date=day.isoformat(), item_id=item_id,
        parent_id=parent_id, last_sequence=account.operations.aggregate(last=Max("sequence"))["last"],
        storage_reference=item.storage_reference)
    if source.kind in ("REVISE", "CORRECT") and account.state == "ACTIVE":
        position, terms = account_position(account), effective_agreement(account)
        snapshot.update(reduction_snapshot(account, workspace, actor, day, [], position.principal, terms.ltv))
    return item, source, snapshot


def preview_handover(*, workspace, actor, account_id, item_id, parent_id):
    with _locked(workspace, actor, account_id, "data.view") as account:
        _, _, snapshot = _handover_review(account, workspace, actor, item_id, parent_id, timezone.localdate())
        return {"snapshot": snapshot, "review_hash": _hash(snapshot)}


def record_handover(*, workspace, actor, account_id, item_id, parent_id, business_date, request_key, review_hash, recipient, reference):
    if not recipient.strip() or not reference.strip():
        raise KhataDraftError("Record the actual recipient and handover reference.")
    key = _key(request_key)
    fingerprint = _hash(dict(kind="HANDOVER", actor=actor.pk, date=business_date, item=item_id, parent=parent_id,
        review=review_hash, recipient=recipient.strip(), reference=reference.strip()))
    with _locked(workspace, actor, account_id, "loan.release") as account:
        if op := _retry(account, key, fingerprint):
            return op
        item, parent, snapshot = _handover_review(account, workspace, actor, item_id, parent_id, business_date)
        if _hash(snapshot) != review_hash:
            raise KhataDraftError("Khata changed after review; refresh before physical handover.")
        snapshot.update(recipient=recipient.strip(), reference=reference.strip())
        op = _operation(account, actor, key, fingerprint, "HANDOVER", business_date, snapshot, item=item, parent=parent)
        if "valuations" in snapshot:
            _save_valuations(op, snapshot)
        return op
