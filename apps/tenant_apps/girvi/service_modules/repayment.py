"""Repayment use-case services for Girvi loans."""

import logging
from dataclasses import dataclass, field as dc_field

from django.db import transaction

from apps.tenant_apps.girvi.integrations.dea_adapter import post_payment_voucher
from apps.tenant_apps.girvi.selectors import build_loan_settlement_balance
from apps.tenant_apps.girvi.service_modules.accrual import (
    InterestAccrualCommand,
    InterestAccrualService,
)
from apps.tenant_apps.girvi.service_modules.loan_posting import GivenLoanPostingService
from apps.tenant_apps.girvi.service_modules.preferences import (
    is_loan_catchup_on_receipt_enabled,
)
from apps.tenant_apps.girvi.service_modules.repayment_idempotency import (
    build_repayment_idempotency_marker,
)

logger = logging.getLogger(__name__)


@dataclass
class RepaymentCommand:
    loan: object
    cleaned_data: dict
    created_by: object
    workspace: object | None = None


@dataclass
class RepaymentResult:
    payment: object | None = None
    payment_created: bool = False
    accounting_posted: bool = False
    success_message: str = ""
    warnings: list[str] = dc_field(default_factory=list)
    errors: list[str] = dc_field(default_factory=list)


def _build_repayment_payload(cleaned_data):
    total = cleaned_data["total_amount"]
    interest = cleaned_data.get("interest_amount")
    principal = (total - interest) if interest is not None else None
    return {
        "total_amount": total,
        "interest_amount": interest,
        "principal_amount": principal,
        "payment_date": cleaned_data["payment_date"],
        "payment_method": cleaned_data["payment_method"],
        "reference_number": cleaned_data.get("reference_number", ""),
        "idempotency_key": cleaned_data.get("idempotency_key", ""),
        "description": cleaned_data.get("description", ""),
        "is_final_payment": cleaned_data.get("is_final_payment", False),
    }


def _repayment_validation_errors(loan, payload, *, loan_kind="given"):
    settlement = build_loan_settlement_balance(loan, loan_kind=loan_kind)
    errors = []
    if payload["total_amount"] > settlement.total_outstanding:
        errors.append(
            f"Payment amount {payload['total_amount']} cannot exceed outstanding amount {settlement.total_outstanding}."
        )
    interest = payload.get("interest_amount") or 0
    if interest > settlement.interest_due:
        errors.append(
            f"Interest portion {interest} cannot exceed outstanding interest {settlement.interest_due}."
        )
    return errors, settlement


def _repayment_success_message(payment, payload, settlement, *, created=True):
    payment_id = getattr(payment, "payment_id", "payment")
    remaining = max(
        settlement.total_outstanding - payload["total_amount"],
        0,
    )
    principal = payload.get("principal_amount") or 0
    interest = payload.get("interest_amount") or 0
    if created:
        action = "recorded and posted to accounting"
    else:
        action = "already recorded and posted to accounting"
    return (
        f"Payment {payment_id} {action}. "
        f"Total {payload['total_amount']}; principal {principal}; "
        f"interest {interest}; remaining outstanding {remaining}."
    )


def _workspace_for_user(user):
    return getattr(getattr(user, "profile", None), "workspace", None)


class GivenLoanRepaymentService:
    """Record a GivenLoan receipt with optional catch-up accrual and posting."""

    @classmethod
    def execute(cls, command: RepaymentCommand) -> RepaymentResult:
        result = RepaymentResult()
        payment_payload = _build_repayment_payload(command.cleaned_data)
        validation_errors, settlement = _repayment_validation_errors(
            command.loan,
            payment_payload,
        )
        if validation_errors:
            result.errors.extend(validation_errors)
            return result

        cls._run_catchup_accrual(command, result)

        try:
            payment, created = GivenLoanPostingService().post_repayment(
                command.loan,
                payment_payload,
                command.created_by,
            )
            result.payment = payment
            result.payment_created = created
            result.accounting_posted = True
            result.success_message = _repayment_success_message(
                payment,
                payment_payload,
                settlement,
                created=created,
            )
        except Exception as exc:
            logger.exception(
                "Accounting post failed for payment %s",
                getattr(result.payment, "payment_id", "unknown"),
            )
            result.errors.append(
                f"Payment was not recorded because accounting posting failed: {exc}"
            )

        return result

    @classmethod
    def _run_catchup_accrual(cls, command: RepaymentCommand, result: RepaymentResult):
        workspace = command.workspace or _workspace_for_user(command.created_by)
        if not is_loan_catchup_on_receipt_enabled(workspace):
            return

        cleaned_data = command.cleaned_data
        try:
            accrual_result = InterestAccrualService.execute(
                InterestAccrualCommand(
                    loan=command.loan,
                    as_of_date=cleaned_data["payment_date"],
                    trigger_source="RECEIPT",
                    created_by=command.created_by,
                    notes=(
                        f"Catch-up accrual before receipt {cleaned_data.get('reference_number', '')}".strip()
                    ),
                    post_to_accounting=True,
                )
            )
            if not accrual_result.success:
                result.warnings.append(
                    "Interest accrual catch-up could not be completed before posting "
                    f"the receipt: {accrual_result.message}"
                )
        except Exception as exc:
            logger.exception(
                "Interest accrual catch-up failed before loan payment for loan %s",
                getattr(command.loan, "pk", None),
            )
            result.warnings.append(
                f"Interest accrual catch-up failed before posting the receipt: {exc}"
            )


class TakenLoanRepaymentService:
    """Record and post a TakenLoan repayment."""

    @classmethod
    def execute(cls, command: RepaymentCommand) -> RepaymentResult:
        cleaned_data = command.cleaned_data
        payload = _build_repayment_payload(cleaned_data)
        result = RepaymentResult()
        validation_errors, settlement = _repayment_validation_errors(
            command.loan,
            payload,
            loan_kind="taken",
        )
        if validation_errors:
            result.errors.extend(validation_errors)
            return result

        try:
            with transaction.atomic():
                existing = None
                reference_number = payload["reference_number"]
                payments = getattr(command.loan, "payments", None)
                if reference_number and payments is not None:
                    existing = (
                        payments.filter(
                            direction="PAYMENT",
                            reference_number=reference_number,
                        )
                        .order_by("pk")
                        .first()
                    )
                if existing:
                    result.payment = existing
                    result.payment_created = False
                    result.accounting_posted = True
                    result.success_message = _repayment_success_message(
                        existing,
                        payload,
                        settlement,
                        created=False,
                    )
                    return result

                if not reference_number:
                    reference_number = build_repayment_idempotency_marker(
                        command.loan,
                        payload,
                        loan_kind="taken",
                    )
                    payload["reference_number"] = reference_number
                    if payments is not None:
                        existing = (
                            payments.filter(
                                direction="PAYMENT",
                                reference_number=reference_number,
                            )
                            .order_by("pk")
                            .first()
                        )
                    if existing:
                        result.payment = existing
                        result.payment_created = False
                        result.accounting_posted = True
                        result.success_message = _repayment_success_message(
                            existing,
                            payload,
                            settlement,
                            created=False,
                        )
                        return result

                payment = command.loan.create_payment(
                    amount=payload["total_amount"],
                    payment_date=payload["payment_date"],
                    payment_method=payload["payment_method"],
                    reference_number=payload["reference_number"],
                    interest=payload["interest_amount"],
                    principal=payload["principal_amount"],
                    description=payload["description"],
                    is_final=payload["is_final_payment"],
                    created_by=command.created_by,
                )
                post_payment_voucher(payment, command.created_by)

            result.payment = payment
            result.payment_created = True
            result.accounting_posted = True
            result.success_message = _repayment_success_message(
                payment,
                payload,
                settlement,
                created=True,
            )
        except Exception as exc:
            logger.exception(
                "Accounting post failed for taken loan payment %s",
                getattr(locals().get("payment"), "payment_id", "unknown"),
            )
            result.errors.append(
                f"Payment was not recorded because accounting posting failed: {exc}"
            )

        return result
