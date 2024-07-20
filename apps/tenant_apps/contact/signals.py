from actstream import action
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.tenant_apps.dea.models import Account, AccountType_Ext, EntityType

from .models import Customer

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
    entity_t = EntityType.objects.get(name="Person")
    if instance.customer_type == "W" or instance.customer_type == "R":
        acct_d = AccountType_Ext.objects.get(description="Debtor")
        account, created = Account.objects.update_or_create(
            contact=instance, entity=entity_t, defaults={"AccountType_Ext": acct_d}
        )
    else:
        acct_c = AccountType_Ext.objects.get(description="Creditor")
        account, created = Account.objects.update_or_create(
            contact=instance, entity=entity_t, defaults={"AccountType_Ext": acct_c}
        )


# @receiver(post_save, sender=Customer)
# def add_account(sender, instance, created, **kwargs):
#     acct_c = AccountType_Ext.objects.get(description="Creditor")
#     acct_d = AccountType_Ext.objects.get(description="Debtor")
#     try:
#         acc = instance.account
#     except Account.DoesNotExist:
#         acc = None
#     if created or acc is None:
#         entity_t = EntityType.objects.get(name="Person")
#         if instance.customer_type == "W" or instance.customer_type == "R":
#             Account.objects.create(
#                 contact=instance, entity=entity_t, AccountType_Ext=acct_d
#             )
#         else:
#             Account.objects.create(
#                 contact=instance, entity=entity_t, AccountType_Ext=acct_c
#             )
#     else:
#         if instance.customer_type == "W" or instance.customer_type == "R":
#             instance.account.AccountType_Ext = acct_d
#         else:
#             instance.account.AccountType_Ext = acct_c
#         instance.account.save(update_fields=["AccountType_Ext"])
