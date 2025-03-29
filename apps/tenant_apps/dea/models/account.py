import logging

from django import db
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models import Sum
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from djmoney.models.fields import MoneyField
from moneyed import Money

from apps.tenant_apps.contact.models import Customer

from ..managers.managers import AccountManager
from ..utils.currency import Balance
from .ledger import Ledger
from .moneyvalue import MoneyValueField

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
# add accountno
class Account(models.Model):
    entity = models.ForeignKey(
        EntityType,
        null=True,
        on_delete=models.SET_NULL,
        default="Person",
    )
    AccountType_Ext = models.ForeignKey(
        AccountType_Ext,
        on_delete=models.CASCADE,
    )

    contact = models.OneToOneField(
        Customer, on_delete=models.CASCADE, related_name="account"
    )
    objects = AccountManager()

    class Meta:
        ordering = ("id",)
        constraints = [
            models.UniqueConstraint(fields=["contact"], name="unique_contact_account")
        ]

    def __str__(self):
        return f"{self.id} | {self.contact} | {self.AccountType_Ext}"

    def get_absolute_url(self):
        return reverse("dea_account_detail", kwargs={"pk": self.pk})

    def set_opening_bal(self, amount):
        # amount is a MoneyField
        # ensure there aint no txns before setting op bal if present then audit and adjust
        return AccountStatement.objects.create(self, ClosingBalance=amount)

    def adjust(self, amount, xacttypecode):
        pass

    def audit(self):
        ls = self.latest_stmt()
        if ls is None:
            since = None
        else:
            since = ls.created
        credit_t = self.total_credit(since=since).monies()
        debit_t = self.total_debit(since=since).monies()
        return AccountStatement.objects.create(
            AccountNo=self,
            ClosingBalance=self.current_balance().monies(),
            TotalCredit=credit_t,
            TotalDebit=debit_t,
        )

    def latest_stmt(self):
        try:
            return self.accountstatements.latest()
        except AccountStatement.DoesNotExist:
            return None

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

    # def current_balance(self):
    #     # return self.total_credit(since =) - self.total_debit(since =)
    #     ls = self.latest_stmt()
    #     if ls is None:
    #         cb = Balance()
    #         ac_txn = self.txns()
    #         cr_bal = self.total_credit()
    #         dr_bal = self.total_debit()
    #     else:
    #         cb = ls.get_cb()
    #         ac_txn = self.txns(since=ls.created)
    #         cr_bal = self.total_credit(since=ls.created)
    #         dr_bal = self.total_debit(since=ls.created)

    #     logger.info(f"cr_bal:{cr_bal} dr_bal:{dr_bal}")
    #     if self.AccountType_Ext.XactTypeCode_id == "Dr":
    #         bal = cb + (dr_bal - cr_bal)
    #     else:
    #         bal = cb + (cr_bal - dr_bal)

    #     logger.info(f"bal:{bal}")
    #     return bal

    # def current_balance(self):
    # chatgpt suggested this change
    #     latest_statement = self.latest_stmt()
    #     closing_balance = Balance() if latest_statement is None else latest_statement.get_cb()
    #     transactions = self.txns() if latest_statement is None else self.txns(since=latest_statement.created)
    #     total_credit = self._calculate_total(transactions, "Cr")
    #     total_debit = self._calculate_total(transactions, "Dr")
    #     current_balance = closing_balance + (total_debit - total_credit) if self.account_type_ext.XactTypeCode_id == "Dr" else closing_balance + (total_credit - total_debit)
    #     logger.info(f"Current balance: {current_balance}")
    #     return current_balance

    def current_balance(self):
        # Retrieve the latest statement
        latest_statement = self.latest_stmt()

        # Initialize balances
        if latest_statement is None:
            closing_balance = Balance()
            transactions = self.txns()
        else:
            closing_balance = latest_statement.get_cb()
            transactions = self.txns(since=latest_statement.created)

        # Calculate total credits and debits
        total_credit = self._calculate_total(transactions, "Cr")
        total_debit = self._calculate_total(transactions, "Dr")

        # Adjust balance based on account type
        if self.AccountType_Ext.XactTypeCode_id == "Dr":
            current_balance = closing_balance + (total_debit - total_credit)
        else:
            current_balance = closing_balance + (total_credit - total_debit)

        logger.info(f"Current balance: {current_balance}")
        return current_balance

    def _calculate_total(self, transactions, xact_type_code):
        return Balance(
            [
                Money(result["total"], result["amount_currency"])
                for result in transactions.filter(
                    XactTypeCode__XactTypeCode=xact_type_code
                )
                .values("amount_currency")
                .annotate(total=Sum("amount"))
            ]
        )

    def get_balance(self):
        return self.accountbalance

    # # ------------------------ditch custom postgres money_value type------------------------

    # def get_active_currencies(self):
    #     """Get list of currencies used in this account's transactions"""
    #     return list(self.accounttransactions.values_list(
    #         'amount_currency', flat=True
    #     ).distinct())

    # def calculate_balance(self, currency, since=None):
    #     """Calculate balance changes for specific currency since given date"""
    #     transactions = self.accounttransactions.filter(
    #         amount_currency=currency,
    #         created__gt=since if since else None
    #     )

    #     credits = transactions.filter(
    #         XactTypeCode__XactTypeCode='Cr'
    #     ).aggregate(total=Sum('amount'))['total'] or 0

    #     debits = transactions.filter(
    #         XactTypeCode__XactTypeCode='Dr'
    #     ).aggregate(total=Sum('amount'))['total'] or 0

    #     if self.AccountType_Ext.XactTypeCode_id == 'Dr':
    #         return debits - credits
    #     else:
    #         return credits - debits

    # def current_balance(self):
    #     """Get current balance in all active currencies"""
    #     balances = []
    #     for currency in self.get_active_currencies():
    #         try:
    #             # Get latest statement for this currency
    #             stmt = self.accountstatements.filter(
    #                 ClosingBalance_currency=currency
    #             ).latest()
    #             prev_balance = stmt.ClosingBalance
    #             since = stmt.created
    #         except AccountStatement.DoesNotExist:
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
    #         # Get transactions since last statement
    #         try:
    #             last_stmt = self.accountstatements.filter(
    #                 ClosingBalance_currency=currency
    #             ).latest()
    #             since = last_stmt.created
    #         except AccountStatement.DoesNotExist:
    #             since = None

    #         # Calculate totals
    #         txns = self.accounttransactions.filter(
    #             amount_currency=currency,
    #             created__gt=since if since else None
    #         )

    #         total_credits = txns.filter(
    #             XactTypeCode__XactTypeCode='Cr'
    #         ).aggregate(total=Sum('amount'))['total'] or 0

    #         total_debits = txns.filter(
    #             XactTypeCode__XactTypeCode='Dr'
    #         ).aggregate(total=Sum('amount'))['total'] or 0

    #         # Calculate closing balance
    #         if self.AccountType_Ext.XactTypeCode_id == 'Dr':
    #             closing_balance = total_debits - total_credits
    #         else:
    #             closing_balance = total_credits - total_debits

    #         # Create new statement
    #         stmt = AccountStatement.objects.create(
    #             AccountNo=self,
    #             currency=currency,
    #             ClosingBalance=closing_balance,
    #             TotalCredit=total_credits,
    #             TotalDebit=total_debits
    #         )
    #         statements.append(stmt)

    #     return statements


# account statement for ext account
class AccountStatement(models.Model):
    AccountNo = models.ForeignKey(
        Account, on_delete=models.CASCADE, related_name="accountstatements"
    )
    created = models.DateTimeField(
        # unique = True,
        auto_now_add=True
    )
    # ClosingBalance = MoneyField(
    #     max_digits=13,
    #     decimal_places=3,
    #     default_currency="INR",
    #     # validators=[MinValueValidator(limit_value=0.0)],
    # )
    # TotalCredit = MoneyField(
    #     max_digits=13,
    #     decimal_places=3,
    #     default_currency="INR",
    #     # validators=[MinValueValidator(limit_value=0.0)],
    # )
    # TotalDebit = MoneyField(
    #     max_digits=13,
    #     decimal_places=3,
    #     default_currency="INR",
    #     # validators=[MinValueValidator(limit_value=0.0)],
    # )
    ClosingBalance = ArrayField(MoneyValueField(null=True, blank=True))
    TotalCredit = ArrayField(MoneyValueField(null=True, blank=True))
    TotalDebit = ArrayField(MoneyValueField(null=True, blank=True))

    class Meta:
        get_latest_by = "created"
        # Use _currency suffix that MoneyField automatically creates
        # unique_together = ['AccountNo', 'ClosingBalance_currency', 'created']

    def __str__(self):
        return f"{self.id} | {self.AccountNo} = {self.ClosingBalance}({self.TotalDebit} - {self.TotalCredit})"

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
        l = Ledger.objects.get(name=ledgerno)
        xc = TransactionType_DE.objects.get(XactTypeCode=XactTypeCode)
        xc_ext = TransactionType_Ext.objects.get(XactTypeCode_ext=XactTypeCode_ext)
        txn = self.create(
            journal_entry=journal_entry,
            ledgerno=l,
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


class Accountbalance(models.Model):
    AccountNo = models.OneToOneField(
        Account,
        on_delete=models.DO_NOTHING,
        primary_key=True,
        related_name="accountbalance",
    )
    ls_created = models.DateTimeField()
    opening_balance = ArrayField(MoneyValueField(null=True, blank=True))
    closing_balance = ArrayField(MoneyValueField(null=True, blank=True))
    cr = ArrayField(MoneyValueField(null=True, blank=True))
    dr = ArrayField(MoneyValueField(null=True, blank=True))

    class Meta:
        managed = False
        db_table = "account_balance"
        # db_table = "acc_bal_v4"

    def __str__(self):
        return f"{self.get_currbal()}"

    def get_currbal(self):
        # more like op + cb(dr-cr if acc.type == dr else cr-dr)
        if self.AccountNo.AccountType_Ext.XactTypeCode_id == "Dr":
            return Balance(self.opening_balance) - self.get_cb()
        # (self.get_cr() - self.get_dr())
        else:
            return (
                Balance(self.opening_balance) + self.get_cb()
            )  # (self.get_dr() - self.get_cr())

    def get_cb(self):
        return Balance(self.closing_balance)

    def get_cr(self):
        return Balance(self.cr)

    def get_dr(self):
        return Balance(self.dr)

    def get_ob(self):
        return Balance(self.opening_balance)


# class Accountbalance(models.Model):
#     AccountNo = models.OneToOneField(
#             Account,
#             on_delete=models.DO_NOTHING,
#             # primary_key=True,
#             related_name="accountbalance",
#         )
#     account_no_id = models.IntegerField(primary_key=True)
#     contact_id = models.IntegerField()
#     ls_created = models.DateTimeField()
#     opening_balance = ArrayField(MoneyValueField(null=True, blank=True))
#     cr = ArrayField(MoneyValueField(null=True, blank=True))
#     dr = ArrayField(MoneyValueField(null=True, blank=True))
#     closing_balance = ArrayField(MoneyValueField(null=True, blank=True))


#     class Meta:
#         managed = False
#         db_table = 'account_balance'
