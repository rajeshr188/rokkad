import logging

from django.core.exceptions import ObjectDoesNotExist
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .models import (
    BaseLoan,
    GivenLoan,
    TakenLoan,
    LoanItem,
    LoanPayment,
    RepledgedLoanItem,
)

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=LoanPayment)
@receiver(pre_save, sender=GivenLoan)
@receiver(pre_save, sender=TakenLoan)
@receiver(post_delete, sender=LoanPayment)
@receiver(post_delete, sender=GivenLoan)
@receiver(post_delete, sender=TakenLoan)
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
            old_instance.reverse_transactions()
            instance.create_transactions()


@receiver([post_delete, post_save], sender=LoanItem)
@receiver([post_save, post_delete], sender=RepledgedLoanItem)
def update_loan(sender, instance, **kwargs):
    try:
        # logger.info(f"Signal received for {sender.__name__}LoanItem with id {instance.id}")
        loan = instance.loan
        if loan is None:
            # logger.error("Loan instance is None")
            return
        # logger.warning(f"Updating Loan with id {loan.loan_id}")

        loan.update()
        # logger.warning(f"Loan with id {loan.loan_id} updated")
    except Exception as e:
        logger.warning(f"Error: {e}")
