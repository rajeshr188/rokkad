import logging
from dataclasses import dataclass, field as dc_field
from decimal import Decimal
from typing import Optional

from django.db import transaction

from apps.orgs.preferences import CompanyPreferences
from apps.tenant_apps.girvi.flows import (
    build_runtime_loan_flow,
    normalize_legacy_given_loan_status,
)
from apps.tenant_apps.girvi.models.loan_item import LoanItem
from apps.tenant_apps.girvi.models.loan_refactored import (
    GivenLoan,
    LoanLifecycleState,
)
from apps.tenant_apps.girvi.models.renewal import LoanRenewal

from .accrual import InterestAccrualCommand, InterestAccrualService
from .payment import record_loan_disbursal

logger = logging.getLogger(__name__)


@dataclass
class LoanRenewalCommand:
    source_loan_id: int
    renewal_date: object
    mode: str
    interest_paid: Decimal = dc_field(default_factory=lambda: Decimal("0"))
    principal_paid: Decimal = dc_field(default_factory=lambda: Decimal("0"))
    requested_extra_amount: Decimal = dc_field(default_factory=lambda: Decimal("0"))
    created_by: object = None
    payment_method: str = "CASH"
    reference_number: str = ""
    notes: str = ""


@dataclass
class LoanRenewalPreview:
    source_loan_id: int
    mode: str
    outstanding_principal: Decimal
    interest_due: Decimal
    collateral_value: Decimal
    principal_paid: Decimal
    interest_paid: Decimal
    requested_extra_amount: Decimal
    new_principal: Decimal
    is_valid: bool
    errors: list = dc_field(default_factory=list)


@dataclass
class LoanRenewalResult:
    success: bool
    message: str
    source_loan_id: int
    new_loan_id: Optional[int] = None
    warnings: list = dc_field(default_factory=list)


class LoanRenewalService:
    def preview(self, command: LoanRenewalCommand) -> LoanRenewalPreview:
        try:
            loan = GivenLoan.objects.get(pk=command.source_loan_id)
        except GivenLoan.DoesNotExist:
            return LoanRenewalPreview(
                source_loan_id=command.source_loan_id,
                mode=command.mode,
                outstanding_principal=Decimal("0"),
                interest_due=Decimal("0"),
                collateral_value=Decimal("0"),
                principal_paid=command.principal_paid,
                interest_paid=command.interest_paid,
                requested_extra_amount=command.requested_extra_amount,
                new_principal=Decimal("0"),
                is_valid=False,
                errors=["Loan not found"],
            )

        outstanding = loan.outstanding_principal.amount
        interest_due = Decimal(str(loan.interest_due()))
        collateral_value = Decimal(str(loan.current_value))

        errors = []
        new_principal = Decimal("0")

        if command.principal_paid > outstanding:
            errors.append(
                f"Principal paid ({command.principal_paid}) exceeds "
                f"outstanding balance ({outstanding})."
            )

        if command.mode == "PAY_AND_RENEW":
            new_principal = outstanding - command.principal_paid
        elif command.mode == "TOPUP_RENEW":
            remaining = outstanding - command.principal_paid
            new_principal = remaining + command.requested_extra_amount
            if new_principal > collateral_value:
                errors.append(
                    f"New principal ({new_principal}) exceeds collateral "
                    f"value ({collateral_value})."
                )
        else:
            errors.append(f"Unknown renewal mode: {command.mode!r}")

        if new_principal < Decimal("0"):
            errors.append("Computed new principal cannot be negative.")

        return LoanRenewalPreview(
            source_loan_id=loan.pk,
            mode=command.mode,
            outstanding_principal=outstanding,
            interest_due=interest_due,
            collateral_value=collateral_value,
            principal_paid=command.principal_paid,
            interest_paid=command.interest_paid,
            requested_extra_amount=command.requested_extra_amount,
            new_principal=max(new_principal, Decimal("0")),
            is_valid=len(errors) == 0,
            errors=errors,
        )

    def execute(self, command: LoanRenewalCommand) -> LoanRenewalResult:
        from django.core.exceptions import ValidationError as DjangoValidationError
        from moneyed import Money

        preview = self.preview(command)
        if not preview.is_valid:
            return LoanRenewalResult(
                success=False,
                message="Renewal validation failed: " + "; ".join(preview.errors),
                source_loan_id=command.source_loan_id,
            )

        try:
            with transaction.atomic():
                loan = GivenLoan.objects.select_for_update().get(pk=command.source_loan_id)
                warns = []
                workspace = getattr(
                    getattr(command.created_by, "profile", None),
                    "workspace",
                    None,
                )
                prefs = CompanyPreferences(workspace)

                if prefs.loan_catchup_on_renewal:
                    accrual_result = InterestAccrualService.execute(
                        InterestAccrualCommand(
                            loan=loan,
                            as_of_date=command.renewal_date,
                            trigger_source="RENEWAL",
                            created_by=command.created_by,
                            notes=f"Catch-up accrual before renewal of {loan.loan_id}",
                            post_to_accounting=True,
                        )
                    )
                    if not accrual_result.success:
                        warns.append(
                            f"Interest accrual catch-up failed before renewal: {accrual_result.message}"
                        )
                    else:
                        warns.extend(accrual_result.warnings)

                allowed_statuses = {
                    LoanLifecycleState.ACTIVE_CURRENT,
                    LoanLifecycleState.ACTIVE_OVERDUE,
                    LoanLifecycleState.ACTIVE_NPA,
                }
                if normalize_legacy_given_loan_status(loan.status) not in allowed_statuses:
                    return LoanRenewalResult(
                        success=False,
                        message=(
                            f"Loan {loan.loan_id} is in status '{loan.status}'. "
                            "Only active/disbursed loans can be renewed."
                        ),
                        source_loan_id=loan.pk,
                    )

                new_principal = preview.new_principal
                old_principal = loan.get_loan_amount

                payment_total = command.interest_paid + command.principal_paid
                if payment_total > Decimal("0"):
                    loan.create_payment(
                        amount=Money(payment_total, "INR"),
                        principal=Money(command.principal_paid, "INR"),
                        interest=Money(command.interest_paid, "INR"),
                        payment_method=command.payment_method,
                        reference_number=(
                            command.reference_number or f"RENEWAL-PAYMENT-{loan.pk}"
                        ),
                        description=f"Renewal payment for {loan.loan_id}",
                        payment_date=command.renewal_date,
                        created_by=command.created_by,
                    )

                new_loan = GivenLoan.objects.create(
                    borrower=loan.borrower,
                    series=loan.series,
                    loan_date=command.renewal_date,
                    tenure=loan.tenure,
                    status=LoanLifecycleState.DRAFT,
                    interest_type=loan.interest_type,
                    created_by=command.created_by,
                )

                scale = (new_principal / old_principal) if old_principal else Decimal("1")
                for item in loan.loanitems.all():
                    LoanItem.objects.create(
                        loan=new_loan,
                        item=item.item,
                        itemtype=item.itemtype,
                        quantity=item.quantity,
                        weight=item.weight,
                        purity=item.purity,
                        loanamount=round(item.loanamount * scale, 2),
                        interestrate=item.interestrate,
                        interest=round(item.interest * scale, 2),
                        itemdesc=item.itemdesc,
                    )

                source_flow = build_runtime_loan_flow(
                    loan,
                    command.created_by,
                    tenant=None,
                    transition_name="complete_renewal",
                )
                if source_flow.request_renewal.can_proceed():
                    source_flow.request_renewal(requested_by=command.created_by)
                source_flow.complete_renewal(
                    completed_by=command.created_by,
                    successor_loan_id=getattr(new_loan, "loan_id", None) or str(new_loan.pk),
                )

                new_flow = build_runtime_loan_flow(
                    new_loan,
                    command.created_by,
                    tenant=None,
                    transition_name="disburse_loan",
                )
                if hasattr(new_flow, "submit_for_approval") and new_flow.submit_for_approval.can_proceed():
                    new_flow.submit_for_approval(submitted_by=command.created_by)

                if hasattr(new_flow, "approve_loan") and new_flow.approve_loan.can_proceed():
                    new_flow.approve_loan(approved_by=command.created_by)

                if hasattr(new_flow, "disburse_loan") and new_flow.disburse_loan.can_proceed():
                    new_flow.disburse_loan(disbursed_by=command.created_by)

                try:
                    record_loan_disbursal(new_loan, command.created_by)
                except Exception as acc_exc:
                    logger.exception(
                        "Renewal disbursal accounting failed for new loan %s",
                        new_loan.pk,
                    )
                    warns.append(f"Loan renewed but disbursal accounting failed: {acc_exc}")

                LoanRenewal.objects.create(
                    source_loan=loan,
                    renewed_loan=new_loan,
                    mode=command.mode,
                    renewal_date=command.renewal_date,
                    interest_paid=command.interest_paid,
                    principal_paid=command.principal_paid,
                    requested_extra_amount=command.requested_extra_amount,
                    created_by=command.created_by,
                    notes=command.notes,
                )

                return LoanRenewalResult(
                    success=True,
                    message=(
                        f"Loan {loan.loan_id} renewed. "
                        f"New loan {new_loan.loan_id} created and disbursed."
                    ),
                    source_loan_id=loan.pk,
                    new_loan_id=new_loan.pk,
                    warnings=warns,
                )

        except (ValueError, DjangoValidationError) as exc:
            return LoanRenewalResult(
                success=False,
                message=str(exc),
                source_loan_id=command.source_loan_id,
            )
        except Exception as exc:
            logger.exception(
                "Unexpected error during loan renewal for source_loan_id=%s",
                command.source_loan_id,
            )
            return LoanRenewalResult(
                success=False,
                message=f"An unexpected error occurred: {exc}",
                source_loan_id=command.source_loan_id,
            )
