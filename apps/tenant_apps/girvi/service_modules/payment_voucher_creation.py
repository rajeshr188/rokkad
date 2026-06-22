"""Compatibility voucher creation helpers for Girvi loan models.

These helpers keep old model method behavior available while moving direct DEA
model access behind the Girvi integration adapter.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.utils import timezone
from moneyed import Money

from apps.tenant_apps.girvi.integrations.dea_adapter import create_payment_voucher
from apps.tenant_apps.girvi.selectors import build_loan_settlement_balance


def _require_created_by(created_by):
    if not created_by:
        raise ValidationError("created_by user is required")


def _money(value, *, currency="INR"):
    if isinstance(value, Money):
        return value
    if isinstance(value, Decimal):
        return Money(value, currency)
    return Money(Decimal(str(value)), currency)


def create_given_loan_release_payment(
    loan,
    *,
    principal=None,
    interest=None,
    payment_date=None,
    payment_method="CASH",
    reference_number="",
    description="",
    created_by=None,
):
    _require_created_by(created_by)

    settlement = build_loan_settlement_balance(loan)
    principal = _money(principal if principal is not None else settlement.principal_due)
    interest = _money(interest if interest is not None else settlement.interest_due)
    total = principal + interest

    return create_payment_voucher(
        loan,
        total_amount=total,
        principal_amount=principal,
        interest_amount=interest,
        direction="RECEIPT",
        payment_type="RECEIPT",
        payment_method=payment_method,
        reference_number=reference_number,
        description=description,
        payment_date=payment_date or timezone.now(),
        created_by=created_by,
        updated_by=created_by,
    )


def create_given_loan_disbursal_payment(
    loan,
    *,
    amount=None,
    payment_date=None,
    payment_method="CASH",
    reference_number="",
    description="",
    created_by=None,
):
    _require_created_by(created_by)
    amount = _money(amount if amount is not None else loan.get_loan_amount_with_currency)

    return create_payment_voucher(
        loan,
        total_amount=amount,
        principal_amount=amount,
        direction="PAYMENT",
        payment_type="DISBURSAL",
        payment_method=payment_method,
        reference_number=reference_number,
        description=description,
        payment_date=payment_date or timezone.now(),
        created_by=created_by,
        updated_by=created_by,
    )


def create_given_loan_receipt_payment(
    loan,
    *,
    amount,
    payment_date=None,
    payment_method="CASH",
    reference_number="",
    interest=None,
    principal=None,
    description="",
    is_final=False,
    create_release=False,
    created_by=None,
):
    _require_created_by(created_by)
    amount = _money(amount)

    return create_payment_voucher(
        loan,
        total_amount=amount,
        principal_amount=principal or amount,
        interest_amount=interest,
        direction="RECEIPT",
        payment_type="RECEIPT",
        payment_method=payment_method,
        reference_number=reference_number,
        description=description,
        is_final_payment=is_final,
        create_release=create_release,
        payment_date=payment_date or timezone.now(),
        created_by=created_by,
        updated_by=created_by,
    )


def create_taken_loan_repayment_payment(
    loan,
    *,
    amount,
    payment_date=None,
    payment_method="CASH",
    reference_number="",
    interest=None,
    principal=None,
    description="",
    is_final=False,
    created_by=None,
):
    _require_created_by(created_by)
    amount = _money(amount)

    return create_payment_voucher(
        loan,
        total_amount=amount,
        principal_amount=principal or amount,
        interest_amount=interest,
        direction="PAYMENT",
        payment_type="RECEIPT",
        payment_method=payment_method,
        reference_number=reference_number,
        description=description,
        is_final_payment=is_final,
        payment_date=payment_date or timezone.now(),
        created_by=created_by,
        updated_by=created_by,
    )
