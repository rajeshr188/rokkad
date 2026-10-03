"""Finalize khata interest and record actual collections against oldest dues."""
import uuid
from decimal import Decimal

from django.db.models import Max
from django.utils import timezone

from apps.tenant_apps.loans.domain.khata import amount
from apps.tenant_apps.loans.models import KhataInterestPeriod, KhataInterestSegment, KhataInterestAllocation
from apps.tenant_apps.loans.selectors.khata import activated_agreements, calculated_interest_periods, interest_schedule
from .khata_accounts import KhataDraftError, _hash, _key, _today
from .khata_opening import _locked, _operation, _retry


def _active(account, day):
    _today(day)
    if account.state != "ACTIVE" or account.opened_on is None:
        raise KhataDraftError("Interest servicing requires an active khata.")
    if day < account.opened_on:
        raise KhataDraftError("Interest servicing cannot precede the first withdrawal.")


def _period_evidence(period, agreements):
    return dict(index=period.index, start_on=period.start.isoformat(), end_on=period.end.isoformat(),
        due_on=period.due_on.isoformat(), actual_charge=str(period.actual_charge.quantize(Decimal("0.01"))),
        minimum_adjustment=str(period.minimum_adjustment.quantize(Decimal("0.01"))),
        charge=str(period.charge.quantize(Decimal("0.01"))), contract_version="KHATA-1",
        segments=[dict(sequence=n, agreement_id=agreements[s.terms.revision].pk, start_on=s.start.isoformat(),
            end_on=s.end.isoformat(), period_days=s.period_days,
            exact_numerator=str(s.exact_charge.numerator), exact_denominator=str(s.exact_charge.denominator))
            for n, s in enumerate(period.segments, 1)])


def _pending_periods(account, day):
    completed = set(account.interest_periods.values_list("index", flat=True))
    agreements = {op.agreement.number: op.agreement for op in activated_agreements(account)}
    return [_period_evidence(p, agreements) for p in calculated_interest_periods(account, day)
        if p.charged_through == p.end and p.index not in completed]


def _save_periods(op, rows):
    for row in rows:
        values = {k: v for k, v in row.items() if k != "segments"}
        period = KhataInterestPeriod(workspace_id=op.workspace_id, account_id=op.account_id,
            operation=op, **values)
        period.full_clean()
        period.save()
        for segment in row["segments"]:
            child = KhataInterestSegment(workspace_id=op.workspace_id, period=period, **segment)
            child.full_clean()
            child.save()


def _finalize(account, actor, day, key, fingerprint, rows):
    op = _operation(account, actor, key, fingerprint, "ACCRUE", day,
        {"schema": "khata-interest/1", "periods": rows})
    _save_periods(op, rows)
    return op


def preview_finalization(*, workspace, actor, account_id):
    with _locked(workspace, actor, account_id, "data.view") as account:
        day = timezone.localdate()
        _active(account, day)
        rows = _pending_periods(account, day)
        if not rows:
            raise KhataDraftError("There are no completed interest periods to finalize.")
        snapshot = dict(date=day.isoformat(), account_id=account.pk,
            last_sequence=account.operations.order_by("-sequence").values_list("sequence", flat=True).first(), periods=rows)
        return {"snapshot": snapshot, "review_hash": _hash(snapshot)}


def finalize_interest(*, workspace, actor, account_id, business_date, request_key, review_hash=None):
    """Freeze every elapsed month; annual charges retain their annual due date."""
    key = _key(request_key)
    instructions = dict(kind="ACCRUE", actor=actor.pk, date=business_date)
    if review_hash is not None:
        instructions["review"] = review_hash
    fingerprint = _hash(instructions)
    with _locked(workspace, actor, account_id, "loan.repay") as account:
        if op := _retry(account, key, fingerprint):
            return op
        _active(account, business_date)
        rows = _pending_periods(account, business_date)
        if not rows:
            raise KhataDraftError("There are no completed interest periods to finalize.")
        snapshot = dict(date=business_date.isoformat(), account_id=account.pk,
            last_sequence=account.operations.order_by("-sequence").values_list("sequence", flat=True).first(), periods=rows)
        if review_hash is not None and _hash(snapshot) != review_hash:
            raise KhataDraftError("Khata changed after review; refresh before finalizing interest.")
        return _finalize(account, actor, business_date, key, fingerprint, rows)


def _receipt_review(account, day, value):
    _active(account, day)
    schedule = interest_schedule(account, day)
    due = sorted((p for p in schedule if p["complete"] and p["due_on"] <= day and p["outstanding"] > 0),
        key=lambda p: (p["due_on"], p["index"]))
    due_total = sum((p["outstanding"] for p in due), Decimal(0))
    if value > due_total:
        raise KhataDraftError("Interest payment exceeds unpaid dues; advance or excess payments are not supported.")
    remaining, allocations = value, []
    for period in due:
        allocated = min(remaining, period["outstanding"])
        if allocated:
            allocations.append(dict(index=period["index"], amount=str(allocated.quantize(Decimal("0.01")))))
            remaining -= allocated
    return dict(schema="khata-interest/1", account_id=account.pk, date=day.isoformat(),
        last_sequence=account.operations.aggregate(last=Max("sequence"))["last"] or 0,
        amount=str(value), due_interest=str(due_total.quantize(Decimal("0.01"))), allocations=allocations)


def preview_interest_payment(*, workspace, actor, account_id, value):
    value = amount(value, positive=True).quantize(Decimal("0.01"))
    with _locked(workspace, actor, account_id, "data.view") as account:
        snapshot = _receipt_review(account, timezone.localdate(), value)
        return {"snapshot": snapshot, "review_hash": _hash(snapshot)}


def _save_allocations(op, rows):
    for row in rows:
        allocation = KhataInterestAllocation(workspace_id=op.workspace_id, operation=op,
            period_id=row["period_id"], amount=row["amount"])
        allocation.full_clean()
        allocation.save()


def record_interest_payment(*, workspace, actor, account_id, request_key, business_date,
                            value, review_hash, payment_reference):
    value = amount(value, positive=True).quantize(Decimal("0.01"))
    if not payment_reference.strip():
        raise KhataDraftError("Record the actual cash receipt or payment reference.")
    key = _key(request_key)
    fingerprint = _hash(dict(kind="INTEREST", actor=actor.pk, date=business_date, amount=str(value),
        review=review_hash, payment_reference=payment_reference.strip()))
    with _locked(workspace, actor, account_id, "loan.repay") as account:
        if op := _retry(account, key, fingerprint):
            return op
        snapshot = _receipt_review(account, business_date, value)
        if _hash(snapshot) != review_hash:
            raise KhataDraftError("Khata changed after review; refresh before collecting interest.")
        # The source receipt and any elapsed-period finalization commit together.
        # Finalization is not a backdated cash transaction.
        if rows := _pending_periods(account, business_date):
            _finalize(account, actor, business_date, uuid.uuid4(),
                _hash(dict(parent_request=str(key), kind="ACCRUE")), rows)
        period_ids = dict(account.interest_periods.values_list("index", "pk"))
        for allocation in snapshot["allocations"]:
            allocation["period_id"] = period_ids[allocation["index"]]
        snapshot["payment_reference"] = payment_reference.strip()
        op = _operation(account, actor, key, fingerprint, "INTEREST", business_date, snapshot, amount=value)
        _save_allocations(op, snapshot["allocations"])
        return op
