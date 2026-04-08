from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import Payment, Purchase, PurchaseItem

# @receiver(signals.pre_delete, sender=PaymentAllocation)
# def delete_status(sender, instance, *args, **kwargs):
#     print("updating purchase status")
#     inv = instance.invoice
#     inv.update_status()


@receiver(pre_save, sender=Payment)
@receiver(pre_save, sender=Purchase)
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


@receiver(pre_save, sender=PurchaseItem)
def reverse_stock_entry(sender, instance, **kwargs):
    print(" in pre_save:reverse stock entry")
    #     # Access model and subclass:
    if instance.pk:  # If journal is being updated
        # Retrieve the old data from the database
        old_instance = sender.objects.get(pk=instance.pk)
        if old_instance.is_changed(instance):
            old_instance.unpost()
            instance.post()


@receiver(post_save, sender=PurchaseItem)
def create_stock_entry(sender, instance, created, **kwargs):
    print(" in post_save:create stock entry")
    if created:
        instance.post()

    instance.invoice.save()
