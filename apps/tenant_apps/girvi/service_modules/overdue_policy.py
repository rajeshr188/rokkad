from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from dateutil.relativedelta import relativedelta
from django.utils import timezone


@dataclass(frozen=True)
class OverduePolicySnapshot:
    maturity_date: object | None
    as_of_date: object
    settlement_amount: Decimal
    current_value: Decimal
    maturity_expired: bool
    undersecured: bool

    @property
    def is_overdue(self) -> bool:
        return self.maturity_expired or self.undersecured

    @property
    def is_npa(self) -> bool:
        return self.undersecured


def _as_date(value):
    return value.date() if hasattr(value, "date") else value


def _as_decimal(value) -> Decimal:
    amount = getattr(value, "amount", value)
    try:
        return Decimal(str(amount or 0)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0.00")


def _current_value(loan) -> Decimal:
    value = getattr(loan, "current_value", None)
    if callable(value):
        value = value()
    if value is None:
        get_current_value = getattr(loan, "get_current_value", None)
        if callable(get_current_value):
            value = get_current_value()
    return _as_decimal(value)


def maturity_date_for_loan(loan):
    maturity_date = getattr(loan, "maturity_date", None)
    if maturity_date:
        return _as_date(maturity_date)

    loan_date = getattr(loan, "loan_date", None)
    tenure = getattr(loan, "tenure", None)
    if loan_date is None or tenure is None:
        return None

    return _as_date(loan_date) + relativedelta(months=int(tenure))


def evaluate_overdue_policy(loan, *, as_of_date=None) -> OverduePolicySnapshot:
    from apps.tenant_apps.girvi.selectors import build_loan_settlement_balance

    as_of = _as_date(as_of_date or timezone.localdate())
    maturity_date = maturity_date_for_loan(loan)
    maturity_expired = bool(maturity_date and maturity_date < as_of)

    settlement = build_loan_settlement_balance(loan)
    settlement_amount = _as_decimal(settlement.total_outstanding)
    current_value = _current_value(loan)
    undersecured = settlement_amount > current_value

    return OverduePolicySnapshot(
        maturity_date=maturity_date,
        as_of_date=as_of,
        settlement_amount=settlement_amount,
        current_value=current_value,
        maturity_expired=maturity_expired,
        undersecured=undersecured,
    )
