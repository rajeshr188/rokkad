"""Controlled period operations and deterministic MVP accounting setup."""

from django.core.exceptions import ValidationError
from django.db import transaction

from ..models import (
    AccountingBook,
    AccountingOrganization,
    AccountingPeriod,
    AccountingPeriodTransition,
    Ledger,
    LedgerNodeKind,
    LedgerSide,
    PeriodStatus,
    ReportingClass,
)

ALLOWED_PERIOD_TRANSITIONS = {
    PeriodStatus.OPEN: {PeriodStatus.ADJUSTMENT_ONLY, PeriodStatus.CLOSED},
    PeriodStatus.ADJUSTMENT_ONLY: {PeriodStatus.CLOSED},
    PeriodStatus.CLOSED: {PeriodStatus.ADJUSTMENT_ONLY, PeriodStatus.LOCKED},
    PeriodStatus.LOCKED: set(),
}


@transaction.atomic
def transition_period(*, period, to_status, actor_id, actor_identity, occurred_at, reason=""):
    locked = AccountingPeriod.objects.select_for_update().get(pk=period.pk)
    if to_status not in ALLOWED_PERIOD_TRANSITIONS[locked.status]:
        raise ValidationError(f"Period transition {locked.status} -> {to_status} is not allowed.")
    reason = (reason or "").strip()
    if locked.status == PeriodStatus.CLOSED and to_status == PeriodStatus.ADJUSTMENT_ONLY and not reason:
        raise ValidationError("Reopening a closed period requires a reason.")
    evidence = AccountingPeriodTransition.objects.create(
        period=locked,
        from_status=locked.status,
        to_status=to_status,
        actor_id=actor_id,
        actor_identity=actor_identity,
        occurred_at=occurred_at,
        reason=reason,
    )
    locked.status = to_status
    if to_status == PeriodStatus.CLOSED:
        locked.closed_at, locked.closed_by_id = occurred_at, actor_id
    if to_status == PeriodStatus.LOCKED:
        locked.locked_at, locked.locked_by_id = occurred_at, actor_id
    locked.save()
    return locked, evidence


def _exact(model, lookup, expected):
    obj, created = model.objects.get_or_create(**lookup, defaults=expected)
    if not created:
        conflicts = [name for name, value in expected.items() if getattr(obj, name) != value]
        if conflicts:
            raise ValidationError(f"Existing {model.__name__} conflicts on: {', '.join(conflicts)}")
    return obj


@transaction.atomic
def bootstrap_mvp_accounting(*, tenant_key, tenant_name, period_key, start_date, end_date):
    organization = _exact(
        AccountingOrganization,
        {"organization_key": "WORKSPACE"},
        {"name": tenant_name, "external_tenant_key": tenant_key, "is_active": True},
    )
    book = _exact(
        AccountingBook,
        {"organization": organization, "book_key": "PRIMARY"},
        {"name": "Primary INR Book", "base_currency": "INR", "decimal_places": 2, "is_active": True},
    )
    period = _exact(
        AccountingPeriod,
        {"book": book, "period_key": period_key},
        {"start_date": start_date, "end_date": end_date, "status": PeriodStatus.OPEN},
    )
    definitions = (
        ("CASH", "1100", "Cash", ReportingClass.ASSET, LedgerSide.DEBIT),
        ("ACCOUNTS_RECEIVABLE", "1200", "Accounts Receivable", ReportingClass.ASSET, LedgerSide.DEBIT),
        ("SALES", "4100", "Sales", ReportingClass.REVENUE, LedgerSide.CREDIT),
    )
    ledgers = []
    for key, code, name, reporting_class, normal_side in definitions:
        ledgers.append(_exact(Ledger, {"book": book, "ledger_key": key}, {
            "code": code, "name": name, "reporting_class": reporting_class,
            "normal_side": normal_side, "node_kind": LedgerNodeKind.POSTING,
            "can_debit": True, "can_credit": True, "is_active": True,
        }))
    return organization, book, period, tuple(ledgers)
