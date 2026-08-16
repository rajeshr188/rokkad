from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from ..models import Price, PricingTier, PricingTierProductPrice


@dataclass(frozen=True)
class EffectivePrice:
    purchase_price: Decimal
    selling_price: Decimal
    source: str
    tier: Optional[PricingTier] = None


def resolve_effective_price(party, product) -> Optional[EffectivePrice]:
    """
    Resolve the effective unit prices for a party and product.

    Precedence:
    1) Walk tier hierarchy from party.pricing_tier upward and pick first hit.
    2) If a party-specific price exists, it overrides tier values.
    """

    tier_price = _resolve_tier_price(party=party, product=product)
    override_price = _resolve_party_override_price(party=party, product=product)

    if override_price is not None:
        return EffectivePrice(
            purchase_price=override_price.purchase_price,
            selling_price=override_price.selling_price,
            source="party_override",
            tier=tier_price.pricing_tier if tier_price else None,
        )

    if tier_price is not None:
        return EffectivePrice(
            purchase_price=tier_price.purchase_price,
            selling_price=tier_price.selling_price,
            source="tier",
            tier=tier_price.pricing_tier,
        )

    return None


def _resolve_tier_price(party, product) -> Optional[PricingTierProductPrice]:
    pricing_tier = getattr(party, "pricing_tier", None)
    while pricing_tier:
        pricing_tier_price = (
            PricingTierProductPrice.objects.filter(
                pricing_tier=pricing_tier,
                product=product,
            )
            .order_by("id")
            .first()
        )
        if pricing_tier_price:
            return pricing_tier_price
        pricing_tier = pricing_tier.parent
    return None


def _resolve_party_override_price(party, product) -> Optional[Price]:
    return (
        Price.objects.filter(
            party=party,
            product=product,
        )
        .order_by("id")
        .first()
    )
