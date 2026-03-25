from decimal import Decimal
from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.tenant_apps.dea.models.voucher import Voucher
from .account import AccountTransaction
from .ledger import LedgerTransaction
from django.utils.translation import gettext_lazy as _


User = get_user_model()
# create a voucher you create a je
# edit voucher:
#     if changed and statement created after the voucher created then reverse the transactions and create new transactions
#     else if changed and statement created before the voucher created then update the transactions
#     else if not changed then do nothing

#  to change acc balance in gold to cash
#     1. create a receipt with gold as payment mode
#     2. create a payment with cash as payment mode
#     3. create a journal entry with both receipt and payment as voucher


class JournalEntry(models.Model):
    # Audit fields
    posted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    posted_at = models.DateTimeField(auto_now_add=True)  # When this JE was created
    desc = models.TextField(blank=True, null=True)

    # Accounting period link
    period = models.ForeignKey(
        "AccountingPeriod",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="journal_entries",
        help_text="Accounting period this entry belongs to",
    )

    voucher = models.ForeignKey(
        Voucher, on_delete=models.PROTECT, related_name="journal_entries"
    )
    is_reversal_of = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="reversed_by",
    )

    class Meta:
        get_latest_by = "id"
        indexes = [
            models.Index(fields=["period", "posted_at"]),
            models.Index(fields=["voucher", "posted_at"]),
        ]
        permissions = [
            ("can_reverse_entry", "Can reverse journal entries"),
            ("can_delete_posted_entry", "Can delete posted entries"),
        ]
        verbose_name = _("Journal Entry")
        verbose_name_plural = _("Journal Entries")

    def __str__(self):
        status = "Posted" if self.is_posted else "Draft"
        return f"JE-{self.id} ({status}) - {self.voucher}"

    @property
    def is_posted(self):
        """
        Derive posting status from voucher status.
        Posted if voucher is POSTED (not DRAFT, not REVERSED).
        """
        from .voucher import VoucherStatus

        return self.voucher.status == VoucherStatus.POSTED

    def get_absolute_url(self):
        return reverse("dea_journal_entry_detail", kwargs={"pk": self.pk})

    def clean(self):
        """Validate journal entry before saving"""
        from .voucher import VoucherStatus

        # Prevent modification of posted entries
        if self.pk:
            original = JournalEntry.objects.get(pk=self.pk)
            # Check if original was posted (derived from voucher status)
            if original.voucher.status == VoucherStatus.POSTED:
                raise ValidationError(
                    "Cannot modify posted journal entries. Create a reversal entry instead."
                )

        # Validate period
        if self.period and not self.period.can_modify_transactions():
            raise ValidationError(
                f"Cannot post entries to {self.period.status} period. "
                f"Period must be OPEN for new entries."
            )

    def save(self, *args, **kwargs):
        """
        Auto-assign period if not specified and validate
        """
        from .period import AccountingPeriod
        from django.utils import timezone

        # Auto-assign current period if not specified
        if not self.period:
            # Use voucher date if available, otherwise today
            target_date = (
                getattr(self.voucher, "voucher_date", None) or timezone.now().date()
            )
            self.period = AccountingPeriod.objects.get_period_for_date(target_date)

            if not self.period:
                raise ValidationError(
                    f"No accounting period found for date {target_date}. "
                    "Please create an accounting period or specify one explicitly."
                )

        # Run validation
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Prevent deletion of posted entries"""
        from .voucher import VoucherStatus

        if self.voucher.status == VoucherStatus.POSTED:
            raise ValidationError(
                "Cannot delete posted journal entries. Create a reversal entry instead."
            )
        super().delete(*args, **kwargs)

    def validate_balanced(self):
        """
        Validate that debits equal credits for this journal entry.

        The two-sided design means each LedgerTransaction has:
        - ledgerno_dr (debit ledger)
        - ledgerno (credit ledger)
        - amount (same amount posted to both sides)

                Primary rule:
                - If ledger transactions exist, validate balance from ledger legs only.
                    Account transactions are subledger attribution and should not re-enter
                    the GL balancing equation.

                Fallback rule:
                - If no ledger transactions exist, validate using account transactions
                    so account-only entries (if any) are still checked.

        Returns (is_balanced, debit_total, credit_total, imbalance_by_currency)
        """
        from djmoney.money import Money

        ledger_txns = list(self.ltxns.all())
        account_txns = list(self.atxns.all())

        # Aggregate ledger transactions
        ledger_debits = {}
        ledger_credits = {}

        for txn in ledger_txns:
            currency = txn.amount.currency
            amount = txn.amount.amount

            # Debit side: ledgerno_dr receives the debit
            ledger_debits[currency] = ledger_debits.get(currency, Decimal("0")) + amount
            # Credit side: ledgerno receives the credit (same amount, opposite side)
            ledger_credits[currency] = (
                ledger_credits.get(currency, Decimal("0")) + amount
            )

        # Aggregate account transactions (used as fallback only)
        account_debits = {}
        account_credits = {}

        for txn in account_txns:
            currency = txn.amount.currency
            if txn.XactTypeCode.XactTypeCode == "Dr":
                account_debits[currency] = (
                    account_debits.get(currency, Decimal("0")) + txn.amount.amount
                )
            else:
                account_credits[currency] = (
                    account_credits.get(currency, Decimal("0")) + txn.amount.amount
                )

        use_ledger_basis = bool(ledger_txns)
        if use_ledger_basis:
            all_currencies = set(ledger_debits.keys()) | set(ledger_credits.keys())
            basis_debits = ledger_debits
            basis_credits = ledger_credits
        else:
            all_currencies = set(account_debits.keys()) | set(account_credits.keys())
            basis_debits = account_debits
            basis_credits = account_credits

        imbalances = {}
        is_balanced = True

        for currency in all_currencies:
            total_dr = basis_debits.get(currency, Decimal("0"))
            total_cr = basis_credits.get(currency, Decimal("0"))

            diff = abs(total_dr - total_cr)
            if diff > Decimal("0.01"):  # Allow for rounding tolerance
                is_balanced = False
                imbalances[currency] = Money(diff, currency)

        return is_balanced, basis_debits, basis_credits, imbalances

    def get_total_debit(self):
        """Get total debit amount from all transactions"""
        from ..utils.currency import Balance

        amounts = []

        # Ledger debits
        for txn in self.ltxns.all():
            amounts.append(txn.amount)

        # Account debits
        for txn in self.atxns.filter(XactTypeCode__XactTypeCode="Dr"):
            amounts.append(txn.amount)

        return Balance(amounts)

    def get_total_credit(self):
        """Get total credit amount from all transactions"""
        from ..utils.currency import Balance

        amounts = []

        # Ledger credits
        for txn in self.ltxns.all():
            amounts.append(txn.amount)

        # Account credits
        for txn in self.atxns.filter(XactTypeCode__XactTypeCode="Cr"):
            amounts.append(txn.amount)

        return Balance(amounts)

    def get_voucher_url(self):
        # if voucher is not None:
        #     return voucher.get_absolute_url()
        # else:
        #     return None
        # if self.parent_object is not None:
        #     return self.parent_object.get_absolute_url()
        # elif self.content_object is not None:
        #     return self.content_object.get_absolute_url()
        # else:
        #     return None
        pass

    # def check_data_integrity(self, lt, at):
    #    # check data integrity constraints before adding transactions chatgpt suggest
    #     total_debit_ledger = sum(i["amount"] for i in lt if i["XactTypeCode"] == "Dr")
    #     total_credit_ledger = sum(i["amount"] for i in lt if i["XactTypeCode"] == "Cr")
    #     total_debit_account = sum(i["amount"] for i in at if i["XactTypeCode"] == "Dr")
    #     total_credit_account = sum(i["amount"] for i in at if i["XactTypeCode"] == "Cr")
    #     if total_debit_ledger != total_credit_ledger or total_debit_account != total_credit_account:
    #         raise ValueError("Transactions are not balanced")
    #     return True

    def check_data_integrity(self, ledger_transactions, account_transactions):
        # check data integrity constraints before adding transactions
        # for example, make sure the sum of debit amounts equals the sum of credit amounts
        # return True if all checks pass, False otherwise

        # Calculate total debit and credit amounts for ledger transactions
        total_debit_ledger = sum(
            amount
            for _, amount, transaction_type in ledger_transactions
            if transaction_type == "debit"
        )
        total_credit_ledger = sum(
            amount
            for _, amount, transaction_type in ledger_transactions
            if transaction_type == "credit"
        )

        # Calculate total debit and credit amounts for account transactions
        total_debit_account = sum(
            amount
            for _, amount, transaction_type in account_transactions
            if transaction_type == "debit"
        )
        total_credit_account = sum(
            amount
            for _, amount, transaction_type in account_transactions
            if transaction_type == "credit"
        )

        # Ensure the ledger transactions are balanced
        if total_debit_ledger != total_credit_ledger:
            raise ValueError("Ledger transactions are not balanced")

        # Ensure the account transactions are balanced
        if total_debit_account != total_credit_account:
            raise ValueError("Account transactions are not balanced")
        return True

    @transaction.atomic()
    def transact(self, lt, at):
        # add transactions to the journal
        # check data integrity constraints before adding transactions
        # if not self.check_data_integrity(lt,at):
        #     raise ValidationError("Data integrity violation.")

        for i in lt:
            # print(f"cr: {i['ledgerno']}dr:{i['ledgerno_dr']}")
            LedgerTransaction.objects.create_txn(
                self, i["ledgerno"], i["ledgerno_dr"], i["amount"]
            )

        for i in at:
            AccountTransaction.objects.create_txn(
                self,
                i["ledgerno"],
                i["XactTypeCode"],
                i["XactTypeCode_Ext"],
                i["Account"],
                i["amount"],
            )

    @transaction.atomic()
    def untransact(self, lt, at):
        for i in lt:
            # print(f"txn:{i}")
            # print(f"cr: {i['ledgerno']} dr:{i['ledgerno_dr']}")
            LedgerTransaction.objects.create_txn(
                self, i["ledgerno_dr"], i["ledgerno"], i["amount"]
            )

        for i in at:
            xacttypecode = "Dr" if i["XactTypeCode"] == "Cr" else "Cr"
            xacttypecode_ext = "AC" if i["XactTypeCode"] == "Cr" else "AD"
            AccountTransaction.objects.create_txn(
                self,
                i["ledgerno"],
                xacttypecode,
                xacttypecode_ext,
                i["Account"],
                i["amount"],
            )

    def get_next(self):
        return JournalEntry.objects.order_by("id").first()

    def get_previous(self):
        return JournalEntry.objects.order_by("id").last()
