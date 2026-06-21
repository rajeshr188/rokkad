import logging
from dataclasses import dataclass, field as dc_field
from datetime import datetime
from decimal import Decimal

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.tenant_apps.girvi.models.loan_item import LoanItem
from apps.tenant_apps.girvi.models.loan_refactored import GivenLoan, LoanLifecycleState
from .id_generation import LoanIDGenerator

logger = logging.getLogger(__name__)


class _LoanChangeLogProxy:
    @property
    def objects(self):
        return apps.get_model("girvi", "LoanChangeLog").objects


LoanChangeLog = _LoanChangeLogProxy()


@dataclass
class LoanItemCreateInput:
    itemdesc: str = ""
    itemtype: str = "Gold"
    quantity: int = 1
    weight: object | None = None
    purity: object | None = Decimal("75")
    loanamount: object | None = None
    interestrate: object | None = None
    item: object | None = None

    def has_user_input(self) -> bool:
        return any(
            value not in (None, "")
            for value in (
                self.item,
                self.itemdesc,
                self.weight,
                self.loanamount,
                self.interestrate,
            )
        )


@dataclass
class LoanCreateCommand:
    borrower: object
    series: object
    loan_date: object
    tenure: int
    interest_type: str
    created_by: object
    borrower_party: object | None = None
    loan_id: str = ""
    initial_items: list[LoanItemCreateInput] = dc_field(default_factory=list)


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
    initial_item_count: int = 0
    initial_item_total: object | None = None
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
    def _to_decimal(value, *, default=Decimal("0")):
        if value in (None, ""):
            return default
        return Decimal(str(value))

    @staticmethod
    def _normalize_initial_item_input(item):
        if isinstance(item, LoanItemCreateInput):
            return item
        if isinstance(item, dict):
            return LoanItemCreateInput(
                item=item.get("item"),
                itemdesc=item.get("itemdesc") or "",
                itemtype=item.get("itemtype") or "Gold",
                quantity=item.get("quantity") or 1,
                weight=item.get("weight"),
                purity=item.get("purity") if item.get("purity") not in (None, "") else Decimal("75"),
                loanamount=item.get("loanamount"),
                interestrate=item.get("interestrate"),
            )
        raise ValidationError("Invalid initial loan item payload.")

    @staticmethod
    def _get_initial_items(initial_items):
        normalized_items = []
        for item in initial_items or []:
            candidate = LoanCreationService._normalize_initial_item_input(item)
            if candidate.has_user_input():
                normalized_items.append(candidate)
        return normalized_items

    @staticmethod
    def _create_initial_items(loan, initial_items):
        created_items = []
        for index, item in enumerate(
            LoanCreationService._get_initial_items(initial_items), start=1
        ):
            try:
                quantity = int(item.quantity or 1)
            except (TypeError, ValueError) as exc:
                raise ValidationError(f"Initial item {index}: quantity must be a whole number.") from exc

            weight = LoanCreationService._to_decimal(item.weight, default=None)
            purity = LoanCreationService._to_decimal(item.purity, default=Decimal("75"))
            loanamount = LoanCreationService._to_decimal(item.loanamount, default=None)
            interestrate = LoanCreationService._to_decimal(item.interestrate, default=None)

            if not (item.itemdesc or "").strip():
                raise ValidationError(f"Initial item {index}: description is required.")
            if quantity <= 0:
                raise ValidationError(f"Initial item {index}: quantity must be greater than zero.")
            if weight is None or weight <= 0:
                raise ValidationError(f"Initial item {index}: weight must be greater than zero.")
            if purity is None or purity <= 0:
                raise ValidationError(f"Initial item {index}: purity must be greater than zero.")
            if loanamount is None or loanamount <= 0:
                raise ValidationError(f"Initial item {index}: loan amount must be greater than zero.")
            if interestrate is None or interestrate < 0:
                raise ValidationError(f"Initial item {index}: interest rate cannot be negative.")

            loan_item = LoanItem(
                loan=loan,
                item=item.item,
                itemdesc=item.itemdesc.strip(),
                itemtype=item.itemtype or "Gold",
                quantity=quantity,
                weight=weight,
                purity=purity,
                loanamount=loanamount,
                interestrate=interestrate,
            )
            loan_item.full_clean()
            loan_item.save()
            created_items.append(loan_item)

        return created_items

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

        initial_items = LoanCreationService._get_initial_items(command.initial_items)
        initial_item_total = sum(
            (
                LoanCreationService._to_decimal(item.loanamount)
                for item in initial_items
            ),
            Decimal("0"),
        )

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
            initial_item_count=len(initial_items),
            initial_item_total=initial_item_total if initial_items else None,
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
            target=str(getattr(loan, "status", LoanLifecycleState.DRAFT)),
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
                    borrower_party=command.borrower_party,
                    series=command.series,
                    loan_date=preview.loan_date,
                    tenure=command.tenure,
                    status=LoanLifecycleState.DRAFT,
                    interest_type=command.interest_type,
                    created_by=command.created_by,
                )
                if command.loan_id:
                    loan.loan_id = command.loan_id
                loan.save()
                LoanCreationService._create_initial_items(loan, command.initial_items)
                LoanCreationService._record_creation_audit(loan, command.created_by)

            return LoanCreateResult(
                success=True,
                message=f"Created Loan: {loan.loan_id}",
                loan=loan,
            )
        except ValidationError as exc:
            error_list = list(getattr(exc, "messages", None) or [str(exc)])
            return LoanCreateResult(
                success=False,
                message="; ".join(error_list),
                errors=error_list,
            )
        except Exception as exc:
            logger.exception("Unexpected error during loan creation")
            return LoanCreateResult(
                success=False,
                message=f"An error occurred while creating loan: {exc}",
                errors=[str(exc)],
            )
