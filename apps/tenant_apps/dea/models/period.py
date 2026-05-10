from asyncio import Condition
import logging
from decimal import Decimal
from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from moneyed import Money

from ..utils.currency import Balance

logger = logging.getLogger(__name__)


class AccountingPeriodManager(models.Manager):
    def get_current_period(self, workspace=None):
        """Get the currently open period"""
        filters = {"status": AccountingPeriod.PeriodStatus.OPEN}
        if workspace:
            filters["workspace"] = workspace
        return self.filter(**filters).order_by("start_date").first()

    def get_period_for_date(self, date, workspace=None):
        """Get the period that contains the given date"""
        filters = {"start_date__lte": date, "end_date__gte": date}
        if workspace:
            filters["workspace"] = workspace
        return self.filter(**filters).first()


class AccountingPeriod(models.Model):
    """
    Represents an accounting period (e.g., monthly, quarterly, yearly).
    Used to organize and close financial records at regular intervals.
    """

    class PeriodStatus(models.TextChoices):
        OPEN = "OPEN", _("Open")
        CLOSED = "CLOSED", _("Closed")  # Period is closed but not locked
        LOCKED = "LOCKED", _("Locked")  # Period is locked, no changes allowed

    # Period identification
    # workspace = models.ForeignKey(
    #     'accounts.Workspace',
    #     on_delete=models.CASCADE,
    #     related_name='accounting_periods',
    #     null=True,
    #     blank=True,
    #     help_text="Multi-tenant workspace support"
    # )
    name = models.CharField(
        max_length=100, help_text="e.g., 'Jan 2024', 'Q1 2024', 'FY 2023-24'"
    )
    start_date = models.DateField(help_text="Period starts on this date (inclusive)")
    end_date = models.DateField(help_text="Period ends on this date (inclusive)")

    # Status management
    status = models.CharField(
        max_length=10, choices=PeriodStatus.choices, default=PeriodStatus.OPEN
    )
    created = models.DateTimeField(auto_now_add=True)
    closed_date = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="closed_periods",
    )

    # Closing entries
    closing_journal_entry = models.OneToOneField(
        "JournalEntry",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="closing_period",
        help_text="Closing entry that closes income/expense accounts",
    )

    # Notes
    notes = models.TextField(blank=True, help_text="Period notes or closing remarks")

    objects = AccountingPeriodManager()

    class Meta:
        ordering = ["-end_date"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gt=models.F("start_date")),
                name="period_end_after_start",
            ),
            models.UniqueConstraint(
                fields=["start_date", "end_date"], name="unique_period_per_workspace"
            ),
        ]
        verbose_name = _("Accounting Period")
        verbose_name_plural = _("Accounting Periods")
        permissions = [
            ("can_close_period", "Can close accounting periods"),
            ("can_lock_period", "Can lock closed periods"),
            ("can_unlock_period", "Can unlock locked periods"),
        ]

    def __str__(self):
        return f"{self.name} ({self.start_date} - {self.end_date})"

    def clean(self):
        """Validate period before save"""
        if self.start_date and self.end_date:
            if self.end_date <= self.start_date:
                raise ValidationError(_("End date must be after start date"))

            # Check for overlapping periods (same workspace)
            overlapping = AccountingPeriod.objects.filter(
                start_date__lte=self.end_date, end_date__gte=self.start_date
            )
            # if self.workspace:
            #     overlapping = overlapping.filter(workspace=self.workspace)
            if self.pk:
                overlapping = overlapping.exclude(pk=self.pk)
            if overlapping.exists():
                raise ValidationError(
                    _("This period overlaps with: ")
                    + ", ".join(str(p) for p in overlapping)
                )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def is_open(self):
        """Check if period is open for transactions"""
        return self.status == self.PeriodStatus.OPEN

    def is_locked(self):
        """Check if period is locked"""
        return self.status == self.PeriodStatus.LOCKED

    def can_modify_transactions(self):
        """Check if transactions in this period can be modified"""
        return self.status in [self.PeriodStatus.OPEN]

    def get_next_period(self):
        """Get the next accounting period (schema-local; no workspace filter needed with django-tenants)."""
        return (
            AccountingPeriod.objects.filter(start_date__gt=self.end_date)
            .order_by("start_date")
            .first()
        )

    def get_previous_period(self):
        """Get the previous accounting period (schema-local; no workspace filter needed with django-tenants)."""
        return (
            AccountingPeriod.objects.filter(end_date__lt=self.start_date)
            .order_by("-end_date")
            .first()
        )

    @transaction.atomic
    def close_period(self, user, notes=""):
        """
        Close the accounting period:
        1. Create closing entries for income/expense accounts
        2. Generate closing statements
        3. Mark period as CLOSED

        Args:
            user: User performing the close
            notes: Optional closing notes
        """
        from django.db import connection
        if connection.schema_name == "public":
            raise RuntimeError(
                "close_period() must not be called in the public schema. "
                "Ensure you are operating inside a tenant schema context."
            )

        if self.status != self.PeriodStatus.OPEN:
            raise ValidationError(
                _("Can only close OPEN periods. Current status: ") + self.status
            )

        # Model-level guard: block close if any DRAFT vouchers fall within this period.
        # The view/form also checks this, but the model enforces it as a last line of defence.
        from .voucher import Voucher, VoucherStatus as VS

        draft_count = Voucher.objects.filter(
            voucher_date__gte=self.start_date,
            voucher_date__lte=self.end_date,
            status=VS.DRAFT,
        ).count()
        if draft_count > 0:
            raise ValidationError(
                _(
                    f"Cannot close period '{self.name}': {draft_count} draft voucher(s) "
                    "exist within the period date range. Post or delete them first."
                )
            )

        from .ledger import Ledger

        try:
            with transaction.atomic():
                income_expense_ledgers = Ledger.objects.filter(
                    AccountType__AccountType__in=["Revenue", "Income", "Expense"]
                ).select_related("AccountType")

                closing_entries = []
                retained_earnings = None
                if income_expense_ledgers.exists():
                    retained_earnings = self._get_or_create_retained_earnings_ledger()

                for ledger in income_expense_ledgers:
                    period_balance = ledger.calculate_period_balance(self)
                    if period_balance.amount == 0:
                        continue

                    amount = Money(abs(period_balance.amount), period_balance.currency)
                    if period_balance.amount > 0:
                        debit_ledger = retained_earnings.name
                        credit_ledger = ledger.name
                    else:
                        debit_ledger = ledger.name
                        credit_ledger = retained_earnings.name

                    closing_entries.append(
                        {
                            "ledgerno": credit_ledger,
                            "ledgerno_dr": debit_ledger,
                            "amount": amount,
                        }
                    )

                if closing_entries:
                    self.closing_journal_entry = self._create_closing_journal_entry(
                        user=user,
                        closing_entries=closing_entries,
                    )

                self._create_closing_statements()

                self.status = self.PeriodStatus.CLOSED
                self.closed_date = timezone.now()
                self.closed_by = user
                self.notes = notes
                self.save()

                logger.info(
                    f"Period {self.name} closed by {user} at {self.closed_date}"
                )

        except Exception as e:
            logger.error(f"Error closing period {self.name}: {str(e)}")
            raise ValidationError(_("Failed to close period: ") + str(e))

    def _get_or_create_retained_earnings_ledger(self):
        """Ensure the required retained earnings ledger exists for period close."""
        from .ledger import AccountType, Ledger

        retained_earnings = Ledger.objects.filter(name="Retained Earnings").first()
        if retained_earnings:
            return retained_earnings

        equity_type, _ = AccountType.objects.get_or_create(
            AccountType="Equity",
            defaults={"description": "Equity Account", "code_prefix": "3"},
        )
        if not equity_type.code_prefix:
            equity_type.code_prefix = "3"
            equity_type.save(update_fields=["code_prefix"])

        capital, _ = Ledger.objects.get_or_create(
            name="Capital",
            defaults={
                "AccountType": equity_type,
                "sort_order": 10,
            },
        )
        capital_updates = []
        if capital.AccountType_id != equity_type.id:
            capital.AccountType = equity_type
            capital_updates.append("AccountType")
        if capital.sort_order != 10:
            capital.sort_order = 10
            capital_updates.append("sort_order")
        if capital_updates:
            capital.save(update_fields=capital_updates)

        if not capital.code:
            capital.save()

        retained_defaults = {
            "AccountType": equity_type,
            "sort_order": 30,
            "parent": capital,
        }
        if capital.code:
            child_segments = []
            for code in capital.children.exclude(code="").values_list("code", flat=True):
                if not code or not code.startswith(f"{capital.code}."):
                    continue
                try:
                    child_segments.append(int(code.split(".")[-1]))
                except (TypeError, ValueError):
                    continue
            next_segment = max(child_segments, default=0) + 1
            retained_defaults["code"] = f"{capital.code}.{next_segment:02d}"

        retained_earnings, created = Ledger.objects.get_or_create(
            name="Retained Earnings",
            defaults=retained_defaults,
        )
        retained_updates = []
        if retained_earnings.AccountType_id != equity_type.id:
            retained_earnings.AccountType = equity_type
            retained_updates.append("AccountType")
        if retained_earnings.parent_id != capital.id:
            retained_earnings.parent = capital
            retained_updates.append("parent")
        if retained_earnings.sort_order != 30:
            retained_earnings.sort_order = 30
            retained_updates.append("sort_order")
        if retained_updates:
            retained_earnings.save(update_fields=retained_updates)

        logger.info(
            "Auto-created retained earnings ledger for accounting period close"
        )
        return retained_earnings

    def _create_closing_journal_entry(self, user, closing_entries):
        """Create and post the voucher-backed journal entry used for period close."""
        from django.contrib.contenttypes.models import ContentType

        from .journal import JournalEntry
        from .voucher import Voucher, VoucherStatus, VoucherType

        voucher_type, _ = VoucherType.objects.get_or_create(
            name="PERIOD_CLOSE",
            defaults={"description": "System-generated accounting period close"},
        )

        voucher = Voucher.objects.create(
            voucher_no=f"PERIOD-CLOSE-{self.pk}-{timezone.now():%Y%m%d%H%M%S}",
            voucher_type=voucher_type,
            voucher_date=self.end_date,
            status=VoucherStatus.POSTED,
            created_by=user,
            updated_by=user,
            doc_content_type=ContentType.objects.get_for_model(type(self)),
            doc_object_id=self.pk,
            fingerprint=f"period-close:{self.pk}:{self.end_date.isoformat()}",
            last_posted_at=timezone.now(),
            narration=f"Period closing entry for {self.name}",
        )

        journal_entry = JournalEntry.objects.create(
            voucher=voucher,
            period=self,
            posted_by=user,
            desc=f"Period Closing Entry - {self.name}",
        )
        journal_entry.transact(closing_entries, [])
        return journal_entry

    def _create_closing_statements(self):
        """Create closing statements for all ledgers and accounts at period end"""
        from .ledger import Ledger, LedgerStatement
        from .account import Account, AccountStatement

        # Create statements for all ledgers
        for ledger in Ledger.objects.all():
            balance = ledger.calculate_period_balance(self)
            LedgerStatement.objects.create(
                ledgerno=ledger,
                ClosingBalance=Money(balance.amount, balance.currency),
                period=self,
                is_opening_statement=False,
            )

        # Create statements for all accounts
        for account in Account.objects.all():
            balance = account.calculate_period_balance(self)
            currency = getattr(balance, "currency", "INR")
            period_transactions = account.accounttransactions.filter(
                created__date__gte=self.start_date,
                created__date__lte=self.end_date,
                amount_currency=currency,
            )
            total_credit_amount = (
                period_transactions.filter(XactTypeCode__XactTypeCode="Cr").aggregate(
                    total=models.Sum("amount")
                )["total"]
                or 0
            )
            total_debit_amount = (
                period_transactions.filter(XactTypeCode__XactTypeCode="Dr").aggregate(
                    total=models.Sum("amount")
                )["total"]
                or 0
            )
            AccountStatement.objects.create(
                AccountNo=account,
                ClosingBalance=Money(balance.amount, currency),
                TotalCredit=Money(total_credit_amount, currency),
                TotalDebit=Money(total_debit_amount, currency),
                period=self,
                is_opening_statement=False,
            )

    @transaction.atomic
    def lock_period(self, user):
        """
        Lock period to prevent any changes.
        Can only lock CLOSED periods.
        """
        if self.status != self.PeriodStatus.CLOSED:
            raise ValidationError(
                _("Can only lock CLOSED periods. Current status: ") + self.status
            )

        self.status = self.PeriodStatus.LOCKED
        self.save()

        logger.info(f"Period {self.name} locked by {user}")

    def unlock_period(self, user):
        """Unlock a locked period (for corrections, requires approval)"""
        if self.status != self.PeriodStatus.LOCKED:
            raise ValidationError(_("Can only unlock LOCKED periods"))

        # Log unlock for audit
        logger.warning(f"Period {self.name} unlocked by {user} at {timezone.now()}")

        self.status = self.PeriodStatus.CLOSED
        self.save()
