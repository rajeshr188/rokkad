"""Reusable transition side-effect orchestration helpers."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from apps.tenant_apps.girvi.transitions.types import TransitionResult


@dataclass
class RecoveryAmountParseResult:
    amount: object = None
    error_message: str = ""


def _to_decimal_or_zero(value):
    if value in (None, ""):
        return Decimal("0.00")
    return Decimal(str(value))


def _apply_disbursal_components(loan, payload_kwargs):
    if not hasattr(loan, "disbursal_upfront_interest_deduction"):
        return

    interest = _to_decimal_or_zero(payload_kwargs.get("upfront_interest_deduction"))
    document_charge = _to_decimal_or_zero(payload_kwargs.get("document_charge"))

    if interest < 0 or document_charge < 0:
        raise ValidationError("Disbursal deduction amounts cannot be negative.")

    principal = Decimal(str(getattr(loan, "get_loan_amount", Decimal("0.00")) or Decimal("0.00")))
    if (interest + document_charge) > principal:
        raise ValidationError("Total disbursal deductions cannot exceed the loan principal amount.")

    loan.disbursal_upfront_interest_deduction = interest
    loan.disbursal_document_charge = document_charge
    save = getattr(loan, "save", None)
    if callable(save):
        try:
            save(
                update_fields=[
                    "disbursal_upfront_interest_deduction",
                    "disbursal_document_charge",
                ]
            )
        except TypeError:
            save()


def parse_recovery_amount(payload_kwargs, *, missing_message, non_positive_message):
    amount = (
        payload_kwargs["amount"]
        if "amount" in payload_kwargs
        else payload_kwargs.get("recovery_amount")
    )
    if amount is not None:
        payload_kwargs["recovery_amount"] = amount
        payload_kwargs.pop("amount", None)

    if amount is None:
        return RecoveryAmountParseResult(error_message=missing_message)

    try:
        if Decimal(str(amount)) <= 0:
            return RecoveryAmountParseResult(error_message=non_positive_message)
    except (InvalidOperation, TypeError, ValueError):
        return RecoveryAmountParseResult(error_message=non_positive_message)

    return RecoveryAmountParseResult(amount=amount)


def execute_disbursal_transition(
    *,
    loan,
    user,
    transition_method,
    payload_kwargs,
    active_statuses,
    post_disbursal,
):
    transition_kwargs = {
        "disbursed_by": payload_kwargs.get("disbursed_by"),
    }

    with transaction.atomic():
        _apply_disbursal_components(loan, payload_kwargs)
        transition_method(**transition_kwargs)
        if loan.status not in active_statuses:
            return TransitionResult(
                success=True,
                level="success",
                message=str(_("Loan status updated successfully.")),
            )

        payment, created = post_disbursal(loan, user)

    if created:
        message = str(
            _(
                f"Loan status updated successfully. "
                f"Disbursal voucher {payment.payment_id} posted."
            )
        )
    else:
        message = str(
            _(
                f"Loan status updated successfully. "
                f"Disbursal already recorded as {payment.payment_id}."
            )
        )

    return TransitionResult(
        success=True,
        level="success",
        message=message,
        payment=payment,
        created=created,
    )


def execute_recovery_transition(
    *,
    loan,
    user,
    transition_method,
    payload_kwargs,
    success_status,
    post_recovery,
    posted_message,
    existing_message,
):
    with transaction.atomic():
        transition_method(**payload_kwargs)
        if loan.status != success_status:
            return TransitionResult(
                success=True,
                level="success",
                message=str(_("Loan status updated successfully.")),
            )

        payment, created = post_recovery(loan, payload_kwargs["recovery_amount"], user)

    message = str(_(posted_message.format(payment_id=payment.payment_id))) if created else str(
        _(existing_message.format(payment_id=payment.payment_id))
    )

    return TransitionResult(
        success=True,
        level="success",
        message=message,
        payment=payment,
        created=created,
    )
