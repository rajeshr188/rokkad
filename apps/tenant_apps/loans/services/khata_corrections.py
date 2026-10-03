"""Bounded compensating corrections, never edits or automatic physical reversals."""
from decimal import Decimal, ROUND_DOWN

from django.db.models import Max
from django.utils import timezone

from apps.tenancy.context import current_workspace_id
from apps.tenant_apps.loans.access import LOANS_ADMIN_ACTION
from apps.tenant_apps.loans.selectors.khata import eligible_items, held_items, account_balances, account_position, effective_agreement
from .action_access import require_workspace_action
from .khata_accounts import KhataDraftError, _hash, _key
from .khata_collateral import _values, _reserve
from .khata_opening import _locked, _operation, _retry, _save_valuations
from .khata_servicing import _active


class KhataCorrectionBlocked(KhataDraftError):
    def __init__(self, operation_ids):
        self.operation_ids = tuple(operation_ids)
        super().__init__("Later dependent operations block correction: " + ", ".join(map(str, operation_ids)))


def correction_guidance(account, source):
    """Read-only scope/dependency guidance; command review remains authoritative."""
    if (current_workspace_id() != account.workspace_id or source.workspace_id != account.workspace_id
            or source.account_id != account.pk):
        raise ValueError("Correction guidance requires the matching Workspace and account.")
    result = dict(source=source, review_available=False, blockers=[], blocker_count=0)
    if account.operations.filter(correction_of=source).exists():
        result["message"] = "This operation has already been corrected. Its original evidence remains preserved."
    elif source.kind not in ("INTEREST", "EXCHANGE"):
        result["message"] = "This operation type has no supported correction workflow. Record the discrepancy and request a reviewed support resolution."
    elif account.state != "ACTIVE":
        result["message"] = "Corrections currently require an active account. Financially settled or closed accounts need a reviewed support resolution."
    else:
        ids = _dependencies(account, source)
        result["blocker_count"] = len(ids)
        result["blockers"] = account.operations.filter(pk__in=ids).order_by("sequence")[:10]
        result["review_available"] = not ids
        result["message"] = ("Later operations block this correction. Review their sources with the workspace administrator."
            if ids else "This operation supports correction review. Review still checks authority, current evidence, cash resolution and applicable collateral conditions.")
    return result


def _source(account, source_id):
    source = account.operations.filter(pk=source_id).first()
    if source is None:
        raise KhataDraftError("Correction source does not belong to this khata.")
    if account.operations.filter(correction_of=source).exists():
        raise KhataDraftError("This source has already been corrected.")
    if source.kind not in ("INTEREST", "EXCHANGE"):
        raise KhataDraftError(f"{source.kind} correction is not supported; do not edit the original source.")
    return source


def _dependencies(account, source):
    later = account.operations.filter(sequence__gt=source.sequence).exclude(kind="CORRECT").filter(corrected_by__isnull=True)
    blocking = list(later.values_list("pk", flat=True))
    for op in account.operations.filter(kind="CORRECT", sequence__gt=source.sequence):
        pending = op.collateral_selections.filter(role="OUT", item__in=held_items(account))
        if pending.exists():
            blocking.append(op.pk)
    return sorted(set(blocking))


def _review(account, workspace, actor, day, source_id):
    _active(account, day)
    if day < account.operations.aggregate(latest=Max("business_date"))["latest"]:
        raise KhataDraftError("Correction date cannot precede the latest recorded operation.")
    source = _source(account, source_id)
    blockers = _dependencies(account, source)
    if blockers:
        raise KhataCorrectionBlocked(blockers)
    snapshot = dict(schema="khata-correction/1", account_id=account.pk, date=day.isoformat(),
        last_sequence=account.operations.aggregate(last=Max("sequence"))["last"], source_id=source.pk,
        source_kind=source.kind, source_sequence=source.sequence, source_request_sha256=source.request_sha256,
        principal=str(account_position(account).principal))
    if source.kind == "INTEREST":
        allocations = list(source.interest_allocations.order_by("period__index").values("period_id", "amount", "period__index"))
        snapshot.update(amount=str(source.amount), allocations=[dict(period_id=r["period_id"],
            index=r["period__index"], amount=str(r["amount"])) for r in allocations],
            due_interest_before=str(account_balances(workspace=workspace, actor=actor, account_id=account.pk)["due_interest"]))
    else:
        original_out = list(source.collateral_selections.filter(role="OUT").order_by("item_id").values_list("item_id", flat=True))
        incoming = list(source.collateral_selections.filter(role="IN").order_by("item_id").values_list("item_id", flat=True))
        # Release the original outgoing reservations logically for this review;
        # replacement items remain held but are reserved for their actual return.
        available_ids = set(eligible_items(account).values_list("pk", flat=True)) | set(original_out)
        items = list(held_items(account).filter(pk__in=available_ids))
        if not set(original_out + incoming).issubset({i.pk for i in items}):
            raise KhataDraftError("Exchange custody has changed; cancellation needs separate review.")
        values = _values(account, workspace, day, items)
        retained = sum((Decimal(v["value"]) for v in values if v["item_id"] not in incoming), Decimal(0))
        backing = (retained*effective_agreement(account).ltv).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
        if backing < account_position(account).principal:
            raise KhataDraftError("Retained collateral does not meet LTV after cancelling this exchange.")
        snapshot.update(amount="0.00", released_ids=original_out, outgoing_ids=incoming, valuations=values,
            retained_value=str(retained), backing=str(backing))
    return source, snapshot


def preview_correction(*, workspace, actor, account_id, source_id):
    with _locked(workspace, actor, account_id, LOANS_ADMIN_ACTION) as account:
        _, snapshot = _review(account, workspace, actor, timezone.localdate(), source_id)
        return {"snapshot": snapshot, "review_hash": _hash(snapshot)}


def record_correction(*, workspace, actor, account_id, source_id, business_date, request_key,
                      review_hash, reason, resolution_reference, cash_resolution=""):
    if not reason.strip() or not resolution_reference.strip():
        raise KhataDraftError("Record the correction reason and actual resolution reference.")
    key = _key(request_key)
    fingerprint = _hash(dict(kind="CORRECT", actor=actor.pk, source_id=source_id, date=business_date,
        review=review_hash, reason=reason.strip(), reference=resolution_reference.strip(), cash_resolution=cash_resolution))
    with _locked(workspace, actor, account_id, LOANS_ADMIN_ACTION) as account:
        source = account.operations.filter(pk=source_id).first()
        if source is None:
            raise KhataDraftError("Correction source does not belong to this khata.")
        require_workspace_action(workspace, actor, *(('loan.repay',) if source.kind == "INTEREST" else ('data.edit', 'loan.release')))
        if op := _retry(account, key, fingerprint):
            return op
        source, snapshot = _review(account, workspace, actor, business_date, source_id)
        if _hash(snapshot) != review_hash:
            raise KhataDraftError("Khata changed after review; refresh the correction preview.")
        if (source.kind == "INTEREST" and cash_resolution not in ("NOT_RECEIVED", "REFUNDED")) or (source.kind == "EXCHANGE" and cash_resolution):
            raise KhataDraftError("Confirm whether the entire receipt was not received or was actually refunded; exchanges do not reverse cash.")
        snapshot.update(reason=reason.strip(), resolution_reference=resolution_reference.strip(), cash_resolution=cash_resolution)
        op = _operation(account, actor, key, fingerprint, "CORRECT", business_date, snapshot,
            correction_of=source, amount=source.amount, agreement=source.agreement)
        if source.kind == "EXCHANGE":
            _save_valuations(op, snapshot)
            _reserve(op, snapshot["outgoing_ids"])
        return op
