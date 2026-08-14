from dataclasses import dataclass, field

from apps.tenant_apps.dea.models import Commodity, CommodityAccount


@dataclass
class CommodityQuickSetupResult:
    created_codes: list[str] = field(default_factory=list)
    existing_codes: list[str] = field(default_factory=list)
    skipped_notes: list[str] = field(default_factory=list)


def setup_standard_commodity_accounts(commodity: Commodity) -> CommodityQuickSetupResult:
    result = CommodityQuickSetupResult()

    standard_accounts = [
        {
            "code": f"{commodity.code}_OWNED_STOCK",
            "name": f"{commodity.name} owned stock",
            "purpose": CommodityAccount.Purpose.OWNED_STOCK,
            "location_label": "Primary stock",
        },
        {
            "code": f"{commodity.code}_VAULT",
            "name": f"{commodity.name} vault",
            "purpose": CommodityAccount.Purpose.VAULT,
            "location_label": "Main vault",
        },
    ]

    for account_data in standard_accounts:
        existing = CommodityAccount.objects.filter(code=account_data["code"]).first()
        if existing:
            result.existing_codes.append(existing.code)
            continue

        account = CommodityAccount.objects.create(
            code=account_data["code"],
            name=account_data["name"],
            commodity=commodity,
            purpose=account_data["purpose"],
            location_label=account_data["location_label"],
        )
        result.created_codes.append(account.code)

    result.skipped_notes.append(
        "Karigar custody accounts are party-specific and still require manual creation."
    )
    return result
