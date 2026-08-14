from dataclasses import dataclass, field as dc_field

from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.tenant_apps.girvi.flows import build_runtime_loan_flow
from apps.tenant_apps.girvi.lifecycle import V2_CLOSURE_STATUSES
from apps.tenant_apps.girvi.models import LoanLifecycleState
from apps.tenant_apps.girvi.models.custody_tracking import ItemCustodyStatus

from .accrual import InterestAccrualCommand, InterestAccrualService
from .payment import record_loan_release
from .preferences import (
    is_loan_catchup_on_release_enabled,
    is_loan_release_fail_closed_on_accrual_error_enabled,
)
from .release_settlement import (
    apply_release_settlement_snapshot,
    build_release_settlement_basis,
)


@dataclass
class ReleaseCreateCommand:
    loan: object
    created_by: object
    release_date: object
    released_by: object = None


@dataclass
class ReleaseCreatePreview:
    is_valid: bool
    loan: object | None = None
    loan_id: str = ""
    current_status: str = ""
    release_date: object | None = None
    released_by: object | None = None
    outstanding_amount: object | None = None
    warnings: list[str] = dc_field(default_factory=list)
    errors: list[str] = dc_field(default_factory=list)


@dataclass
class ReleaseCreateResult:
    success: bool
    message: str
    release: object | None = None
    payment: object | None = None
    payment_created: bool = False
    warnings: list[str] = dc_field(default_factory=list)
    errors: list[str] = dc_field(default_factory=list)
    stage_outcomes: dict[str, str] = dc_field(default_factory=dict)
    failed_stage: str = ""
    stage_errors: dict[str, list[str]] = dc_field(default_factory=dict)
    stage_warnings: dict[str, list[str]] = dc_field(default_factory=dict)
    settlement_basis: object | None = None


class ReleaseLifecycleService:
    """Command-style release creation for GivenLoan lifecycle writes."""

    STAGE_READINESS = "readiness_checked"
    STAGE_ACCRUAL = "accrual_catchup"
    STAGE_CUSTODY = "custody_transferred"
    STAGE_RELEASE_SAVE = "release_saved"
    STAGE_POSTING = "posting_completed"
    STAGE_CLOSURE = "closure_completed"

    RELEASE_SETTLEMENT_STATUSES = {
        LoanLifecycleState.ACTIVE_CURRENT,
        LoanLifecycleState.ACTIVE_OVERDUE,
        LoanLifecycleState.ACTIVE_NPA,
        LoanLifecycleState.CLOSURE_PENDING,
    }

    STAGES = (
        STAGE_READINESS,
        STAGE_ACCRUAL,
        STAGE_CUSTODY,
        STAGE_RELEASE_SAVE,
        STAGE_POSTING,
        STAGE_CLOSURE,
    )

    @classmethod
    def _new_stage_outcomes(cls):
        return {stage: "not_started" for stage in cls.STAGES}

    @staticmethod
    def _existing_release(loan):
        try:
            return getattr(loan, "release", None)
        except Exception:
            return None

    @staticmethod
    def _exception_messages(exc):
        return list(getattr(exc, "messages", None) or [str(exc)])

    @staticmethod
    def _release_items_to_customer(loan, created_by):
        loan_items = getattr(loan, "loanitems", None)
        if loan_items is None:
            return

        errors = []
        for item in loan_items.all():
            release_to_customer = getattr(item, "release_to_customer", None)
            if not callable(release_to_customer):
                continue

            try:
                release_to_customer(user=created_by)
            except Exception as exc:
                if (
                    getattr(item, "custody_status", None)
                    == ItemCustodyStatus.WITH_CUSTOMER
                ):
                    continue

                item_label = getattr(item, "itemdesc", None) or str(item)
                for message in ReleaseLifecycleService._exception_messages(exc):
                    errors.append(f"{item_label}: {message}")

        if errors:
            raise ValidationError(
                ["Cannot release loan because collateral custody update failed."]
                + errors
            )

    @staticmethod
    def preview(command: ReleaseCreateCommand) -> ReleaseCreatePreview:
        errors = []
        warnings = []
        loan = getattr(command, "loan", None)
        created_by = getattr(command, "created_by", None)

        if not loan:
            errors.append("Loan is required for release creation.")

        if not created_by:
            errors.append("created_by is required for release creation.")

        existing_release = ReleaseLifecycleService._existing_release(loan) if loan else None
        if existing_release is not None:
            release_id = getattr(existing_release, "release_id", None) or getattr(
                existing_release, "pk", ""
            )
            errors.append(
                f"Loan {getattr(loan, 'loan_id', '')} already has a release"
                f"{f' ({release_id})' if release_id else ''}."
            )

        outstanding_amount = None
        if loan and existing_release is None:
            from apps.tenant_apps.girvi.selectors import build_loan_settlement_balance

            outstanding_amount = build_loan_settlement_balance(loan).total_outstanding
        if outstanding_amount is not None and outstanding_amount <= 0:
            warnings.append(
                "Loan has no outstanding balance. Release accounting may be skipped."
            )

        if loan and created_by and existing_release is None:
            current_status = getattr(loan, "status", "")
            can_release = current_status in ReleaseLifecycleService.RELEASE_SETTLEMENT_STATUSES

            if not can_release:
                errors.append(
                    f"Loan {loan.loan_id} cannot be released in status {loan.status}."
                )

        return ReleaseCreatePreview(
            is_valid=len(errors) == 0,
            loan=loan,
            loan_id=getattr(loan, "loan_id", "") if loan else "",
            current_status=getattr(loan, "status", "") if loan else "",
            release_date=getattr(command, "release_date", None),
            released_by=getattr(command, "released_by", None),
            outstanding_amount=outstanding_amount,
            warnings=warnings,
            errors=errors,
        )

    @staticmethod
    def execute(command: ReleaseCreateCommand) -> ReleaseCreateResult:
        stage_outcomes = ReleaseLifecycleService._new_stage_outcomes()
        stage_errors: dict[str, list[str]] = {}
        stage_warnings: dict[str, list[str]] = {}

        preview = ReleaseLifecycleService.preview(command)
        if not preview.is_valid:
            stage_outcomes[ReleaseLifecycleService.STAGE_READINESS] = "failed"
            stage_errors[ReleaseLifecycleService.STAGE_READINESS] = list(preview.errors)
            return ReleaseCreateResult(
                success=False,
                message="; ".join(preview.errors),
                warnings=preview.warnings,
                errors=preview.errors,
                stage_outcomes=stage_outcomes,
                failed_stage=ReleaseLifecycleService.STAGE_READINESS,
                stage_errors=stage_errors,
                stage_warnings=stage_warnings,
            )

        stage_outcomes[ReleaseLifecycleService.STAGE_READINESS] = "completed"

        Release = apps.get_model("girvi", "Release")
        created_by = command.created_by
        workspace = getattr(getattr(created_by, "profile", None), "workspace", None)
        warnings = list(preview.warnings)
        current_stage = ""

        try:
            with transaction.atomic():
                current_stage = ReleaseLifecycleService.STAGE_ACCRUAL
                if is_loan_catchup_on_release_enabled(workspace):
                    fail_closed_on_accrual_error = bool(
                        is_loan_release_fail_closed_on_accrual_error_enabled(workspace)
                    )
                    accrual_result = InterestAccrualService.execute(
                        InterestAccrualCommand(
                            loan=command.loan,
                            as_of_date=command.release_date,
                            trigger_source="RELEASE",
                            created_by=created_by,
                            notes=f"Catch-up accrual before release of {command.loan.loan_id}",
                            post_to_accounting=True,
                        )
                    )
                    if not accrual_result.success:
                        issue_text = (
                            f"Interest accrual catch-up failed before release: {accrual_result.message}"
                        )
                        if fail_closed_on_accrual_error:
                            raise ValidationError(issue_text)
                        warnings.append(issue_text)
                        stage_warnings.setdefault(current_stage, []).append(issue_text)
                        stage_outcomes[current_stage] = "warning"
                    else:
                        accrual_warnings = list(accrual_result.warnings or [])
                        warnings.extend(accrual_warnings)
                        if accrual_warnings:
                            stage_warnings[current_stage] = accrual_warnings
                            stage_outcomes[current_stage] = "warning"
                        else:
                            stage_outcomes[current_stage] = "completed"
                else:
                    stage_outcomes[current_stage] = "skipped"

                flow = build_runtime_loan_flow(
                    command.loan,
                    created_by,
                    workspace,
                )
                release = Release(
                    loan=command.loan,
                    release_date=command.release_date,
                    released_by=command.released_by,
                    created_by=created_by,
                )
                settlement_basis = build_release_settlement_basis(
                    command.loan,
                    command.release_date,
                )
                apply_release_settlement_snapshot(release, settlement_basis)
                if not settlement_basis.used_accrual_rows:
                    compatibility_code = getattr(
                        settlement_basis,
                        "compatibility_code",
                        "SELECTOR_COMPATIBILITY",
                    )
                    compatibility_reason = getattr(
                        settlement_basis,
                        "compatibility_reason",
                        "Selector compatibility settlement was required.",
                    )
                    issue_text = (
                        "Final release settlement used selector compatibility basis "
                        f"({compatibility_code}): {compatibility_reason}"
                    )
                    warnings.append(issue_text)
                    stage_warnings.setdefault(
                        ReleaseLifecycleService.STAGE_ACCRUAL,
                        [],
                    ).append(issue_text)
                    if (
                        stage_outcomes.get(ReleaseLifecycleService.STAGE_ACCRUAL)
                        == "completed"
                    ):
                        stage_outcomes[ReleaseLifecycleService.STAGE_ACCRUAL] = "warning"
                current_stage = ReleaseLifecycleService.STAGE_CUSTODY
                ReleaseLifecycleService._release_items_to_customer(
                    command.loan,
                    created_by,
                )
                stage_outcomes[current_stage] = "completed"

                current_stage = ReleaseLifecycleService.STAGE_RELEASE_SAVE
                release.save()
                stage_outcomes[current_stage] = "completed"

                current_stage = ReleaseLifecycleService.STAGE_POSTING
                release_posting = record_loan_release(release, created_by=created_by)
                if isinstance(release_posting, tuple):
                    payment, payment_created = release_posting
                else:
                    payment = release_posting
                    payment_created = bool(release_posting)
                stage_outcomes[current_stage] = "completed"

                current_status = getattr(command.loan, "status", "")
                use_v2_closure = current_status in V2_CLOSURE_STATUSES
                deliver = getattr(flow, "deliver", None)
                complete_closure = getattr(flow, "complete_closure", None)
                request_closure = getattr(flow, "request_closure", None)

                current_stage = ReleaseLifecycleService.STAGE_CLOSURE
                if use_v2_closure:
                    if request_closure is not None and request_closure.can_proceed():
                        if callable(request_closure):
                            request_closure(requested_by=created_by)

                    if not (complete_closure and complete_closure.can_proceed()):
                        raise ValidationError(
                            f"Loan {command.loan.loan_id} cannot complete closure in status {command.loan.status}."
                        )

                    if callable(complete_closure):
                        complete_closure(
                            completed_by=created_by,
                            release_id=getattr(release, "release_id", None),
                        )
                elif deliver is not None and getattr(deliver, "can_proceed", lambda: False)():
                    if callable(deliver):
                        deliver(
                            created_by=created_by,
                            released_by=command.released_by,
                            release_date=command.release_date,
                        )
                else:
                    raise ValidationError(
                        f"Loan {command.loan.loan_id} has no release-capable transition flow."
                    )
                stage_outcomes[current_stage] = "completed"

            message = f"Loan {command.loan.loan_id} released successfully."
            if payment is None:
                warnings.append(
                    "Release created without accounting receipt because no outstanding amount remained."
                )
                stage_outcomes[ReleaseLifecycleService.STAGE_POSTING] = "skipped"
            elif payment_created:
                payment_id = getattr(payment, "payment_id", None)
                if payment_id:
                    message = (
                        f"Loan {command.loan.loan_id} released successfully. "
                        f"Receipt {payment_id} posted."
                    )
            else:
                payment_id = getattr(payment, "payment_id", None)
                if payment_id:
                    warnings.append(
                        f"Release receipt already existed as {payment_id}."
                    )

            return ReleaseCreateResult(
                success=True,
                message=message,
                release=release,
                payment=payment,
                payment_created=bool(payment_created),
                warnings=warnings,
                stage_outcomes=stage_outcomes,
                stage_errors=stage_errors,
                stage_warnings=stage_warnings,
                settlement_basis=settlement_basis,
            )
        except ValidationError as exc:
            error_list = list(getattr(exc, "messages", None) or [str(exc)])
            if current_stage:
                if stage_outcomes.get(current_stage) == "not_started":
                    stage_outcomes[current_stage] = "failed"
                stage_errors[current_stage] = error_list
            return ReleaseCreateResult(
                success=False,
                message="; ".join(error_list),
                warnings=preview.warnings,
                errors=error_list,
                stage_outcomes=stage_outcomes,
                failed_stage=current_stage,
                stage_errors=stage_errors,
                stage_warnings=stage_warnings,
            )
        except Exception as exc:
            if current_stage:
                if stage_outcomes.get(current_stage) == "not_started":
                    stage_outcomes[current_stage] = "failed"
                stage_errors[current_stage] = [str(exc)]
            return ReleaseCreateResult(
                success=False,
                message=f"An error occurred while creating release: {exc}",
                warnings=preview.warnings,
                errors=[str(exc)],
                stage_outcomes=stage_outcomes,
                failed_stage=current_stage,
                stage_errors=stage_errors,
                stage_warnings=stage_warnings,
            )

    @staticmethod
    def create_release(*, loan, created_by, release_date, released_by=None):
        result = ReleaseLifecycleService.execute(
            ReleaseCreateCommand(
                loan=loan,
                created_by=created_by,
                release_date=release_date,
                released_by=released_by,
            )
        )
        if not result.success:
            raise ValidationError(result.errors or [result.message])
        return result.release
