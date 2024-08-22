from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models import F, Sum
from django.db.models.signals import post_delete, post_save, pre_delete, pre_save
from django.dispatch import receiver

from .models import Loan, LoanItem, LoanPayment


@receiver(pre_save, sender=LoanPayment)
@receiver(pre_save, sender=LoanItem)
@receiver(post_delete, sender=LoanItem)
def reverse_journal_entry(sender, instance, **kwargs):
    # print(" in pre_save:reverse journal entry")
    if instance.pk:  # If journal is being updated
        # Retrieve the old data from the database
        try:
            old_instance = sender.objects.get(pk=instance.pk)
        except ObjectDoesNotExist:
            # Handle the case where the instance does not exist in the database
            return
        # Compare the old and new instances
        if old_instance.is_changed(instance):
            # print("change of balances in instances")
            old_instance.reverse_transactions()
            instance.create_transactions()


@receiver(post_save, sender=LoanPayment)
@receiver(post_save, sender=LoanItem)
def create_journal_entry(sender, instance, created, **kwargs):
    # print(" in post_save:create journal entry")
    if created:
        instance.create_transactions()


@receiver([post_delete, post_save], sender=LoanItem)
def update_loan(sender, instance, **kwargs):
    loan = instance.loan
    loan.update()
    # loan.loan_amount = LoanItem.objects.filter(loan=loan).aggregate(total_loanamount=Sum('loanamount'))['total_loanamount']
    # loan.item_desc = ", ".join([item.itemdesc for item in LoanItem.objects.filter(loan=loan)])
    # loan.interest = LoanItem.objects.filter(loan=loan).aggregate(total_interest=Sum('interest'))['total_interest'] or 0
    # loan.save()
