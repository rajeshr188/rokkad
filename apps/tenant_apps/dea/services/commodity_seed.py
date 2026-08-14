from dataclasses import dataclass

from apps.tenant_apps.dea.models import Commodity


@dataclass(frozen=True)
class CanonicalCommodity:
    code: str
    name: str
    commodity_type: str
    default_uom: str


CANONICAL_COMMODITIES = (
    CanonicalCommodity(
        code="GOLD",
        name="Gold",
        commodity_type=Commodity.CommodityType.METAL,
        default_uom=Commodity.UnitOfMeasure.GRAM,
    ),
    CanonicalCommodity(
        code="SILVER",
        name="Silver",
        commodity_type=Commodity.CommodityType.METAL,
        default_uom=Commodity.UnitOfMeasure.GRAM,
    ),
)


def seed_default_commodities():
    created = 0
    updated = 0

    for commodity in CANONICAL_COMMODITIES:
        _obj, was_created = Commodity.objects.update_or_create(
            code=commodity.code,
            defaults={
                "name": commodity.name,
                "commodity_type": commodity.commodity_type,
                "default_uom": commodity.default_uom,
                "is_active": True,
            },
        )
        if was_created:
            created += 1
        else:
            updated += 1

    return {
        "created": created,
        "updated": updated,
        "total": len(CANONICAL_COMMODITIES),
    }
