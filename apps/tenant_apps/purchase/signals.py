from django.db import transaction
from django.db.models import signals
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.forms import model_to_dict

from apps.tenant_apps.dea.models import JournalEntry

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


@receiver(post_save, sender=Payment)
@receiver(post_save, sender=Purchase)
def create_journal_entry(sender, instance, created, **kwargs):
    print(" in post_save:create journal entry")
    if created:
        with transaction.atomic():
            instance.create_transactions()


@receiver(pre_save, sender=PurchaseItem)
def reverse_stock_entry(sender, instance, **kwargs):
    print(" in pre_save:reverse stock entry")
    #     # Access model and subclass:
    if instance.pk:  # If journal is being updated
        # Retrieve the old data from the database
        old_instance = sender.objects.get(pk=instance.pk)
        if old_instance.is_changed(instance):
            if old_instance.stock_item.stockstatement_set.exists():
                old_instance.unpost()
                instance.post()
            else:
                old_instance.stock_item.stocktransaction_set.all().delete()
                stock_item = old_instance.stock_item
                stock_item.purchase_item = instance
                stock_item.variant = instance.product
                stock_item.weight = instance.weight
                stock_item.quantity = instance.quantity
                stock_item.purchase_touch = instance.touch
                stock_item.purchase_rate = (
                    instance.invoice.gold_rate
                    if instance.product.product.category.name == "Gold"
                    else instance.invoice.silver_rate
                )
                stock_item.huid = instance.huid
                stock_item.save()
                stock_item.transact(
                    weight=instance.weight,
                    quantity=instance.quantity,
                    movement_type="P",
                )


@receiver(post_save, sender=PurchaseItem)
def create_stock_entry(sender, instance, created, **kwargs):
    print(" in post_save:create stock entry")
    if created:
        instance.post()

    instance.invoice.save()
