from datetime import timezone
import logging

from django.db import models
from django.db.models import Sum
from django.urls import reverse
from django.core.exceptions import ValidationError
from djmoney.models.fields import MoneyField
from moneyed import Money
from mptt.models import MPTTModel, TreeForeignKey

from ..utils.currency import Balance

logger = logging.getLogger(__name__)


# ledger account type  for COA ,asset,liability,revenue,expense,gain,loss
class AccountType(models.Model):
    AccountType = models.CharField(max_length=50)
    description = models.CharField(max_length=100)
    code_prefix = models.CharField(
        max_length=2,
        help_text="Leading segment for ledger codes (e.g., 1=Asset, 2=Liability, 4=Income, 5=Expense)",
        default="",
        blank=True,
    )

    def __str__(self):
        return self.AccountType


# ledger is chart of accounts
# add ledgerno
class Ledger(MPTTModel):
    AccountType = models.ForeignKey(
        AccountType, on_delete=models.CASCADE, related_name="ledgers"
    )
    code = models.CharField(
        max_length=64, unique=True, db_index=True, blank=True, default=""
    )
    sort_order = models.PositiveIntegerField(
        default=0, help_text="Optional manual ordering among siblings"
    )
    name = models.CharField(
        max_length=100,
        unique=True,  # if you have tenant scoping, drop this and add a UniqueConstraint with tenant
        null=True,
        blank=True,
        help_text="Stable symbolic key for posting rules (e.g., 'LOAN_RECEIVABLE', 'CASH').",
    )
    parent = TreeForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="children"
    )
    # Add new classification fields
    is_operating_revenue = models.BooleanField(
        default=False, help_text="Indicates if this is an operating revenue account"
    )
    is_direct_expense = models.BooleanField(
        default=False, help_text="Indicates if this is a direct expense (COGS) account"
    )
    is_operating_expense = models.BooleanField(
        default=False, help_text="Indicates if this is an operating expense account"
    )
    is_current_asset = models.BooleanField(
        default=True, help_text="Asset accounts: True = current, False = fixed/non-current"
    )
    is_current_liability = models.BooleanField(
        default=True, help_text="Liability accounts: True = current, False = long-term"
    )

    # objects = LedgerManager()

    class MPTTMeta:
        order_insertion_by = ["name"]
        parent_attr = "parent"
        constraints = [
            models.UniqueConstraint(
                fields=["name", "parent"], name="unique ledgername-parent"
            )
        ]

    class Meta:
        ordering = ["tree_id", "lft"]  # Add proper MPTT ordering
        constraints = [
            models.UniqueConstraint(
                fields=["name", "parent"], name="unique_ledgername_parent"
            )
        ]

    def clean(self):
        """Validate ledger classification"""
        # Prevent code change after it has transactions
        if self.pk and self.code:
            has_txn = (
                self.credit_txns.exists()
                or self.debit_txns.exists()
                or self.aleg.exists()
            )
            if has_txn:
                # protect immutability of code
                orig = type(self).objects.only("code").get(pk=self.pk)
                if orig.code != self.code:
                    raise ValidationError(
                        "Ledger code cannot be changed after transactions exist."
                    )
        super().clean()

        # Ensure revenue accounts are properly marked
        if self.AccountType.AccountType == "Revenue":
            if self.is_direct_expense or self.is_operating_expense:
                raise ValidationError("Revenue account cannot be marked as an expense")

        # Ensure expense accounts are properly marked
        if self.AccountType.AccountType == "Expense":
            if self.is_operating_revenue:
                raise ValidationError("Expense account cannot be marked as revenue")
            if self.is_direct_expense and self.is_operating_expense:
                raise ValidationError(
                    "Expense account cannot be both direct and operating"
                )

    def __str__(self):
        return f"{self.name} - {self.AccountType}"

    def get_absolute_url(self):
        return reverse("dea_ledger_detail", kwargs={"pk": self.pk})

    def get_latest_stmt(self):
        try:
            return self.ledgerstatements.latest()
        except LedgerStatement.DoesNotExist:
            return None

    def set_opening_bal(self, amounts):
        """
        Set opening balances for multiple currencies
        Args:
            amounts: List[Money] - List of Money objects for different currencies
        Returns:
            List[LedgerStatement] - Created statements
        """
        statements = []

        # Validate no existing transactions
        if self.credit_txns.exists() or self.debit_txns.exists() or self.aleg.exists():
            raise ValidationError(
                "Cannot set opening balance - ledger already has transactions"
            )

        for amount in amounts:
            # Create statement for each currency
            statement = LedgerStatement.objects.create(
                ledgerno=self, ClosingBalance=amount
            )
            statements.append(statement)

        return statements

    def ctxns(self, since=None):
        if since is not None:
            return self.credit_txns.filter(created__gte=since).select_related(
                "journal_entry"
            )
        else:
            return self.credit_txns.all().select_related("journal_entry")

    def dtxns(self, since=None):
        if since is not None:
            return self.debit_txns.filter(created__gte=since).select_related(
                "journal_entry"
            )
        else:
            return self.debit_txns.all().select_related("journal_entry")

    def aleg_txns(self, since=None, xacttypecode=None):
        if since is not None:
            return self.aleg.filter(
                created__gte=since, XactTypeCode=xacttypecode
            ).select_related("journal_entry")
        else:
            return self.aleg.filter(XactTypeCode=xacttypecode).select_related(
                "journal_entry"
            )

    def get_closing_balance(self):
        """Get closing balance in all active currencies"""
        balances = []

        # Get all active currencies for this ledger
        for currency in self.get_active_currencies():
            try:
                # Get latest statement for this currency
                stmt = self.ledgerstatements.filter(
                    ClosingBalance_currency=currency
                ).latest()
                balances.append(stmt.ClosingBalance)
            except LedgerStatement.DoesNotExist:
                # If no statement exists for this currency, add zero balance
                balances.append(Money(0, currency))

        return Balance(balances)

    def get_active_currencies(self):
        """Get list of currencies used in this ledger's transactions"""
        currencies = set()
        currencies.update(
            self.credit_txns.values_list("amount_currency", flat=True).distinct()
        )
        currencies.update(
            self.debit_txns.values_list("amount_currency", flat=True).distinct()
        )
        currencies.update(
            self.aleg.values_list("amount_currency", flat=True).distinct()
        )
        return list(currencies)

    def calculate_balance(self, currency, since=None):
        """
        Calculate balance changes for specific currency since given date
        Returns net balance change (Dr - Cr) for given currency since date.
        Positive = net debit, Negative = net credit.
        """
        # Base filters for currency
        credit_filters = {"amount_currency": currency}
        debit_filters = {"amount_currency": currency}

        # Add date filter only if since is not None
        if since:
            credit_filters["created__gt"] = since
            debit_filters["created__gt"] = since

        # Get credits with proper filters
        credit_sum = (
            self.credit_txns.filter(**credit_filters).aggregate(total=Sum("amount"))[
                "total"
            ]
            or 0
        )

        aleg_credit_sum = (
            self.aleg.filter(**credit_filters, XactTypeCode="Cr").aggregate(
                total=Sum("amount")
            )["total"]
            or 0
        )

        # Get debits with proper filters
        debit_sum = (
            self.debit_txns.filter(**debit_filters).aggregate(total=Sum("amount"))[
                "total"
            ]
            or 0
        )

        aleg_debit_sum = (
            self.aleg.filter(**debit_filters, XactTypeCode="Dr").aggregate(
                total=Sum("amount")
            )["total"]
            or 0
        )
        logger.debug(
            "calculate_balance %s: ds=%s cs=%s ads=%s acs=%s",
            self.name, debit_sum, credit_sum, aleg_debit_sum, aleg_credit_sum,
        )
        m = Money(
            (debit_sum + aleg_debit_sum) - (credit_sum + aleg_credit_sum), currency
        )
        logger.debug("calculated balance %s change: %s", self.name, m)
        return m

    def calculate_period_balance(self, period):
        """
        Calculate balance for transactions within a specific accounting period.
        Only includes transactions created within the period date range.

        Args:
            period: AccountingPeriod instance

        Returns:
            Money: Net balance change for the period in the primary currency (INR)
        """
        from .period import AccountingPeriod

        if not isinstance(period, AccountingPeriod):
            raise ValueError("Must provide an AccountingPeriod instance")

        # Filter transactions by period dates
        credit_sum = (
            self.credit_txns.filter(
                created__date__gte=period.start_date,
                created__date__lte=period.end_date,
                amount_currency="INR",
            ).aggregate(total=Sum("amount"))["total"]
            or 0
        )

        debit_sum = (
            self.debit_txns.filter(
                created__date__gte=period.start_date,
                created__date__lte=period.end_date,
                amount_currency="INR",
            ).aggregate(total=Sum("amount"))["total"]
            or 0
        )

        aleg_credit_sum = (
            self.aleg.filter(
                created__date__gte=period.start_date,
                created__date__lte=period.end_date,
                XactTypeCode__XactTypeCode="Cr",
                amount_currency="INR",
            ).aggregate(total=Sum("amount"))["total"]
            or 0
        )

        aleg_debit_sum = (
            self.aleg.filter(
                created__date__gte=period.start_date,
                created__date__lte=period.end_date,
                XactTypeCode__XactTypeCode="Dr",
                amount_currency="INR",
            ).aggregate(total=Sum("amount"))["total"]
            or 0
        )

        net_balance = (debit_sum + aleg_debit_sum) - (credit_sum + aleg_credit_sum)
        return Money(net_balance, "INR")

    def get_opening_balance_for_period(self, period):
        """
        Get the opening balance for a period (closing balance of previous period).

        Args:
            period: AccountingPeriod instance

        Returns:
            Balance: Opening balance in all currencies
        """
        from .period import AccountingPeriod

        if not isinstance(period, AccountingPeriod):
            raise ValueError("Must provide an AccountingPeriod instance")

        # Get the previous period
        previous_period = period.get_previous_period()

        if not previous_period:
            # No previous period, use first opening statement
            try:
                stmt = self.ledgerstatements.filter(is_opening_statement=True).earliest(
                    "created"
                )
                return stmt.get_cb()
            except LedgerStatement.DoesNotExist:
                return Balance()

        # Get closing balance of previous period
        try:
            stmt = self.ledgerstatements.filter(
                period=previous_period, is_opening_statement=False
            ).latest("created")
            return stmt.get_cb()
        except LedgerStatement.DoesNotExist:
            # If no closing statement, calculate from transactions
            return Balance()

    def get_balance_at_period_end(self, period):
        """
        Get cumulative balance through the end of a specific period.
        This is: opening balance + period transactions.

        Args:
            period: AccountingPeriod instance

        Returns:
            Balance: Cumulative balance through period end
        """
        opening_balance = self.get_opening_balance_for_period(period)
        period_change = self.calculate_period_balance(period)

        # Combine balances
        balances = []
        for money in opening_balance.monies():
            new_balance = money + period_change
            balances.append(new_balance)

        if not balances and period_change.amount != 0:
            balances = [period_change]

        return Balance(balances)

    def current_balance(self):
        """Get current balance in all active currencies"""
        balances = []
        for currency in self.get_active_currencies():
            # Get latest statement for this currency
            try:
                stmt = self.ledgerstatements.filter(
                    ClosingBalance_currency=currency
                ).latest()
                prev_balance = stmt.ClosingBalance
                since = stmt.created
            except LedgerStatement.DoesNotExist:
                prev_balance = Money(0, currency)
                since = None

            # Calculate changes since last statement
            balance_change = self.calculate_balance(currency, since)
            balances.append(prev_balance + balance_change)

        return Balance(balances)

    def get_current_balance(self):
        """Get current balance using the database view with optimized querying"""
        try:
            balances = []
            # Use select_related to optimize the query
            balance_entries = LedgerBalance.objects.filter(
                ledgerno=self
            ).select_related("ledgerno")

            if not balance_entries.exists():
                return Balance([Money(0, "INR")])  # Default balance if no entries found

            for balance in balance_entries:
                balances.append(Money(balance.current_balance, balance.currency))
            return Balance(balances)
        except Exception as e:
            logger.error(
                f"Error getting current balance for ledger {self.pk}: {str(e)}"
            )
            return Balance([Money(0, "INR")])  # Return safe default on error

    def audit(self):
        """Create statements for all active currencies"""
        # statements = []
        # for currency in self.get_active_currencies():
        #     balance = self.current_balance().get(currency)
        #     stmt = LedgerStatement.objects.create(
        #         ledgerno=self,
        #         ClosingBalance=balance
        #     )
        #     statements.append(stmt)
        # return statements

        balance = self.current_balance()
        for money in balance.monies():
            LedgerStatement.objects.create(ledgerno=self, ClosingBalance=money)

    def save(self, *args, **kwargs):
        # Assign code if missing (predictable, concurrency-safe)
        if not self.code:
            from .numbering import generate_ledger_code

            self.code = generate_ledger_code(self)
        super().save(*args, **kwargs)


class LedgerTransactionManager(models.Manager):
    def create_txn(self, journal_entry, ledgerno, ledgerno_dr, amount):
        """Create a new ledger transaction with validation"""
        try:
            dr = Ledger.objects.select_related("AccountType").get(name=ledgerno_dr)
            cr = Ledger.objects.select_related("AccountType").get(name=ledgerno)

            txn = self.create(
                journal_entry=journal_entry, ledgerno=cr, ledgerno_dr=dr, amount=amount
            )
            return txn
        except Ledger.DoesNotExist as e:
            logger.error(f"Error creating transaction: {str(e)}")
            raise ValueError("Invalid ledger account specified")


class LedgerTransaction(models.Model):
    journal_entry = models.ForeignKey(
        "JournalEntry", on_delete=models.CASCADE, related_name="ltxns"
    )
    ledgerno = models.ForeignKey(
        Ledger, on_delete=models.CASCADE, related_name="credit_txns"
    )
    created = models.DateTimeField(
        auto_now_add=True,
        # unique = True
    )
    ledgerno_dr = models.ForeignKey(
        Ledger, on_delete=models.CASCADE, related_name="debit_txns"
    )
    amount = MoneyField(
        max_digits=13,
        decimal_places=3,
        default_currency="INR",
    )
    amount_base = MoneyField(
        max_digits=13, decimal_places=3, default_currency="INR", null=True, blank=True
    )
    objects = LedgerTransactionManager()

    class Meta:
        indexes = [
            models.Index(fields=["ledgerno"]),
            models.Index(fields=["ledgerno_dr"]),
            models.Index(fields=["created"]),
            models.Index(fields=["journal_entry", "created"]),
        ]
        ordering = ["-created"]

    def __str__(self):
        return self.ledgerno.name


class LedgerStatement(models.Model):
    ledgerno = models.ForeignKey(
        Ledger, on_delete=models.CASCADE, related_name="ledgerstatements"
    )
    period = models.ForeignKey(
        "AccountingPeriod",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="ledger_statements",
        help_text="Accounting period this statement belongs to",
    )
    created = models.DateTimeField(
        # unique = True,
        auto_now_add=True
    )
    ClosingBalance = MoneyField(
        max_digits=13,
        decimal_places=3,
        default_currency="INR",
    )
    is_opening_statement = models.BooleanField(
        default=False,
        help_text="True if this is an opening balance statement, False if closing",
    )

    class Meta:
        unique_together = ["ledgerno", "ClosingBalance_currency", "created"]
        get_latest_by = "created"
        ordering = ["-created"]
        indexes = [
            models.Index(fields=["ledgerno", "period"]),
            models.Index(fields=["period", "is_opening_statement"]),
        ]

    def __str__(self):
        stmt_type = "Opening" if self.is_opening_statement else "Closing"
        period_str = f" ({self.period})" if self.period else ""
        return f"{self.created.date()} - {stmt_type} - {self.ledgerno} - {self.ClosingBalance}{period_str}"

    def get_cb(self):
        return Balance(self.ClosingBalance)

    # def clean(self):
    #     """Validate statement data before saving"""
    #     if self.ClosingBalance.amount < 0 and self.ledgerno.AccountType.AccountType in ['Asset', 'Expense']:
    #         raise ValidationError('Asset and Expense accounts cannot have negative balance')

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    @classmethod
    def create_statement(cls, ledger, balance, date=None):
        """Factory method to create new statement with validation"""
        try:
            return cls.objects.create(
                ledgerno=ledger, ClosingBalance=balance, created=date or timezone.now()
            )
        except Exception as e:
            logger.error(f"Error creating statement for ledger {ledger.pk}: {str(e)}")
            raise


# postgresql read-only-view


class LedgerBalance(models.Model):
    """
    Model representing the lb_1 database view that shows ledger balances with transaction details
    """

    ledgerno = models.OneToOneField(
        "dea.Ledger",
        primary_key=True,
        db_column="ledgerno_id",
        on_delete=models.DO_NOTHING,
    )
    ledger_name = models.CharField(max_length=255)
    AccountType = models.ForeignKey(
        "dea.AccountType", on_delete=models.DO_NOTHING, db_column="AccountType_id"
    )
    currency = models.CharField(max_length=3, default="INR")
    last_statement_date = models.DateTimeField(null=True)
    opening_balance = models.DecimalField(max_digits=15, decimal_places=3, default=0)
    ledger_credit_sum = models.DecimalField(max_digits=15, decimal_places=3, default=0)
    ledger_debit_sum = models.DecimalField(max_digits=15, decimal_places=3, default=0)
    account_credit_sum = models.DecimalField(max_digits=15, decimal_places=3, default=0)
    account_debit_sum = models.DecimalField(max_digits=15, decimal_places=3, default=0)
    total_credit_sum = models.DecimalField(max_digits=15, decimal_places=3, default=0)
    total_debit_sum = models.DecimalField(max_digits=15, decimal_places=3, default=0)
    current_balance = models.DecimalField(max_digits=15, decimal_places=3, default=0)

    class Meta:
        managed = False
        db_table = "ledger_balances"

    def get_balance(self):
        """Returns the current balance as a Money object"""
        return Money(self.current_balance, self.currency)

    def get_opening_balance(self):
        """Returns the opening balance as a Money object"""
        return Money(self.opening_balance, self.currency)

    def get_total_credits(self):
        """Returns total credits as a Money object"""
        return Money(self.total_credit_sum, self.currency)

    def get_total_debits(self):
        """Returns total debits as a Money object"""
        return Money(self.total_debit_sum, self.currency)

    def __str__(self):
        return f"{self.ledger_name} ({self.currency}): {self.get_balance()}"
