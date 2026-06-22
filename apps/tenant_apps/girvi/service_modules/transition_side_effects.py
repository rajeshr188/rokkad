"""Reusable transition side-effect orchestration helpers."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils.translation import gettext_lazy as _

from apps.tenant_apps.girvi.transitions.types import TransitionResult


@dataclass
class RecoveryAmountParseResult:
    amount: object = None
    error_message: str = ""


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
    with transaction.atomic():
        transition_method(**payload_kwargs)
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
