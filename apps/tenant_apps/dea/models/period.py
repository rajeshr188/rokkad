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
            if self.workspace:
                overlapping = overlapping.filter(workspace=self.workspace)
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
        """Get the next accounting period"""
        query = AccountingPeriod.objects.filter(start_date__gt=self.end_date)
        if self.workspace:
            query = query.filter(workspace=self.workspace)
        return query.order_by("start_date").first()

    def get_previous_period(self):
        """Get the previous accounting period"""
        query = AccountingPeriod.objects.filter(end_date__lt=self.start_date)
        if self.workspace:
            query = query.filter(workspace=self.workspace)
        return query.order_by("-end_date").first()

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
        if self.status != self.PeriodStatus.OPEN:
            raise ValidationError(
                _("Can only close OPEN periods. Current status: ") + self.status
            )

        from .ledger import Ledger, LedgerStatement
        from .journal_entry import JournalEntry

        try:
            with transaction.atomic():
                # Get all ledgers with income/expense accounts
                income_expense_ledgers = Ledger.objects.filter(
                    AccountType__AccountType__in=["Revenue", "Expense"]
                )

                closing_entries = []
                retained_earnings = Ledger.objects.get(name="Retained Earnings")

                # Calculate balances for this period only
                for ledger in income_expense_ledgers:
                    period_balance = ledger.calculate_period_balance(self)

                    if period_balance.amount != 0:
                        # Create closing entry
                        closing_entries.append(
                            {
                                "ledgerno": retained_earnings.name,
                                "ledgerno_dr": ledger.name,
                                "amount": Money(
                                    abs(period_balance.amount), period_balance.currency
                                ),
                            }
                        )

                # Create closing journal entry if there are entries
                if closing_entries:
                    je = JournalEntry.objects.create(
                        desc=f"Period Closing Entry - {self.end_date}",
                        period=self,
                        created_by=user,
                    )
                    je.transact_from_list(closing_entries)
                    self.closing_journal_entry = je

                # Create closing statements for all ledgers and accounts
                self._create_closing_statements()

                # Update period status
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
            AccountStatement.objects.create(
                AccountNo=account,
                ClosingBalance=Money(balance.amount, balance.currency),
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
