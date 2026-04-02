import logging
from dataclasses import dataclass, field as dc_field
from datetime import datetime

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.tenant_apps.girvi.models.loan_refactored import GivenLoan
from .id_generation import LoanIDGenerator

logger = logging.getLogger(__name__)


class _LoanChangeLogProxy:
    @property
    def objects(self):
        return apps.get_model("girvi", "LoanChangeLog").objects


LoanChangeLog = _LoanChangeLogProxy()


@dataclass
class LoanCreateCommand:
    borrower: object
    series: object
    loan_date: object
    tenure: int
    interest_type: str
    created_by: object
    loan_id: str = ""


@dataclass
class LoanCreatePreview:
    is_valid: bool
    expected_loan_id: str = ""
    borrower: object | None = None
    series: object | None = None
    loan_date: object | None = None
    tenure: int | None = None
    interest_type: str = ""
    borrower_credit_limit: object | None = None
    borrower_current_balance: object | None = None
    borrower_available_credit: object | None = None
    warnings: list[str] = dc_field(default_factory=list)
    errors: list[str] = dc_field(default_factory=list)


@dataclass
class LoanCreateResult:
    success: bool
    message: str
    loan: object | None = None
    errors: list[str] = dc_field(default_factory=list)


class LoanCreationService:
    """Command-style service for creating new GivenLoan records."""

    @staticmethod
    def _normalize_loan_date(loan_date):
        if not isinstance(loan_date, datetime):
            return loan_date
        if timezone.is_naive(loan_date):
            return timezone.make_aware(loan_date, timezone.get_current_timezone())
        return loan_date

    @staticmethod
    def _get_borrower_account_summary(borrower):
        if not borrower:
            return None, None, None

        try:
            account = borrower.account
        except (AttributeError, ObjectDoesNotExist):
            return None, None, None

        credit_limit = getattr(account, "credit_limit", None)

        try:
            current_balance = account.get_current_balance()
        except Exception as exc:
            logger.warning("Could not read borrower current balance: %s", exc)
            current_balance = None

        try:
            available_credit = account.get_available_credit()
        except Exception as exc:
            logger.warning("Could not read borrower available credit: %s", exc)
            available_credit = None

        return credit_limit, current_balance, available_credit

    @staticmethod
    def preview(command: LoanCreateCommand) -> LoanCreatePreview:
        errors = []
        warnings = []

        if not command.borrower:
            errors.append("Borrower is required for loan creation.")

        if not command.series:
            errors.append("Series is required for loan creation.")
        elif not getattr(command.series, "is_active", False):
            errors.append(f"Cannot create loan in inactive series '{command.series}'.")

        normalized_loan_date = LoanCreationService._normalize_loan_date(command.loan_date)
        if isinstance(normalized_loan_date, datetime) and normalized_loan_date > timezone.now():
            errors.append("Loan date cannot be in the future.")

        expected_loan_id = command.loan_id or ""
        if not expected_loan_id and command.series and getattr(command.series, "is_active", False):
            try:
                expected_loan_id = LoanIDGenerator.generate(command.series)
            except Exception as exc:
                logger.warning("Could not preview next loan ID: %s", exc)
                warnings.append(f"Could not preview next loan ID: {exc}")

        (
            borrower_credit_limit,
            borrower_current_balance,
            borrower_available_credit,
        ) = LoanCreationService._get_borrower_account_summary(command.borrower)

        return LoanCreatePreview(
            is_valid=len(errors) == 0,
            expected_loan_id=expected_loan_id,
            borrower=command.borrower,
            series=command.series,
            loan_date=normalized_loan_date,
            tenure=command.tenure,
            interest_type=command.interest_type,
            borrower_credit_limit=borrower_credit_limit,
            borrower_current_balance=borrower_current_balance,
            borrower_available_credit=borrower_available_credit,
            warnings=warnings,
            errors=errors,
        )

    @staticmethod
    def _record_creation_audit(loan, created_by):
        content_type = ContentType.objects.get_for_model(loan.__class__)
        LoanChangeLog.objects.create(
            content_type=content_type,
            object_id=loan.pk,
            source="Initial",
            target="Created",
            author=created_by,
            diff="",
            metadata={
                "created_via": "LoanCreationService",
                "borrower_id": getattr(getattr(loan, "borrower", None), "pk", None),
                "series_id": getattr(getattr(loan, "series", None), "pk", None),
            },
        )

    @staticmethod
    def execute(command: LoanCreateCommand) -> LoanCreateResult:
        if not command.created_by:
            return LoanCreateResult(
                success=False,
                message="created_by is required for loan creation.",
                errors=["created_by is required for loan creation."],
            )

        preview = LoanCreationService.preview(command)
        if not preview.is_valid:
            return LoanCreateResult(
                success=False,
                message="; ".join(preview.errors),
                errors=preview.errors,
            )

        try:
            with transaction.atomic():
                loan = GivenLoan(
                    borrower=command.borrower,
                    series=command.series,
                    loan_date=preview.loan_date,
                    tenure=command.tenure,
                    interest_type=command.interest_type,
                    created_by=command.created_by,
                )
                if command.loan_id:
                    loan.loan_id = command.loan_id
                loan.save()
                LoanCreationService._record_creation_audit(loan, command.created_by)

            return LoanCreateResult(
                success=True,
                message=f"Created Loan: {loan.loan_id}",
                loan=loan,
            )
        except ValidationError as exc:
            return LoanCreateResult(
                success=False,
                message=str(exc),
                errors=[str(exc)],
            )
        except Exception as exc:
            logger.exception("Unexpected error during loan creation")
            return LoanCreateResult(
                success=False,
                message=f"An error occurred while creating loan: {exc}",
                errors=[str(exc)],
            )
