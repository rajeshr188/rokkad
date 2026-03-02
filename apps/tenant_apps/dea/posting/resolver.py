from django.core.cache import cache
from django.core.exceptions import ValidationError
from ..models.ledger import Ledger

CACHE_TTL = 300  # seconds


def get_ledger_id_by_key(key: str, *, tenant_id: int | None = None) -> int:
    """
    Resolve a ledger ID by its stable key. If you have tenant scoping, include it in the cache key and filter.
    """
    if not key:
        raise ValidationError("Ledger key is required")

    cache_key = f"coa:ledger_id:{tenant_id or 'global'}:{key}"
    lid = cache.get(cache_key)
    if lid is not None:
        return lid

    qs = Ledger.objects.only("id").filter(name=key)
    # If you have tenant scoping, use: qs = qs.filter(tenant_id=tenant_id)
    try:
        lid = qs.get().id
    except Ledger.DoesNotExist:
        raise ValidationError(f"Ledger with key '{key}' not found")
    cache.set(cache_key, lid, CACHE_TTL)
    return lid
