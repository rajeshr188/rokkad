from django.core.cache import cache
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Rate


@receiver(post_save, sender=Rate)
def update_rate_cache(sender, instance, **kwargs):
    if instance.metal == Rate.Metal.GOLD:
        cache.set("gold_rate", instance)
    elif instance.metal == Rate.Metal.SILVER:
        cache.set("silver_rate", instance)
