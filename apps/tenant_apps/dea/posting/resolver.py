from django.core.cache import cache
from django.core.exceptions import ValidationError

from ..models.ledger import Ledger

CACHE_TTL = 300  # seconds
LEDGER_KEY_ALIASES = {
    "INTEREST_RECEIVABLE": ["INTEREST_RECEIVABLE", "Interest Receivables"],
}


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

    candidate_names = LEDGER_KEY_ALIASES.get(key, [key])
    qs = Ledger.objects.only("id", "name").filter(name__in=candidate_names)
    # If you have tenant scoping, use: qs = qs.filter(tenant_id=tenant_id)
    lid = None
    for candidate in candidate_names:
        match = qs.filter(name=candidate).first()
        if match:
            lid = match.id
            break

    if lid is None:
        raise ValidationError(f"Ledger with key '{key}' not found")

    cache.set(cache_key, lid, CACHE_TTL)
    return lid
