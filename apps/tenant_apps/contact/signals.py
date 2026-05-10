import logging
from venv import logger

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.tenant_apps.dea.facade import ensure_customer_account

from .models import Customer

logger = logging.getLogger(__name__)

# models_to_track = [Model1, Model2, Model3]

# def send_action(sender, instance, created, **kwargs):
#     if created:
#         action.send(instance, verb='was created')
#     else:
#         action.send(instance, verb='was updated')


# for model in models_to_track:
#     post_save.connect(send_action, sender=model)
# @receiver(post_save, sender=Customer)
# def send_customer_action(sender, instance, created, **kwargs):
#     if created:
#         action.send(instance, verb="was created")
#     else:
#         action.send(instance, verb="was updated")


@receiver(post_save, sender=Customer)
def add_account(sender, instance, created, **kwargs):
    logger.info("Adding account")
    ensure_customer_account(instance)
