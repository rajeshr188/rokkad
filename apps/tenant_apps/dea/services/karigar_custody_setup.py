from dataclasses import dataclass

from apps.tenant_apps.dea.models import Commodity, CommodityAccount
from apps.tenant_apps.party.models import Party


@dataclass(frozen=True)
class KarigarCustodySetupResult:
    account: CommodityAccount
    created: bool


def ensure_karigar_custody_account(
    *,
    commodity: Commodity,
    party: Party,
    code: str = "",
    name: str = "",
    location_label: str = "",
) -> KarigarCustodySetupResult:
    existing = CommodityAccount.objects.filter(
        commodity=commodity,
        purpose=CommodityAccount.Purpose.KARIGAR_CUSTODY,
        party=party,
    ).first()
    if existing:
        return KarigarCustodySetupResult(account=existing, created=False)

    normalized_code = code or f"{commodity.code}_KARIGAR_{party.party_code.replace('-', '_')}"
    normalized_name = name or f"{commodity.name} karigar custody - {party.display_name}"
    normalized_location = location_label or f"{party.display_name} custody"

    account = CommodityAccount.objects.create(
        code=normalized_code,
        name=normalized_name,
        commodity=commodity,
        purpose=CommodityAccount.Purpose.KARIGAR_CUSTODY,
        party=party,
        location_label=normalized_location,
    )
    return KarigarCustodySetupResult(account=account, created=True)
