from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from apps.tenant_apps.dea.models import Commodity, CommodityAccount, CommodityMovement
from apps.tenant_apps.party.models import Party


@dataclass(frozen=True)
class CommodityPositionRow:
    commodity_id: int
    commodity_code: str
    commodity_name: str
    account_id: int
    account_code: str
    account_name: str
    account_purpose: str
    party_id: int | None
    party_name: str
    location_label: str
    fixed_status: str
    uom: str
    gross_weight: Decimal
    fine_weight: Decimal


def get_commodity_position_rows(
    *,
    as_of: date | None = None,
    commodity: Commodity | None = None,
    account: CommodityAccount | None = None,
    party: Party | None = None,
    location_label: str | None = None,
) -> list[CommodityPositionRow]:
    movements = CommodityMovement.objects.select_related(
        "commodity",
        "from_account",
        "from_account__party",
        "to_account",
        "to_account__party",
    )
    if as_of is not None:
        movements = movements.filter(movement_date__lte=as_of)
    if commodity is not None:
        movements = movements.filter(commodity=commodity)

    positions: dict[tuple[int, str, str], dict] = {}
    for movement in movements.order_by("movement_date", "pk"):
        if movement.to_account_id and _account_matches(
            movement.to_account,
            account=account,
            party=party,
            location_label=location_label,
        ):
            _apply_movement(
                positions=positions,
                movement=movement,
                account=movement.to_account,
                sign=Decimal("1"),
            )
        if movement.from_account_id and _account_matches(
            movement.from_account,
            account=account,
            party=party,
            location_label=location_label,
        ):
            _apply_movement(
                positions=positions,
                movement=movement,
                account=movement.from_account,
                sign=Decimal("-1"),
            )

    rows = [
        _build_row(position)
        for position in positions.values()
        if position["gross_weight"] != 0 or position["fine_weight"] != 0
    ]
    return sorted(
        rows,
        key=lambda row: (
            row.commodity_code,
            row.account_code,
            row.fixed_status,
            row.uom,
        ),
    )


def get_commodity_position_for_account(
    account: CommodityAccount,
    *,
    as_of: date | None = None,
) -> list[CommodityPositionRow]:
    return get_commodity_position_rows(as_of=as_of, account=account)


def get_commodity_position_for_party(
    party: Party,
    *,
    as_of: date | None = None,
) -> list[CommodityPositionRow]:
    return get_commodity_position_rows(as_of=as_of, party=party)


def _account_matches(
    row_account: CommodityAccount,
    *,
    account: CommodityAccount | None,
    party: Party | None,
    location_label: str | None,
) -> bool:
    if account is not None and row_account.pk != account.pk:
        return False
    if party is not None and row_account.party_id != party.pk:
        return False
    if location_label is not None and row_account.location_label != location_label:
        return False
    return True


def _apply_movement(
    *,
    positions: dict[tuple[int, str, str], dict],
    movement: CommodityMovement,
    account: CommodityAccount,
    sign: Decimal,
) -> None:
    key = (account.pk, movement.fixed_status, movement.uom)
    if key not in positions:
        positions[key] = {
            "commodity": movement.commodity,
            "account": account,
            "fixed_status": movement.fixed_status,
            "uom": movement.uom,
            "gross_weight": Decimal("0.000"),
            "fine_weight": Decimal("0.000"),
        }
    positions[key]["gross_weight"] += movement.gross_weight * sign
    positions[key]["fine_weight"] += movement.fine_weight * sign


def _build_row(position: dict) -> CommodityPositionRow:
    commodity = position["commodity"]
    account = position["account"]
    party = account.party
    return CommodityPositionRow(
        commodity_id=commodity.pk,
        commodity_code=commodity.code,
        commodity_name=commodity.name,
        account_id=account.pk,
        account_code=account.code,
        account_name=account.name,
        account_purpose=account.purpose,
        party_id=party.pk if party else None,
        party_name=party.display_name if party else "",
        location_label=account.location_label,
        fixed_status=position["fixed_status"],
        uom=position["uom"],
        gross_weight=position["gross_weight"],
        fine_weight=position["fine_weight"],
    )
