import logging
from dataclasses import dataclass, field as dc_field
from datetime import date, datetime, time
from decimal import Decimal, ROUND_HALF_UP

from dateutil.relativedelta import relativedelta
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from moneyed import Money

from apps.tenant_apps.dea.models import (
    JournalEntryLineItem,
    JournalEntryVoucher,
    VoucherType,
)
from apps.tenant_apps.dea.posting.engine import DjangoPostingEngine
from apps.tenant_apps.dea.posting.resolver import get_ledger_id_by_key
from apps.tenant_apps.dea.services.post_doc import create_and_post_voucher_for_doc
from apps.tenant_apps.girvi.models.accrual import (
    AccrualStatus,
    AccrualTriggerSource,
    LoanInterestAccrual,
)

logger = logging.getLogger(__name__)
MONEY_PLACES = Decimal("0.01")


@dataclass
class InterestAccrualCommand:
    loan: object
    as_of_date: object = None
    trigger_source: str = AccrualTriggerSource.MANUAL
    created_by: object | None = None
    notes: str = ""
    post_to_accounting: bool = False


@dataclass
class InterestAccrualPeriod:
    period_index: int
    period_start: date
    period_end: date
    accrued_amount: Decimal
    base_interest_snapshot: Decimal


@dataclass
class InterestAccrualPreview:
    is_valid: bool
    loan: object | None = None
    loan_id: str = ""
    as_of_date: date | None = None
    effective_end_date: date | None = None
    base_interest_amount: Decimal = Decimal("0.00")
    completed_periods: int = 0
    existing_periods: int = 0
    pending_periods: int = 0
    gross_accrued_amount: Decimal = Decimal("0.00")
    newly_accrued_amount: Decimal = Decimal("0.00")
    periods_to_create: list[InterestAccrualPeriod] = dc_field(default_factory=list)
    warnings: list[str] = dc_field(default_factory=list)
    errors: list[str] = dc_field(default_factory=list)


@dataclass
class InterestAccrualResult:
    success: bool
    message: str
    loan: object | None = None
    as_of_date: date | None = None
    accruals: list[object] = dc_field(default_factory=list)
    created_count: int = 0
    total_created_amount: Decimal = Decimal("0.00")
    journal_entry_voucher: object | None = None
    accounting_voucher: object | None = None
    journal_entry: object | None = None
    warnings: list[str] = dc_field(default_factory=list)
    errors: list[str] = dc_field(default_factory=list)


class InterestAccrualService:
    """Create persistent monthly accrual rows for completed GivenLoan interest periods."""

    @staticmethod
    def _round_money(value) -> Decimal:
        return Decimal(str(value or 0)).quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)

    @staticmethod
    def _post_accrual_batch_to_accounting(command, preview, created_rows):
        total_amount = InterestAccrualService._round_money(
            sum((getattr(row, "accrued_amount", Decimal("0.00")) for row in created_rows), Decimal("0.00"))
        )
        if total_amount <= 0:
            return None, None, None

        interest_receivable_id = get_ledger_id_by_key("INTEREST_RECEIVABLE")
        interest_income_id = get_ledger_id_by_key("INTEREST_INCOME")
        effective_date = preview.effective_end_date or preview.as_of_date or timezone.localdate()

        accrual_doc = JournalEntryVoucher.objects.create(
            je_date=effective_date,
            entry_type="ACCRUAL",
            description=(
                f"Loan interest accrual for {preview.loan_id} through {effective_date}"
            ),
            memo="LOAN_INTEREST_ACCRUAL",
            reference=f"LOAN-ACCRUAL:{getattr(command.loan, 'pk', 'new')}:{effective_date.isoformat()}",
            total_debit=Money(total_amount, "INR"),
            total_credit=Money(total_amount, "INR"),
            reviewed_by=command.created_by,
            reviewed_at=timezone.now() if command.created_by else None,
            created_by=command.created_by,
            updated_by=command.created_by,
            auto_post_to_accounting=False,
        )
        JournalEntryLineItem.objects.bulk_create(
            [
                JournalEntryLineItem(
                    journal_entry=accrual_doc,
                    line_number=1,
                    ledger_id=interest_receivable_id,
                    ledger_name="INTEREST_RECEIVABLE",
                    side="DR",
                    amount=Money(total_amount, "INR"),
                    description=f"Interest receivable recognition for {preview.loan_id}",
                ),
                JournalEntryLineItem(
                    journal_entry=accrual_doc,
                    line_number=2,
                    ledger_id=interest_income_id,
                    ledger_name="INTEREST_INCOME",
                    side="CR",
                    amount=Money(total_amount, "INR"),
                    description=f"Interest income recognition for {preview.loan_id}",
                ),
            ]
        )

        VoucherType.objects.get_or_create(
            name=accrual_doc.get_voucher_type(),
            defaults={"description": "System-posted loan interest accrual"},
        )
        accounting_voucher, journal_entry = create_and_post_voucher_for_doc(
            doc=accrual_doc,
            user=command.created_by,
            voucher_type_input=accrual_doc.get_voucher_type(),
            engine=DjangoPostingEngine(),
        )

        for row in created_rows:
            update_fields = []
            if getattr(row, "status", None) != AccrualStatus.POSTED:
                row.status = AccrualStatus.POSTED
                update_fields.append("status")
            if getattr(row, "journal_entry_voucher", None) != accrual_doc:
                row.journal_entry_voucher = accrual_doc
                update_fields.append("journal_entry_voucher")
            if update_fields and hasattr(row, "save"):
                row.save(update_fields=update_fields)

        return accrual_doc, accounting_voucher, journal_entry

    @staticmethod
    def _normalize_datetime(value):
        if isinstance(value, datetime):
            if timezone.is_naive(value):
                return timezone.make_aware(value, timezone.get_current_timezone())
            return timezone.localtime(value)
        if isinstance(value, date):
            return timezone.make_aware(
                datetime.combine(value, time.max),
                timezone.get_current_timezone(),
            )
        raise ValidationError("Invalid date/datetime value supplied for interest accrual.")

    @staticmethod
    def _normalize_as_of_date(value):
        if value in (None, ""):
            return timezone.localdate()
        if isinstance(value, datetime):
            return InterestAccrualService._normalize_datetime(value).date()
        if isinstance(value, date):
            return value
        raise ValidationError("as_of_date must be a valid date or datetime.")

    @staticmethod
    def _get_effective_end_datetime(loan, as_of_date: date):
        effective_end = InterestAccrualService._normalize_datetime(as_of_date)
        release = getattr(loan, "release", None)
        release_date = getattr(release, "release_date", None)
        if release_date:
            release_end = InterestAccrualService._normalize_datetime(release_date)
            if release_end < effective_end:
                effective_end = release_end
        return effective_end

    @staticmethod
    def _get_existing_period_keys(loan) -> set[tuple[date, date]]:
        if not getattr(loan, "pk", None):
            return set()

        related_manager = getattr(loan, "interest_accruals", None)
        if related_manager is None:
            return set()

        try:
            return set(related_manager.values_list("period_start", "period_end"))
        except Exception as exc:
            logger.warning("Could not inspect existing interest accruals for loan %s: %s", getattr(loan, "loan_id", None), exc)
            return set()

    @staticmethod
    def preview(command: InterestAccrualCommand) -> InterestAccrualPreview:
        errors: list[str] = []
        warnings: list[str] = []
        loan = getattr(command, "loan", None)

        if not loan:
            errors.append("Loan is required for interest accrual.")
            return InterestAccrualPreview(is_valid=False, errors=errors)

        try:
            as_of_date = InterestAccrualService._normalize_as_of_date(
                getattr(command, "as_of_date", None)
            )
        except ValidationError as exc:
            return InterestAccrualPreview(
                is_valid=False,
                loan=loan,
                loan_id=getattr(loan, "loan_id", ""),
                errors=list(getattr(exc, "messages", None) or [str(exc)]),
            )

        if as_of_date > timezone.localdate():
            errors.append("Interest accrual cannot be previewed for a future date.")

        loan_date = getattr(loan, "loan_date", None)
        if loan_date is None:
            errors.append("Loan has no loan_date; interest accrual cannot be calculated.")

        base_interest_amount = InterestAccrualService._round_money(
            getattr(loan, "get_interest_amount", Decimal("0"))
        )
        if base_interest_amount <= 0:
            warnings.append(
                f"Loan {getattr(loan, 'loan_id', '')} has zero base interest to accrue."
            )

        if errors:
            return InterestAccrualPreview(
                is_valid=False,
                loan=loan,
                loan_id=getattr(loan, "loan_id", ""),
                as_of_date=as_of_date,
                base_interest_amount=base_interest_amount,
                warnings=warnings,
                errors=errors,
            )

        from apps.tenant_apps.girvi.services import InterestCalculationService

        loan_start = InterestAccrualService._normalize_datetime(loan_date)
        effective_end_dt = InterestAccrualService._get_effective_end_datetime(loan, as_of_date)
        completed_periods = InterestCalculationService.months_between(loan_start, effective_end_dt)

        if completed_periods <= 0:
            warnings.append(
                f"Loan {getattr(loan, 'loan_id', '')} has no completed interest periods as of {as_of_date}."
            )

        existing_keys = InterestAccrualService._get_existing_period_keys(loan)
        periods_to_create: list[InterestAccrualPeriod] = []

        for period_index in range(1, completed_periods + 1):
            period_start = (loan_start + relativedelta(months=period_index - 1)).date()
            period_end = (loan_start + relativedelta(months=period_index)).date()
            if (period_start, period_end) in existing_keys:
                continue
            periods_to_create.append(
                InterestAccrualPeriod(
                    period_index=period_index,
                    period_start=period_start,
                    period_end=period_end,
                    accrued_amount=base_interest_amount,
                    base_interest_snapshot=base_interest_amount,
                )
            )

        return InterestAccrualPreview(
            is_valid=True,
            loan=loan,
            loan_id=getattr(loan, "loan_id", ""),
            as_of_date=as_of_date,
            effective_end_date=effective_end_dt.date(),
            base_interest_amount=base_interest_amount,
            completed_periods=completed_periods,
            existing_periods=len(existing_keys),
            pending_periods=len(periods_to_create),
            gross_accrued_amount=InterestAccrualService._round_money(
                base_interest_amount * completed_periods
            ),
            newly_accrued_amount=InterestAccrualService._round_money(
                base_interest_amount * len(periods_to_create)
            ),
            periods_to_create=periods_to_create,
            warnings=warnings,
            errors=errors,
        )

    @staticmethod
    def execute(command: InterestAccrualCommand) -> InterestAccrualResult:
        preview = InterestAccrualService.preview(command)
        if not preview.is_valid:
            return InterestAccrualResult(
                success=False,
                message="; ".join(preview.errors),
                loan=preview.loan,
                as_of_date=preview.as_of_date,
                warnings=preview.warnings,
                errors=preview.errors,
            )

        warnings = list(preview.warnings)

        if preview.pending_periods == 0:
            return InterestAccrualResult(
                success=True,
                message=f"No new interest accrual periods were due for loan {preview.loan_id}.",
                loan=preview.loan,
                as_of_date=preview.as_of_date,
                created_count=0,
                total_created_amount=Decimal("0.00"),
                warnings=warnings,
            )

        try:
            with transaction.atomic():
                created_rows = []
                for period in preview.periods_to_create:
                    created_rows.append(
                        LoanInterestAccrual.objects.create(
                            loan=command.loan,
                            period_start=period.period_start,
                            period_end=period.period_end,
                            accrued_amount=period.accrued_amount,
                            base_interest_snapshot=period.base_interest_snapshot,
                            months_covered=1,
                            trigger_source=getattr(command, "trigger_source", AccrualTriggerSource.MANUAL)
                            or AccrualTriggerSource.MANUAL,
                            status=AccrualStatus.DRAFT,
                            notes=getattr(command, "notes", "") or "",
                            created_by=getattr(command, "created_by", None),
                        )
                    )

                journal_entry_voucher = None
                accounting_voucher = None
                journal_entry = None
                if getattr(command, "post_to_accounting", False):
                    journal_entry_voucher, accounting_voucher, journal_entry = (
                        InterestAccrualService._post_accrual_batch_to_accounting(
                            command,
                            preview,
                            created_rows,
                        )
                    )
        except ValidationError as exc:
            error_list = list(getattr(exc, "messages", None) or [str(exc)])
            return InterestAccrualResult(
                success=False,
                message="; ".join(error_list),
                loan=preview.loan,
                as_of_date=preview.as_of_date,
                warnings=warnings,
                errors=error_list,
            )
        except Exception as exc:
            return InterestAccrualResult(
                success=False,
                message=f"An error occurred while creating interest accrual rows: {exc}",
                loan=preview.loan,
                as_of_date=preview.as_of_date,
                warnings=warnings,
                errors=[str(exc)],
            )

        message = (
            f"Created {len(created_rows)} interest accrual period(s) "
            f"for loan {preview.loan_id}."
        )
        if journal_entry_voucher is not None:
            message = (
                f"Created {len(created_rows)} interest accrual period(s) for loan "
                f"{preview.loan_id} and posted the DEA accrual journal."
            )

        return InterestAccrualResult(
            success=True,
            message=message,
            loan=preview.loan,
            as_of_date=preview.as_of_date,
            accruals=created_rows,
            created_count=len(created_rows),
            total_created_amount=InterestAccrualService._round_money(
                sum((row.accrued_amount for row in created_rows), Decimal("0.00"))
            ),
            journal_entry_voucher=journal_entry_voucher,
            accounting_voucher=accounting_voucher,
            journal_entry=journal_entry,
            warnings=warnings,
        )
