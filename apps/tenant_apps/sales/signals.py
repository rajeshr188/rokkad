from django.db import transaction
from django.db.models import signals
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.tenant_apps.dea.models import JournalEntry
from apps.tenant_apps.sales.models import Invoice, InvoiceItem, Receipt

# @receiver(signals.post_delete, sender=ReceiptAllocation)
# def delete_status(sender, instance, *args, **kwargs):
#     print("deleting invoice status")
#     inv = instance.invoice
#     print(f"in bal :{inv.get_balance()}")
#     if inv.get_balance() == inv.balance:
#         inv.status = "Unpaid"
#     else:
#         inv.status = "PartialPaid"
#     inv.save()


@receiver(pre_save, sender=Receipt)
@receiver(pre_save, sender=Invoice)
def reverse_journal_entry(sender, instance, **kwargs):
    print(" in pre_save:reverse journal entry")
    if instance.pk:  # If journal is being updated
        # Retrieve the old data from the database
        try:
            old_instance = sender.objects.get(pk=instance.pk)
        except ObjectDoesNotExist:
            # Handle the case where the instance does not exist in the database
            return
        # Compare the old and new instances
        if old_instance.is_changed(instance):
            print("change of balances in instances")
            old_instance.reverse_transactions()
            instance.create_transactions()


@receiver(post_save, sender=Receipt)
@receiver(post_save, sender=Invoice)
def create_journal_entry(sender, instance, created, **kwargs):
    print(" in post_save:create journal entry")
    if created:
        with transaction.atomic():
            instance.create_transactions()


@receiver(pre_save, sender=InvoiceItem)
def reverse_stock_entry(sender, instance, **kwargs):
    #     # Access model and subclass:
    if instance.pk:  # If journal is being updated
        # Retrieve the old data from the database
        old_instance = sender.objects.get(pk=instance.pk)
        if old_instance.is_changed(instance):
            old_instance.unpost()
            instance.post()


@receiver(post_save, sender=InvoiceItem)
def create_stock_entry(sender, instance, created, **kwargs):
    if created:
        instance.post()

    instance.invoice.save()
