"""Collect all khata debt, stop financial accrual and reserve remaining custody."""
from decimal import Decimal

from django.db.models import Max
from django.utils import timezone

from apps.tenant_apps.loans.models import KhataInterestPeriod
from apps.tenant_apps.loans.selectors.khata import account_position, effective_agreement, eligible_items, held_items, interest_schedule, calculated_interest_periods, activated_agreements
from .khata_accounts import KhataDraftError, _hash, _key
from .khata_collateral import _reserve
from .khata_opening import _locked, _operation, _retry
from .khata_servicing import _active, _period_evidence, _save_periods, _save_allocations


def _review(account, day):
    _active(account, day)
    position = account_position(account)
    periods = interest_schedule(account, day)
    interest = sum((p["outstanding"] for p in periods), Decimal(0))
    return dict(schema="khata-settlement/1", account_id=account.pk, date=day.isoformat(),
        last_sequence=account.operations.aggregate(last=Max("sequence"))["last"],
        agreement_id=effective_agreement(account).pk, principal=str(position.principal),
        interest=str(interest.quantize(Decimal("0.01"))), total=str((position.principal+interest).quantize(Decimal("0.01"))),
        held_ids=list(held_items(account).values_list("pk", flat=True)),
        outgoing_ids=list(eligible_items(account).values_list("pk", flat=True)),
        allocations=[dict(index=p["index"], amount=str(p["outstanding"].quantize(Decimal("0.01")))) for p in periods if p["outstanding"] > 0])


def preview_settlement(*, workspace, actor, account_id):
    with _locked(workspace, actor, account_id, "data.view") as account:
        snapshot = _review(account, timezone.localdate())
        return {"snapshot": snapshot, "review_hash": _hash(snapshot)}


def record_settlement(*, workspace, actor, account_id, business_date, request_key, review_hash, payment_reference):
    if not payment_reference.strip():
        raise KhataDraftError("Record the actual settlement payment/reference.")
    key = _key(request_key)
    fingerprint = _hash(dict(kind="SETTLE", actor=actor.pk, date=business_date, review=review_hash,
        payment_reference=payment_reference.strip()))
    with _locked(workspace, actor, account_id, "loan.repay") as account:
        if op := _retry(account, key, fingerprint):
            return op
        snapshot = _review(account, business_date)
        if _hash(snapshot) != review_hash:
            raise KhataDraftError("Khata changed after review; refresh the settlement quote.")
        saved = set(account.interest_periods.values_list("index", flat=True))
        agreements = {o.agreement.number: o.agreement for o in activated_agreements(account)}
        rows = []
        for p in calculated_interest_periods(account, business_date):
            if p.index not in saved:
                row = _period_evidence(p, agreements)
                row["charged_through"] = p.charged_through.isoformat() if p.charged_through < p.end else None
                rows.append(row)
        snapshot.update(periods=rows, payment_reference=payment_reference.strip())
        op = _operation(account, actor, key, fingerprint, "SETTLE", business_date, snapshot,
            amount=Decimal(snapshot["principal"]), interest_amount=Decimal(snapshot["interest"]), agreement_id=snapshot["agreement_id"])
        _save_periods(op, rows)
        ids = dict(KhataInterestPeriod.objects.filter(account=account).values_list("index", "pk"))
        # IDs are deterministically available only after inserting the new periods.
        # The frozen receipt evidence binds monthly indexes; typed rows bind IDs.
        _save_allocations(op, [dict(p, period_id=ids[p["index"]]) for p in snapshot["allocations"]])
        _reserve(op, snapshot["outgoing_ids"])
        return op
