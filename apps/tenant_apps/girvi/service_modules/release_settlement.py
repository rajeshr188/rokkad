from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Sum

from apps.tenant_apps.girvi.models.accrual import AccrualStatus


MONEY_PLACES = Decimal("0.01")
ROUNDING_TOLERANCE = Decimal("0.01")
COMPATIBILITY_NO_POSTED_ACCRUAL_ROWS = "NO_POSTED_ACCRUAL_ROWS"
VARIANCE_MATCH = "MATCH"
VARIANCE_WITHIN_TOLERANCE = "WITHIN_TOLERANCE"
VARIANCE_ABOVE_TOLERANCE = "ABOVE_TOLERANCE"


@dataclass(frozen=True)
class ReleaseSettlementBasis:
    principal_due: Decimal
    selector_interest_quote: Decimal
    accrual_interest_gross: Decimal
    interest_paid: Decimal
    final_interest_due: Decimal
    total_due: Decimal
    variance: Decimal
    basis: str
    used_accrual_rows: bool
    compatibility_reason: str = ""
    compatibility_code: str = ""
    variance_classification: str = VARIANCE_MATCH


def _decimal(value) -> Decimal:
    amount = getattr(value, "amount", value)
    return Decimal(str(amount or 0)).quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)


def _sum_accrual_rows(loan, release_date) -> Decimal:
    accruals = getattr(loan, "interest_accruals", None)
    if accruals is None or not getattr(loan, "pk", None):
        return Decimal("0.00")

    cutoff = release_date.date() if hasattr(release_date, "date") else release_date
    total = (
        accruals.filter(
            period_end__lte=cutoff,
            status=AccrualStatus.POSTED,
        ).aggregate(total=Sum("accrued_amount"))["total"]
        or Decimal("0.00")
    )
    return _decimal(total)


def classify_settlement_variance(variance: Decimal) -> str:
    absolute_variance = abs(_decimal(variance))
    if absolute_variance == 0:
        return VARIANCE_MATCH
    if absolute_variance <= ROUNDING_TOLERANCE:
        return VARIANCE_WITHIN_TOLERANCE
    return VARIANCE_ABOVE_TOLERANCE


def build_release_settlement_basis(loan, release_date) -> ReleaseSettlementBasis:
    from apps.tenant_apps.girvi.selectors import (
        build_loan_settlement_balance,
        loan_total_interest_payments,
    )

    settlement = build_loan_settlement_balance(loan, as_of_date=release_date)
    principal_due = _decimal(settlement.principal_due)
    selector_interest_quote = _decimal(settlement.interest_due)
    interest_paid = _decimal(loan_total_interest_payments(loan))
    accrual_interest_gross = _sum_accrual_rows(loan, release_date)

    if accrual_interest_gross > 0:
        final_interest_due = max(
            accrual_interest_gross - interest_paid,
            Decimal("0.00"),
        ).quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)
        basis = "ACCRUAL_ROWS"
        used_accrual_rows = True
        compatibility_reason = ""
        compatibility_code = ""
    else:
        final_interest_due = selector_interest_quote
        basis = "SELECTOR_COMPATIBILITY"
        used_accrual_rows = False
        compatibility_reason = "No posted accrual rows were available through the release date."
        compatibility_code = COMPATIBILITY_NO_POSTED_ACCRUAL_ROWS

    total_due = (principal_due + final_interest_due).quantize(
        MONEY_PLACES,
        rounding=ROUND_HALF_UP,
    )
    variance = (selector_interest_quote - final_interest_due).quantize(
        MONEY_PLACES,
        rounding=ROUND_HALF_UP,
    )

    return ReleaseSettlementBasis(
        principal_due=principal_due,
        selector_interest_quote=selector_interest_quote,
        accrual_interest_gross=accrual_interest_gross,
        interest_paid=interest_paid,
        final_interest_due=final_interest_due,
        total_due=total_due,
        variance=variance,
        basis=basis,
        used_accrual_rows=used_accrual_rows,
        compatibility_reason=compatibility_reason,
        compatibility_code=compatibility_code,
        variance_classification=classify_settlement_variance(variance),
    )


def apply_release_settlement_snapshot(release, basis: ReleaseSettlementBasis):
    release.settlement_basis = basis.basis
    release.settlement_principal_amount = basis.principal_due
    release.settlement_interest_amount = basis.final_interest_due
    release.settlement_total_amount = basis.total_due
    release.selector_interest_quote = basis.selector_interest_quote
    release.accrual_interest_gross = basis.accrual_interest_gross
    release.interest_paid_snapshot = basis.interest_paid
    release.interest_basis_variance = basis.variance
    return release
