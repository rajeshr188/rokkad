"""Repayment use-case services for Girvi loans."""

import logging
from dataclasses import dataclass, field as dc_field

from apps.orgs.preferences import CompanyPreferences
from apps.tenant_apps.girvi.integrations.dea_adapter import post_payment_voucher
from apps.tenant_apps.girvi.service_modules.accrual import (
    InterestAccrualCommand,
    InterestAccrualService,
)
from apps.tenant_apps.girvi.service_modules.loan_posting import GivenLoanPostingService

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
        "description": cleaned_data.get("description", ""),
        "is_final_payment": cleaned_data.get("is_final_payment", False),
    }


def _workspace_for_user(user):
    return getattr(getattr(user, "profile", None), "workspace", None)


class GivenLoanRepaymentService:
    """Record a GivenLoan receipt with optional catch-up accrual and posting."""

    @classmethod
    def execute(cls, command: RepaymentCommand) -> RepaymentResult:
        result = RepaymentResult()
        cls._run_catchup_accrual(command, result)

        payment_payload = _build_repayment_payload(command.cleaned_data)
        try:
            payment, created = GivenLoanPostingService().post_repayment(
                command.loan,
                payment_payload,
                command.created_by,
            )
            result.payment = payment
            result.payment_created = created
            result.accounting_posted = True
            result.success_message = (
                f"Payment {payment.payment_id} recorded and posted to accounting."
            )
        except Exception as exc:
            logger.exception(
                "Accounting post failed for payment %s",
                getattr(result.payment, "payment_id", "unknown"),
            )
            result.warnings.append(f"Payment saved but accounting posting failed: {exc}")

        return result

    @classmethod
    def _run_catchup_accrual(cls, command: RepaymentCommand, result: RepaymentResult):
        workspace = command.workspace or _workspace_for_user(command.created_by)
        prefs = CompanyPreferences(workspace)
        if not prefs.loan_catchup_on_receipt:
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
        result.payment = payment
        result.payment_created = True

        try:
            post_payment_voucher(payment, command.created_by)
            result.accounting_posted = True
            result.success_message = (
                f"Payment {payment.payment_id} recorded and posted to accounting."
            )
        except Exception as exc:
            logger.exception(
                "Accounting post failed for taken loan payment %s",
                getattr(payment, "payment_id", "unknown"),
            )
            result.warnings.append(
                f"Payment {payment.payment_id} saved but accounting posting failed: {exc}"
            )

        return result
