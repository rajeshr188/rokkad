import logging

from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models import Sum
from django.urls import reverse
from djmoney.models.fields import MoneyField
from moneyed import Money
from mptt.models import MPTTModel, TreeForeignKey

from ..utils.currency import Balance
from .moneyvalue import MoneyValueField

logger = logging.getLogger(__name__)


# ledger account type  for COA ,asset,liability,revenue,expense,gain,loss
class AccountType(models.Model):
    AccountType = models.CharField(max_length=50)
    description = models.CharField(max_length=100)

    def __str__(self):
        return self.AccountType


# ledger is chart of accounts
# add ledgerno
class Ledger(MPTTModel):
    AccountType = models.ForeignKey(
        AccountType, on_delete=models.CASCADE, related_name="ledgers"
    )
    name = models.CharField(max_length=100)
    parent = TreeForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="children"
    )
    # objects = LedgerManager()

    class MPTTMeta:
        order_insertion_by = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["name", "parent"], name="unique ledgername-parent"
            )
        ]

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["name", "parent"], name="unique_ledgername_parent"
            )
        ]

    def __str__(self):
        return f"{self.name} - {self.AccountType}"

    def get_absolute_url(self):
        return reverse("dea_ledger_detail", kwargs={"pk": self.pk})

    def get_latest_stmt(self):
        try:
            return self.ledgerstatements.latest()
        except LedgerStatement.DoesNotExist:
            return None

    def get_closing_balance(self):
        # just return the ledgerbalance views closing balance
        ls = self.get_latest_stmt()
        if ls is None:
            return Balance(self.ledgerbalance.ClosingBalance)
        else:
            return Balance(ls.ClosingBalance)

    def set_opening_bal(self, amount):
        # ensure there aint no txns before setting op bal if present then audit and adjust
        return LedgerStatement.objects.create(self, amount)

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

    def audit(self):
        # this statement will serve as opening balance for this acc
        return LedgerStatement.objects.create(
            ledgerno=self, ClosingBalance=self.current_balance().monies()
        )

    def current_balance_wrt_descendants(self):
        # decendants = self.get_descendants(include_self = True)

        # bal = [Balance([Money(r["total"], r["amount_currency"])
        #                 for r in acc.debit_txns.values("amount_currency").annotate(total = Sum("amount"))])
        #         -
        #        Balance([Money(r["total"], r["amount_currency"])
        #                 for r in acc.credit_txns.values("amount_currency").annotate(total = Sum("amount"))])
        #         for acc in decendants
        #         ]

        descendants = [
            i.get_balance() for i in self.get_descendants(include_self=False)
        ]
        bal = sum(descendants, self.get_balance())
        return bal

    def get_credit_bal(self, since=None):
        c_bal = (
            Balance(
                [
                    Money(r["total"], r["amount_currency"])
                    for r in self.ctxns(since)
                    .values("amount_currency")
                    .annotate(total=Sum("amount"))
                ]
            )
            if self.ctxns(since=since)
            else Balance()
        )
        aleg_cr = Balance(
            [
                Money(r["total"], r["amount_currency"])
                for r in self.aleg_txns(since, "Cr")
                .values("amount_currency")
                .annotate(total=Sum("amount"))
            ]
        )
        return c_bal + aleg_cr

    def get_debit_bal(self, since=None):
        d_bal = (
            Balance(
                [
                    Money(r["total"], r["amount_currency"])
                    for r in self.dtxns(since)
                    .values("amount_currency")
                    .annotate(total=Sum("amount"))
                ]
            )
            if self.dtxns(since=since)
            else Balance()
        )
        aleg_dr = Balance(
            [
                Money(r["total"], r["amount_currency"])
                for r in self.aleg_txns(since, "Dr")
                .values("amount_currency")
                .annotate(total=Sum("amount"))
            ]
        )
        return d_bal + aleg_dr

    def current_balance(self):
        ls = self.get_latest_stmt()
        if ls is None:
            cb = Balance()
            since = None
        else:
            cb = ls.get_cb()
            since = ls.created

        credit_balance = self.get_credit_bal(since)  # credit balance with aleg
        debit_balance = self.get_debit_bal(since)  # debit balance with aleg
        # logger.warning(
        #     f"credit_balance: {credit_balance} debit_balance: {debit_balance}"
        # )

        bal = cb + (debit_balance - credit_balance)
        return bal

    def current_balance_with_aleg(self):
        ls = self.get_latest_stmt()
        if ls is None:
            cb = Balance()
            since = None
        else:
            cb = ls.get_cb()
            since = ls.created
        c_bal = (
            Balance(
                [
                    Money(r["total"], r["amount_currency"])
                    for r in self.ctxns(since)
                    .values("amount_currency")
                    .annotate(total=Sum("amount"))
                ]
            )
            if self.ctxns(since=since)
            else Balance()
        )
        d_bal = (
            Balance(
                [
                    Money(r["total"], r["amount_currency"])
                    for r in self.dtxns(since)
                    .values("amount_currency")
                    .annotate(total=Sum("amount"))
                ]
            )
            if self.dtxns(since=since)
            else Balance()
        )
        aleg_cr = Balance(
            [
                Money(r["total"], r["amount_currency"])
                for r in self.aleg_txns(since, "Cr")
                .values("amount_currency")
                .annotate(total=Sum("amount"))
            ]
        )
        aleg_dr = Balance(
            [
                Money(r["total"], r["amount_currency"])
                for r in self.aleg_txns(since, "Dr")
                .values("amount_currency")
                .annotate(total=Sum("amount"))
            ]
        )

        bal = cb + (d_bal - c_bal) + (aleg_cr - aleg_dr)
        return bal

    def get_balance(self):
        return self.ledgerbalance.get_currbal()

    # -------------------ditching custom postgres money_value----------------

    # def get_closing_balance(self):
    #     """Get closing balance in all active currencies"""
    #     balances = []

    #     # Get all active currencies for this ledger
    #     for currency in self.get_active_currencies():
    #         try:
    #             # Get latest statement for this currency
    #             stmt = self.ledgerstatements.filter(
    #                 ClosingBalance_currency=currency
    #             ).latest()
    #             balances.append(stmt.ClosingBalance)
    #         except LedgerStatement.DoesNotExist:
    #             # If no statement exists for this currency, add zero balance
    #             balances.append(Money(0, currency))

    #     return Balance(balances)

    # def get_active_currencies(self):
    #     """Get list of currencies used in this ledger's transactions"""
    #     currencies = set()
    #     currencies.update(self.credit_txns.values_list('amount_currency', flat=True).distinct())
    #     currencies.update(self.debit_txns.values_list('amount_currency', flat=True).distinct())
    #     currencies.update(self.aleg.values_list('amount_currency', flat=True).distinct())
    #     return list(currencies)

    # def calculate_balance(self, currency, since=None):
    #     """Calculate balance changes for specific currency since given date"""
    #     # Base filters for currency
    #     credit_filters = {'amount_currency': currency}
    #     debit_filters = {'amount_currency': currency}

    #     # Add date filter only if since is not None
    #     if since:
    #         credit_filters['created__gt'] = since
    #         debit_filters['created__gt'] = since

    #     # Get credits with proper filters
    #     credit_sum = self.credit_txns.filter(
    #         **credit_filters
    #     ).aggregate(total=Sum('amount'))['total'] or 0

    #     aleg_credit_sum = self.aleg.filter(
    #         **credit_filters,
    #         XactTypeCode='Cr'
    #     ).aggregate(total=Sum('amount'))['total'] or 0

    #     # Get debits with proper filters
    #     debit_sum = self.debit_txns.filter(
    #         **debit_filters
    #     ).aggregate(total=Sum('amount'))['total'] or 0

    #     aleg_debit_sum = self.aleg.filter(
    #         **debit_filters,
    #         XactTypeCode='Dr'
    #     ).aggregate(total=Sum('amount'))['total'] or 0

    #     return Money(
    #         (debit_sum + aleg_debit_sum) - (credit_sum + aleg_credit_sum),
    #         currency
    #     )

    # def current_balance(self):
    #     """Get current balance in all active currencies"""
    #     balances = []
    #     for currency in self.get_active_currencies():
    #         # Get latest statement for this currency
    #         try:
    #             stmt = self.ledgerstatements.filter(
    #                 ClosingBalance_currency=currency
    #             ).latest()
    #             prev_balance = stmt.ClosingBalance
    #             since = stmt.created
    #         except LedgerStatement.DoesNotExist:
    #             prev_balance = Money(0, currency)
    #             since = None

    #         # Calculate changes since last statement
    #         balance_change = self.calculate_balance(currency, since)
    #         balances.append(prev_balance + balance_change)

    #     return Balance(balances)

    # def audit(self):
    #     """Create statements for all active currencies"""
    #     statements = []
    #     for currency in self.get_active_currencies():
    #         balance = self.current_balance().get(currency)
    #         stmt = LedgerStatement.objects.create(
    #             ledgerno=self,
    #             ClosingBalance=balance
    #         )
    #         statements.append(stmt)
    #     return statements


class LedgerTransactionManager(models.Manager):
    def create_txn(self, journal_entry, ledgerno, ledgerno_dr, amount):
        dr = Ledger.objects.get(name=ledgerno_dr)
        cr = Ledger.objects.get(name=ledgerno)
        txn = self.create(
            journal_entry=journal_entry, ledgerno=cr, ledgerno_dr=dr, amount=amount
        )
        return txn


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
    objects = LedgerTransactionManager()

    class Meta:
        indexes = [
            models.Index(
                fields=[
                    "ledgerno",
                ]
            ),
            models.Index(
                fields=[
                    "ledgerno_dr",
                ]
            ),
        ]

    def __str__(self):
        return self.ledgerno.name


class LedgerStatement(models.Model):
    ledgerno = models.ForeignKey(
        Ledger, on_delete=models.CASCADE, related_name="ledgerstatements"
    )
    created = models.DateTimeField(
        # unique = True,
        auto_now_add=True
    )
    # ClosingBalance = MoneyField(
    #     max_digits=13,
    #     decimal_places=3,
    #     default_currency="INR",
    # )
    ClosingBalance = ArrayField(MoneyValueField(null=True, blank=True))

    class Meta:
        # unique_together = ['ledgerno', 'ClosingBalance_currency', 'created']
        get_latest_by = "created"
        ordering = ["-created"]

    def __str__(self):
        return f"{self.created.date()} - {self.ledgerno} - {self.ClosingBalance}"

    def get_cb(self):
        return Balance(self.ClosingBalance)


# postgresql read-only-view
class Ledgerbalance(models.Model):
    ledgerno = models.OneToOneField(
        Ledger,
        on_delete=models.DO_NOTHING,
        primary_key=True,
        related_name="ledgerbalance",
    )
    # name = models.CharField(max_length=100)
    # AccountType = models.CharField(max_length=50)
    statement_created = models.DateTimeField()
    opening_balance = ArrayField(
        MoneyValueField(blank=True, null=True), blank=True, null=True
    )
    closing_balance = ArrayField(
        MoneyValueField(blank=True, null=True), blank=True, null=True
    )
    credit = ArrayField(MoneyValueField(blank=True, null=True), blank=True, null=True)
    debit = ArrayField(MoneyValueField(blank=True, null=True), blank=True, null=True)

    class Meta:
        managed = False
        db_table = "resultlb11"
        # ordering = ["ledgerno__AccountType", "ledgerno__name"]

    def get_currbal(self):
        return Balance(self.closing_balance)

    def get_ob(self):
        return Balance(self.opening_balance)

    def get_cb(self):
        return Balance(self.closing_balance)

    def get_running_balance(self):
        return sum(
            [
                i.ledgerbalance.get_currbal()
                for i in self.ledgerno.get_descendants(include_self=True)
            ],
            Balance(),
        )

    def get_dr(self):
        return Balance(self.debit)

    def get_cr(self):
        return Balance(self.credit)
