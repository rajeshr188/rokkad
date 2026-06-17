from django.core.cache import cache
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Rate


@receiver(post_save, sender=Rate)
def update_rate_cache(sender, instance, **kwargs):
    for key in ("rate_gold_buying", "rate_silver_buying", "rate_bronze_buying"):
        cache.delete(key)

    if instance.metal == Rate.Metal.GOLD:
        cache.set("gold_rate", instance)
    elif instance.metal == Rate.Metal.SILVER:
        cache.set("silver_rate", instance)
    elif instance.metal == Rate.Metal.BRONZE:
        cache.set("bronze_rate", instance)
