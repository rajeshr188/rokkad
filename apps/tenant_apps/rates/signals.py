from django.core.cache import cache
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Rate


@receiver(post_save, sender=Rate)
def update_rate_cache(sender, instance, **kwargs):
    prefix = f"workspace:{instance.workspace_id}:"
    for key in ("rate_gold_buying", "rate_silver_buying", "rate_bronze_buying"):
        cache.delete(f"{prefix}{key}")

    cache_key = {
        Rate.Metal.GOLD: "gold_rate",
        Rate.Metal.SILVER: "silver_rate",
        Rate.Metal.BRONZE: "bronze_rate",
    }.get(instance.metal)
    if cache_key:
        cache.set(f"{prefix}{cache_key}", instance)
