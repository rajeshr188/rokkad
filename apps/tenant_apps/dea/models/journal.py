import uuid

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models, transaction
from django.forms import model_to_dict
from django.urls import reverse

from .account import AccountTransaction
from .ledger import LedgerTransaction

# create a voucher you create a je
# edit voucher:
#     if changed and statement created after the voucher created then reverse the transactions and create new transactions
#     else if changed and statement created before the voucher created then update the transactions
#     else if not changed then do nothing

#  to change acc balance in gold to cash
#     1. create a receipt with gold as payment mode
#     2. create a payment with cash as payment mode
#     3. create a journal entry with both receipt and payment as voucher


def reverse_journal_entry(sender, instance, **kwargs):
    #     # Access model and subclass:
    if instance.pk:  # If journal is being updated
        # Retrieve the old data from the database
        old_instance = sender.objects.get(pk=instance.pk)
        if old_instance.is_changed(instance):
            with transaction.atomic():
                old_instance.reverse_transactions()
                instance.create_transactions()


def create_journal_entry(sender, instance, created, **kwargs):
    if created:
        with transaction.atomic():
            instance.create_transactions()


# no longer relevant
class Journal(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True, editable=False)
    created_by = models.ForeignKey(
        "users.CustomUser", on_delete=models.CASCADE, null=True, blank=True
    )
    desc = models.TextField(blank=True, null=True)
    uuid = models.UUIDField(
        unique=True, default=uuid.uuid4, editable=False, null=True, blank=True
    )

    class Meta:
        abstract = True

    def get_class_name(self):
        return self.__class__.__name__

    def get_items(self):
        # By default, return None or an empty list.
        return None

    def get_journal_entry(self, desc=None):
        if self.journal_entries.exists():
            return self.journal_entries.latest()
        else:
            return JournalEntry.objects.create(
                content_object=self, desc=self.__class__.__name__
            )

    def delete_journal_entry(self):
        if self.journal_entries.exists():
            self.journal_entries.delete()

    def get_transactions(self):
        lt = []
        at = []
        # to be defined by the subclass
        return lt, at

    def create_transactions(self):
        journal_entry = self.get_journal_entry()
        lt, at = self.get_transactions()
        if lt and at:
            journal_entry.transact(lt, at)

    def reverse_transactions(self):
        journal_entry = self.get_journal_entry()
        lt, at = self.get_transactions()
        if lt and at:
            journal_entry.untransact(lt, at)

    def is_changed(self, old_instance):
        # https://stackoverflow.com/questions/31286330/django-compare-two-objects-using-fields-dynamically
        # TODO efficient way to compare old and new instances
        # Implement logic to compare old and new instances
        # Compare all fields using dictionaries
        return model_to_dict(
            self, fields=["loan_amount", "customer", "lid"]
        ) != model_to_dict(old_instance, fields=["loan_amount", "customer", "lid"])

    # https://stackoverflow.com/questions/7792287/how-to-use-django-model-inheritance-with-signals
    @classmethod
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        models.signals.pre_save.connect(reverse_journal_entry, sender=cls)
        models.signals.post_save.connect(create_journal_entry, sender=cls)


class JournalEntry(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    desc = models.TextField(blank=True, null=True)
    # Below the mandatory fields for generic relation
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="item_entries",
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")

    parent_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="parent_entries",
    )
    parent_object_id = models.PositiveIntegerField(null=True, blank=True)
    parent_object = GenericForeignKey("parent_content_type", "parent_object_id")

    class Meta:
        get_latest_by = "id"
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
        ]

    def __str__(self):
        return f"#{self.id} - {self.content_type}# {self.object_id}"

    def get_absolute_url(self):
        return reverse("dea_journal_entry_detail", kwargs={"pk": self.pk})

    def get_voucher_url(self):
        # voucher = self.content_object
        # if voucher is not None:
        #     return voucher.get_absolute_url()
        # else:
        #     return None
        if self.parent_object is not None:
            return self.parent_object.get_absolute_url()
        elif self.content_object is not None:
            return self.content_object.get_absolute_url()
        else:
            return None

    def check_data_integrity(self, lt, at):
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
            xacttypecode = ""
            xacttypecode_ext = ""
            if i["XactTypeCode"] == "Cr":
                xacttypecode = "Dr"
                xacttypecode_ext = "AC"
            else:
                xacttypecode = "Cr"
                xacttypecode_ext = "AD"
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
