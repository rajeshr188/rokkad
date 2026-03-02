import logging

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from djmoney.models.fields import MoneyField
from moneyed import Money

from apps.tenant_apps.contact.models import Customer

from ..managers import AccountManager
from ..utils.currency import Balance
from .ledger import Ledger


logger = logging.getLogger(__name__)


# cr credit,dr debit
class TransactionType_DE(models.Model):
    XactTypeCode = models.CharField(max_length=2, primary_key=True)
    name = models.CharField(
        max_length=10, unique=True, verbose_name=_("Transaction Type")
    )

    def __str__(self):
        return self.name


# sundry_debtor[dr],sundry_creditor[cr],let desc be unique
class AccountType_Ext(models.Model):
    XactTypeCode = models.ForeignKey(TransactionType_DE, on_delete=models.CASCADE)
    description = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.description


# person or organisation
class EntityType(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name=_("Entity Type"))

    def __str__(self):
        return self.name


# rameshbi[sundry debtor],ramlalji,narsa,mjk[sundry creditor]
class AccountStatus(models.TextChoices):
    ACTIVE = "ACTIVE", _("Active")
    INACTIVE = "INACTIVE", _("Inactive")
    SUSPENDED = "SUSPENDED", _("Suspended")
    CLOSED = "CLOSED", _("Closed")


class Account(models.Model):
    """
    Represents a customer/vendor account in the accounting system.
    Each account is linked to a contact and can have credit limits.

    Account Numbering Format: <AccountType_prefix><sequential_number>
    Example: DR0001, CR0001 (DR=Debtor, CR=Creditor)
    """

    entity = models.ForeignKey(
        EntityType,
        null=True,
        on_delete=models.SET_NULL,
        default="Person",
        verbose_name=_("Entity Type"),
    )
    AccountType_Ext = models.ForeignKey(
        AccountType_Ext, on_delete=models.CASCADE, verbose_name=_("Account Type")
    )
    contact = models.OneToOneField(
        Customer, on_delete=models.CASCADE, related_name="account"
    )

    # Account identification
    account_number = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        blank=True,
        help_text="Auto-generated unique account number",
    )

    # Account status
    status = models.CharField(
        max_length=10,
        choices=AccountStatus.choices,
        default=AccountStatus.ACTIVE,
        db_index=True,
    )

    # Credit management
    credit_limit = MoneyField(
        max_digits=15,
        decimal_places=2,
        default_currency="INR",
        null=True,
        blank=True,
        help_text="Maximum credit allowed for this account",
    )
    credit_days = models.PositiveIntegerField(
        default=0, help_text="Payment terms in days (0 = cash only)"
    )

    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    closed_date = models.DateField(
        null=True, blank=True, help_text="Date when account was closed"
    )
    notes = models.TextField(blank=True)

    objects = AccountManager()

    class Meta:
        ordering = ("account_number",)
        constraints = [
            models.UniqueConstraint(fields=["contact"], name="unique_contact_account")
        ]
        indexes = [
            models.Index(fields=["account_number", "status"]),
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self):
        return f"{self.account_number or self.id} | {self.contact} | {self.AccountType_Ext}"

    def save(self, *args, **kwargs):
        # Generate account number if not set
        if not self.account_number:
            self.account_number = self._generate_account_number()
        self.full_clean()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("dea_account_detail", kwargs={"pk": self.pk})

    def _generate_account_number(self):
        """
        Generate unique account number: <AccountType_prefix><sequential_number>
        Example: DR0001 for Debtor, CR0001 for Creditor
        """
        account_type = self.AccountType_Ext.XactTypeCode.XactTypeCode  # 'Dr' or 'Cr'
        prefix = account_type.upper()  # 'DR' or 'CR'

        # Get the last account with this prefix
        last_account = (
            Account.objects.filter(account_number__startswith=prefix)
            .order_by("account_number")
            .last()
        )

        if last_account and last_account.account_number:
            # Extract number and increment
            try:
                last_num = int(last_account.account_number[len(prefix) :])
                new_num = last_num + 1
            except (ValueError, IndexError):
                new_num = 1
        else:
            new_num = 1

        return f"{prefix}{new_num:04d}"  # Zero-padded to 4 digits

    def is_active(self):
        """Check if account is active"""
        return self.status == AccountStatus.ACTIVE

    def can_transact(self):
        """Check if transactions are allowed on this account"""
        return self.status in [AccountStatus.ACTIVE, AccountStatus.INACTIVE]

    def get_available_credit(self):
        """
        Calculate available credit: credit_limit - current_balance
        Returns Amount object or None if no credit limit
        """
        if not self.credit_limit:
            return None

        current_bal = self.current_balance()
        # For debtor accounts, balance should not exceed credit limit
        if self.AccountType_Ext.XactTypeCode_id == "Dr":
            # Get balance in same currency as credit limit
            balance_amount = current_bal.get(self.credit_limit.currency)
            if balance_amount:
                available = self.credit_limit - balance_amount
                return max(available, Money(0, self.credit_limit.currency))
        return self.credit_limit

    def is_over_credit_limit(self):
        """Check if account has exceeded credit limit"""
        available = self.get_available_credit()
        if available is None:
            return False
        return available.amount <= 0

    def close_account(self, closed_date=None, notes=""):
        """
        Close the account. Validates that balance is zero.
        """
        from django.utils import timezone

        # Check if balance is zero
        balance = self.current_balance()
        if not balance.is_zero():
            raise ValidationError(
                f"Cannot close account with non-zero balance: {balance}"
            )

        self.status = AccountStatus.CLOSED
        self.closed_date = closed_date or timezone.now().date()
        if notes:
            self.notes = (
                f"{self.notes}\n\nClosed: {notes}" if self.notes else f"Closed: {notes}"
            )
        self.save()

    def set_opening_bal(self, amounts):
        """
        Set opening balances for multiple currencies
        Args:
            amounts: List[Money] - List of Money objects for different currencies
        Returns:
            List[AccountStatement] - Created statements
        """
        statements = []

        # Ensure no transactions exist
        if self.accounttransactions.exists():
            raise ValidationError(
                "Cannot set opening balance - account already has transactions"
            )

        for amount in amounts:
            # Create statement for each currency
            statement = AccountStatement.objects.create(
                AccountNo=self,
                ClosingBalance=amount,
                TotalCredit=Money(0, amount.currency),
                TotalDebit=Money(0, amount.currency),
            )
            statements.append(statement)

        return statements

    def txns(self, since=None):
        txns = (
            self.accounttransactions.all()
            .select_related(
                "journal_entry",
                # "journal_entry__content_object",not possible in django for gfks
                "journal_entry__content_type",
                "Account",
                "XactTypeCode",
                "XactTypeCode_ext",
                "ledgerno",
            )
            .prefetch_related("journal_entry__content_object")
            # .order_by("id") breaks current_balance
        )
        if since:
            txns = txns.filter(created__gte=since)
        return txns

    def total_credit(self, since=None):
        txns = self.txns(since=since)
        bal = Balance(
            [
                Money(r["total"], r["amount_currency"])
                for r in txns.filter(
                    # XactTypeCode_ext__in=["LT", "LR", "IR", "CPU", "CRPU", "RCT", "AC"]
                    XactTypeCode__XactTypeCode="Dr"
                )
                .values("amount_currency")
                .annotate(total=Sum("amount"))
            ]
        )
        logger.info(f"total_credit:{bal}")
        return bal

    def total_debit(self, since=None):
        txns = self.txns(since=since)
        return Balance(
            [
                Money(r["total"], r["amount_currency"])
                for r in txns.filter(
                    # XactTypeCode_ext__in=["LG", "LP", "IP", "PYT", "CRSL", "AD"]
                    XactTypeCode__XactTypeCode="Cr"
                )
                .values("amount_currency")
                .annotate(total=Sum("amount"))
            ]
        )

    def get_active_currencies(self):
        """Get list of currencies used in this account's transactions"""
        return list(
            self.accounttransactions.values_list("amount_currency", flat=True)
            .distinct()
            .order_by("amount_currency")
        )

    def calculate_balance(self, currency, since=None):
        """Calculate balance changes for specific currency since given date"""
        # Base query with currency filter
        query_filters = {"amount_currency": currency}

        # Only add date filter if since is provided
        if since is not None:
            query_filters["created__gt"] = since

        transactions = self.accounttransactions.filter(**query_filters)

        credits = (
            transactions.filter(XactTypeCode__XactTypeCode="Cr").aggregate(
                total=Sum("amount")
            )["total"]
            or 0
        )

        debits = (
            transactions.filter(XactTypeCode__XactTypeCode="Dr").aggregate(
                total=Sum("amount")
            )["total"]
            or 0
        )

        if self.AccountType_Ext.XactTypeCode_id == "Dr":
            return Money(debits - credits, currency)
        else:
            return Money(credits - debits, currency)

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
        transactions = self.accounttransactions.filter(
            created__date__gte=period.start_date,
            created__date__lte=period.end_date,
            amount_currency="INR",
        )

        credits = (
            transactions.filter(XactTypeCode__XactTypeCode="Cr").aggregate(
                total=Sum("amount")
            )["total"]
            or 0
        )

        debits = (
            transactions.filter(XactTypeCode__XactTypeCode="Dr").aggregate(
                total=Sum("amount")
            )["total"]
            or 0
        )

        # Apply account type logic
        if self.AccountType_Ext.XactTypeCode_id == "Dr":
            net_balance = debits - credits
        else:
            net_balance = credits - debits

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
                stmt = self.accountstatements.filter(
                    is_opening_statement=True
                ).earliest("created")
                return Balance([stmt.get_cb()])
            except AccountStatement.DoesNotExist:
                return Balance()

        # Get closing balance of previous period
        try:
            stmt = self.accountstatements.filter(
                period=previous_period, is_opening_statement=False
            ).latest("created")
            return Balance([stmt.get_cb()])
        except AccountStatement.DoesNotExist:
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
        """Get current balance in all active currencies (METHOD 1: Snapshot + Incremental)

        This method uses a two-step calculation:
        1. Find the latest AccountStatement snapshot (checkpoint)
        2. Calculate all transactions SINCE that snapshot
        3. Return: snapshot_balance + changes_since_snapshot

        When to use:
        - For audit trail (shows balance at specific checkpoint + subsequent changes)
        - When AccountBalance view is not available
        - For debugging/verification against database view

        Performance: O(n) where n = transactions since last snapshot

        See also:
        - get_current_balance(): Faster method using database view
        - audit(): Creates new snapshot for future incremental calculations
        """
        balances = []
        print(f" active currencies: {self.get_active_currencies()}")
        for currency in self.get_active_currencies():
            try:
                # Get latest statement for this currency
                stmt = self.accountstatements.filter(
                    ClosingBalance_currency=currency
                ).latest()
                prev_balance = stmt.ClosingBalance
                since = stmt.created
            except AccountStatement.DoesNotExist:
                prev_balance = Money(0, currency)
                since = None

            # Calculate changes since last statement
            balance_change = self.calculate_balance(currency, since)
            balances.append(prev_balance + balance_change)
            print(
                f"Currency: {currency}, Previous Balance: {prev_balance}, Change: {balance_change}, Current Balance: {prev_balance + balance_change}"
            )

        return Balance(balances)

    # Balance from the postgres view - read-only, always reflects latest state without needing statements
    def get_current_balance(self):
        """Get current balance using the account_balances view (METHOD 2: Database View - RECOMMENDED)

        This method queries the PostgreSQL view 'account_balances' which:
        1. Aggregates ALL AccountTransaction records for this account
        2. Groups by currency
        3. Calculates: last_statement_balance + (dr_sum - cr_sum) or (cr_sum - dr_sum)
           depending on account type (Debtor vs Creditor)

        When to use:
        - For real-time balance queries (default choice)
        - For reports requiring current balances (AR Aging, Customer Statements)
        - For credit limit checks

        Performance: O(1) - View is pre-aggregated by PostgreSQL

        Database View Definition:
        See migration 0003_create_ledger_balance_view.py for SQL definition

        Example:
        >>> customer_account = Account.objects.get(contact__name='ABC Corp')
        >>> balance_obj = customer_account.get_current_balance()
        >>> inr_balance = balance_obj.get('INR')  # Returns Money object
        >>> print(f"ABC Corp owes: {inr_balance}")

        Returns:
            Balance: Object containing Money amounts per currency
        """
        balances = []
        for balance in AccountBalance.objects.filter(account=self):
            balances.append(Money(balance.current_balance, balance.currency))
        return Balance(balances)

    def audit(self):
        """Create audit statements to snapshot current balances for each currency

        Purpose:
        - Creates AccountStatement records (balance snapshots) for each active currency
        - Future incremental balance calculations use these as starting points
        - Improves performance of current_balance() method by reducing transaction scans

        When to call:
        - End of accounting period (month/quarter/year close)
        - After bulk transaction imports
        - When account has many transactions (>1000)
        - Before generating historical reports

        Process:
        1. Get current live balance from account_balances view
        2. Create AccountStatement record for each currency
        3. Store total debits, credits, and closing balance
        4. These become checkpoints for future current_balance() calls

        Example:
        >>> customer_account = Account.objects.get(contact__name='ABC Corp')
        >>> statements = customer_account.audit()  # Creates snapshots
        >>> # Now current_balance() only scans transactions AFTER these snapshots

        Returns:
            list: AccountStatement objects created (one per active currency)
        """
        statements = []
        current_balances = self.get_current_balance()  # Get balances from view

        for currency in self.get_active_currencies():
            balance = current_balances.get(currency, Money(0, currency))

            # Create new statement using the verified balance
            stmt = AccountStatement.objects.create(
                AccountNo=self,
                ClosingBalance=balance,
                TotalCredit=self.total_credit().get(currency, Money(0, currency)),
                TotalDebit=self.total_debit().get(currency, Money(0, currency)),
            )
            statements.append(stmt)

        return statements


# account statement for ext account
class AccountStatement(models.Model):
    AccountNo = models.ForeignKey(
        Account, on_delete=models.CASCADE, related_name="accountstatements"
    )
    period = models.ForeignKey(
        "AccountingPeriod",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="account_statements",
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
        # validators=[MinValueValidator(limit_value=0.0)],
    )
    TotalCredit = MoneyField(
        max_digits=13,
        decimal_places=3,
        default_currency="INR",
        # validators=[MinValueValidator(limit_value=0.0)],
    )
    TotalDebit = MoneyField(
        max_digits=13,
        decimal_places=3,
        default_currency="INR",
        # validators=[MinValueValidator(limit_value=0.0)],
    )
    is_opening_statement = models.BooleanField(
        default=False,
        help_text="True if this is an opening balance statement, False if closing",
    )

    class Meta:
        get_latest_by = "created"
        ordering = ("created",)
        indexes = [
            models.Index(
                fields=[
                    "AccountNo",
                ]
            ),
            models.Index(fields=["period", "is_opening_statement"]),
        ]
        unique_together = [
            ["AccountNo", "ClosingBalance_currency", "created"],
            ["AccountNo", "period", "is_opening_statement"],
        ]

    def __str__(self):
        stmt_type = "Opening" if self.is_opening_statement else "Closing"
        period_str = f" ({self.period})" if self.period else ""
        return f"{self.id} | {stmt_type} | {self.AccountNo} = {self.ClosingBalance}{period_str}"

    def get_cb(self):
        return self.ClosingBalance


# sales,purchase,receipt,payment,loan,release
class TransactionType_Ext(models.Model):
    XactTypeCode_ext = models.CharField(max_length=4, primary_key=True)
    description = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.XactTypeCode_ext} | {self.description}"


class AccountTransactionManager(models.Manager):
    def create_txn(
        self, journal_entry, ledgerno, XactTypeCode, XactTypeCode_ext, Account, amount
    ):
        ledger = Ledger.objects.get(name=ledgerno)
        xc = TransactionType_DE.objects.get(XactTypeCode=XactTypeCode)
        xc_ext = TransactionType_Ext.objects.get(XactTypeCode_ext=XactTypeCode_ext)
        txn = self.create(
            journal_entry=journal_entry,
            ledgerno=ledger,
            XactTypeCode=xc,
            XactTypeCode_ext=xc_ext,
            Account=Account,
            amount=amount,
        )
        return txn


class AccountTransaction(models.Model):
    journal_entry = models.ForeignKey(
        "JournalEntry", on_delete=models.CASCADE, related_name="atxns"
    )
    # ledger to be credited or debited opp action of XactTypeCode(cr,dr) against account
    ledgerno = models.ForeignKey(
        "Ledger", on_delete=models.CASCADE, related_name="aleg"
    )
    created = models.DateTimeField(
        auto_now_add=True,
        # unique = True
    )
    XactTypeCode = models.ForeignKey(TransactionType_DE, on_delete=models.CASCADE)
    # xacttypecode_ext denotes the kind of transaction like sales,purchase...etc
    XactTypeCode_ext = models.ForeignKey(TransactionType_Ext, on_delete=models.CASCADE)
    Account = models.ForeignKey(
        Account, on_delete=models.CASCADE, related_name="accounttransactions"
    )
    amount = MoneyField(
        max_digits=13,
        decimal_places=3,
        default_currency="INR",
        # validators=[MinValueValidator(limit_value=0.0)],
    )
    objects = AccountTransactionManager()

    class Meta:
        ordering = ("created",)
        indexes = [
            models.Index(
                fields=[
                    "ledgerno",
                ]
            ),
        ]

    def __str__(self):
        return f"{self.XactTypeCode_ext}"

    def get_voucher_url(self):
        # voucher = self.journal_entry.content_object
        # return voucher.get_absolute_url()
        return self.journal_entry.get_voucher_url()


class AccountBalance(models.Model):
    """PostgreSQL View: Real-time account balance aggregation (READ-ONLY)

    This is NOT a regular Django model - it's a view (managed=False).
    The 'account_balances' view is created by migration 0003 and provides
    real-time balance calculations without manually creating AccountStatement snapshots.

    View Structure:
    ---------------
    For each Account + Currency combination:

    1. last_statement_balance: Most recent AccountStatement.ClosingBalance (if any)
    2. debit_sum: Sum of DR transactions SINCE last statement
    3. credit_sum: Sum of CR transactions SINCE last statement
    4. current_balance: Calculated based on account type:
       - Debtor accounts: last_statement_balance + debit_sum - credit_sum
       - Creditor accounts: last_statement_balance + credit_sum - debit_sum

    Query Examples:
    --------------
    # Get balance for specific account
    >>> balance = AccountBalance.objects.get(account_id=customer.account.id, currency='INR')
    >>> print(f"Current balance: {balance.get_balance()}")

    # Top 10 debtor accounts
    >>> top_debtors = AccountBalance.objects.filter(
    ...     currency='INR',
    ...     current_balance__gt=0
    ... ).order_by('-current_balance')[:10]

    # Total AR across all customers
    >>> total_ar = AccountBalance.objects.filter(
    ...     AccountType_Ext__XactTypeCode_id='Dr',
    ...     currency='INR'
    ... ).aggregate(total=Sum('current_balance'))['total']

    Performance:
    -----------
    - O(1) per query (pre-aggregated by PostgreSQL)
    - Automatically updates when AccountTransaction records change
    - No manual refresh needed (standard VIEW, not MATERIALIZED VIEW)

    Data Integrity:
    --------------
    - This view always reflects the LATEST data from AccountTransaction
    - For audit purposes, use AccountStatement snapshots instead
    - Verify: SUM(customer_balances) should equal Ledger 'Accounts Receivable' balance
    """

    account = models.OneToOneField(
        Account, primary_key=True, db_column="account_id", on_delete=models.DO_NOTHING
    )
    contact = models.ForeignKey(
        "contact.Customer", db_column="contact_id", on_delete=models.DO_NOTHING
    )
    AccountType_Ext = models.ForeignKey(
        "AccountType_Ext", db_column="AccountType_Ext_id", on_delete=models.DO_NOTHING
    )
    currency = models.CharField(max_length=3)
    last_statement_date = models.DateTimeField(null=True)
    last_statement_balance = models.DecimalField(
        max_digits=15, decimal_places=3, default=0
    )
    credit_sum = models.DecimalField(max_digits=15, decimal_places=3, default=0)
    debit_sum = models.DecimalField(max_digits=15, decimal_places=3, default=0)
    current_balance = models.DecimalField(max_digits=15, decimal_places=3, default=0)

    class Meta:
        managed = False
        db_table = "account_balances"

    def __str__(self):
        return f"{self.account} - Balance: {self.get_balance()}"

    def get_ob(self):
        return Balance(Money(self.last_statement_balance, self.currency))

    def get_balance(self):
        return Money(self.current_balance, self.currency)

    def get_available_credit(self):
        """Calculate available credit based on current balance and account's credit limit"""
        if not self.account.credit_limit:
            return None

        current_bal = self.get_balance()
        if self.account.AccountType_Ext.XactTypeCode_id == "Dr":
            available = self.account.credit_limit - current_bal
            return max(available, Money(0, self.account.credit_limit.currency))
        return self.account.credit_limit
