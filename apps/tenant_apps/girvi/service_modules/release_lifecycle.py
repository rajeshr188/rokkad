from dataclasses import dataclass, field as dc_field

from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import transaction


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


class ReleaseLifecycleService:
    """Command-style release creation for GivenLoan lifecycle writes."""

    @staticmethod
    def preview(command: ReleaseCreateCommand) -> ReleaseCreatePreview:
        from apps.tenant_apps.girvi.flows import build_runtime_loan_flow

        errors = []
        warnings = []
        loan = getattr(command, "loan", None)
        created_by = getattr(command, "created_by", None)

        if not loan:
            errors.append("Loan is required for release creation.")

        if not created_by:
            errors.append("created_by is required for release creation.")

        outstanding_amount = getattr(loan, "total_due", None) if loan else None
        if outstanding_amount is not None and outstanding_amount <= 0:
            warnings.append(
                "Loan has no outstanding balance. Release accounting may be skipped."
            )

        if loan and created_by:
            workspace = getattr(getattr(created_by, "profile", None), "workspace", None)
            flow = build_runtime_loan_flow(
                loan,
                created_by,
                workspace,
            )
            can_release = False
            use_v2_closure = str(getattr(loan, "status", "")) in {
                "ActiveCurrent",
                "ActiveOverdue",
                "ActiveNPA",
                "ClosurePending",
            }
            deliver = getattr(flow, "deliver", None)
            request_closure = getattr(flow, "request_closure", None)
            complete_closure = getattr(flow, "complete_closure", None)

            if use_v2_closure:
                if request_closure and request_closure.can_proceed():
                    can_release = True
                elif complete_closure and complete_closure.can_proceed():
                    can_release = True
            elif deliver and deliver.can_proceed():
                can_release = True

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
        from apps.tenant_apps.girvi.flows import build_runtime_loan_flow
        from apps.tenant_apps.girvi.service_modules.payment import record_loan_release

        preview = ReleaseLifecycleService.preview(command)
        if not preview.is_valid:
            return ReleaseCreateResult(
                success=False,
                message="; ".join(preview.errors),
                warnings=preview.warnings,
                errors=preview.errors,
            )

        Release = apps.get_model("girvi", "Release")
        created_by = command.created_by
        workspace = getattr(getattr(created_by, "profile", None), "workspace", None)

        try:
            with transaction.atomic():
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
                release.save()

                use_v2_closure = str(getattr(command.loan, "status", "")) in {
                    "ActiveCurrent",
                    "ActiveOverdue",
                    "ActiveNPA",
                    "ClosurePending",
                }
                deliver = getattr(flow, "deliver", None)
                complete_closure = getattr(flow, "complete_closure", None)
                request_closure = getattr(flow, "request_closure", None)

                if use_v2_closure:
                    if request_closure is not None and request_closure.can_proceed():
                        request_closure(requested_by=created_by)

                    if not (complete_closure and complete_closure.can_proceed()):
                        raise ValidationError(
                            f"Loan {command.loan.loan_id} cannot complete closure in status {command.loan.status}."
                        )

                    complete_closure(
                        completed_by=created_by,
                        release_id=getattr(release, "release_id", None),
                    )
                elif deliver is not None:
                    deliver(
                        created_by=created_by,
                        released_by=command.released_by,
                        release_date=command.release_date,
                    )
                else:
                    raise ValidationError(
                        f"Loan {command.loan.loan_id} has no release-capable transition flow."
                    )

                release_posting = record_loan_release(release, created_by=created_by)
                if isinstance(release_posting, tuple):
                    payment, payment_created = release_posting
                else:
                    payment = release_posting
                    payment_created = bool(release_posting)

            warnings = list(preview.warnings)
            message = f"Loan {command.loan.loan_id} released successfully."
            if payment is None:
                warnings.append(
                    "Release created without accounting receipt because no outstanding amount remained."
                )
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
            )
        except ValidationError as exc:
            error_list = list(getattr(exc, "messages", None) or [str(exc)])
            return ReleaseCreateResult(
                success=False,
                message="; ".join(error_list),
                warnings=preview.warnings,
                errors=error_list,
            )
        except Exception as exc:
            return ReleaseCreateResult(
                success=False,
                message=f"An error occurred while creating release: {exc}",
                warnings=preview.warnings,
                errors=[str(exc)],
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
