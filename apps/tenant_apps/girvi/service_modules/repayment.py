"""Repayment use-case services for Girvi loans."""

import logging
from dataclasses import dataclass, field as dc_field

from django.db import connection, transaction

from apps.configuration.accounting_integration import is_dea_integration_enabled
from apps.tenant_apps.girvi.integrations.dea_adapter import (
    build_posting_idempotency_key,
    post_payment_voucher,
    record_posting_event,
)
from apps.tenant_apps.girvi.models import LoanRepayment, LoanRepaymentDirection
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
    repayment: object | None = None
    repayment_created: bool = False
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


def _taken_repayment_success_message(result, payload, settlement):
    repayment_id = getattr(result.repayment, "pk", "repayment")
    remaining = max(settlement.total_outstanding - payload["total_amount"], 0)
    if result.accounting_posted:
        delivery = "and posted to accounting"
    else:
        delivery = "for deferred accounting delivery"
    action = "recorded" if result.repayment_created else "already recorded"
    return (
        f"Repayment {repayment_id} {action} {delivery}. "
        f"Total {payload['total_amount']}; principal {payload['principal_amount'] or 0}; "
        f"interest {payload['interest_amount'] or 0}; remaining outstanding {remaining}."
    )


def _taken_repayment_conflicts(existing, payload):
    expected = {
        "total_amount": payload["total_amount"],
        "principal_amount": payload["principal_amount"],
        "interest_amount": payload["interest_amount"],
        "payment_date": payload["payment_date"],
        "payment_method": payload["payment_method"],
        "description": payload["description"],
        "is_final_payment": payload["is_final_payment"],
    }
    return tuple(
        field_name
        for field_name, expected_value in expected.items()
        if getattr(existing, field_name) != expected_value
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
                reference_number = payload["reference_number"]
                if not reference_number:
                    reference_number = build_repayment_idempotency_marker(
                        command.loan,
                        payload,
                        loan_kind="taken",
                    )
                    payload["reference_number"] = reference_number

                existing_repayment = (
                    LoanRepayment.objects.filter(
                        taken_loan=command.loan,
                        reference_number=reference_number,
                    )
                    .order_by("pk")
                    .first()
                )
                if existing_repayment:
                    conflicts = _taken_repayment_conflicts(
                        existing_repayment,
                        payload,
                    )
                    if conflicts:
                        result.errors.append(
                            "Repayment reference was already used with different "
                            f"details: {', '.join(conflicts)}."
                        )
                        return result
                    result.repayment = existing_repayment
                    if existing_repayment.accounting_voucher_pk:
                        result.payment = command.loan.payments.filter(
                            pk=existing_repayment.accounting_voucher_pk
                        ).first()
                        result.accounting_posted = result.payment is not None
                    result.success_message = _taken_repayment_success_message(
                        result, payload, settlement
                    )
                    return result

                payments = getattr(command.loan, "payments", None)
                legacy_payment = None
                if payments is not None:
                    legacy_payment = (
                        payments.filter(
                            direction="PAYMENT",
                            reference_number=reference_number,
                        )
                        .order_by("pk")
                        .first()
                    )
                if legacy_payment:
                    result.payment = legacy_payment
                    result.accounting_posted = True
                    result.success_message = _repayment_success_message(
                        legacy_payment, payload, settlement, created=False
                    )
                    return result

                workspace = command.workspace or getattr(connection, "tenant", None)
                payment = None
                if is_dea_integration_enabled(workspace):
                    payment = command.loan.create_payment(
                        amount=payload["total_amount"],
                        payment_date=payload["payment_date"],
                        payment_method=payload["payment_method"],
                        reference_number=reference_number,
                        interest=payload["interest_amount"],
                        principal=payload["principal_amount"],
                        description=payload["description"],
                        is_final=payload["is_final_payment"],
                        created_by=command.created_by,
                    )
                    post_payment_voucher(payment, command.created_by)

                repayment = LoanRepayment.objects.create(
                    taken_loan=command.loan,
                    direction=LoanRepaymentDirection.PAYMENT,
                    total_amount=payload["total_amount"],
                    principal_amount=payload["principal_amount"],
                    interest_amount=payload["interest_amount"],
                    payment_date=payload["payment_date"],
                    payment_method=payload["payment_method"],
                    reference_number=reference_number,
                    description=payload["description"],
                    is_final_payment=payload["is_final_payment"],
                    created_by=command.created_by,
                    accounting_voucher_pk=getattr(payment, "pk", None),
                )

                if payment is None:
                    dedupe_key = build_posting_idempotency_key(
                        event_key="taken_loan_repayment",
                        source_document=repayment,
                    )
                    record_posting_event(
                        event_key="taken_loan_repayment",
                        source_document=repayment,
                        dedupe_key=dedupe_key,
                        payload=None,
                    )

            result.repayment = repayment
            result.repayment_created = True
            result.payment = payment
            result.payment_created = payment is not None
            result.accounting_posted = payment is not None
            result.success_message = _taken_repayment_success_message(
                result, payload, settlement
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
