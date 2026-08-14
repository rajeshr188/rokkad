from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from apps.tenant_apps.dea.models import Commodity, CommodityAccount
from apps.tenant_apps.dea.selectors.commodity import (
    CommodityPositionRow,
    get_commodity_position_rows,
)
from apps.tenant_apps.party.models import Party


@dataclass(frozen=True)
class MetalBalanceTotal:
    commodity_id: int
    commodity_code: str
    commodity_name: str
    uom: str
    gross_weight: Decimal
    fine_weight: Decimal


@dataclass(frozen=True)
class MetalBalanceStatusTotal:
    commodity_id: int
    commodity_code: str
    commodity_name: str
    fixed_status: str
    uom: str
    gross_weight: Decimal
    fine_weight: Decimal


@dataclass(frozen=True)
class MetalBalanceReport:
    as_of: date | None
    commodity_id: int | None
    account_id: int | None
    party_id: int | None
    location_label: str
    fixed_status: str
    include_adjustment_accounts: bool
    rows: tuple[CommodityPositionRow, ...]
    totals_by_commodity: tuple[MetalBalanceTotal, ...]
    totals_by_status: tuple[MetalBalanceStatusTotal, ...]


def build_metal_balance_report(
    *,
    as_of: date | None = None,
    commodity: Commodity | None = None,
    account: CommodityAccount | None = None,
    party: Party | None = None,
    location_label: str | None = None,
    fixed_status: str | None = None,
    include_adjustment_accounts: bool = False,
) -> MetalBalanceReport:
    rows = get_commodity_position_rows(
        as_of=as_of,
        commodity=commodity,
        account=account,
        party=party,
        location_label=location_label,
    )
    if not include_adjustment_accounts and account is None:
        rows = [
            row
            for row in rows
            if row.account_purpose
            not in {
                CommodityAccount.Purpose.ADJUSTMENT,
                CommodityAccount.Purpose.LOSS_GAIN,
            }
        ]
    if fixed_status:
        rows = [row for row in rows if row.fixed_status == fixed_status]

    return MetalBalanceReport(
        as_of=as_of,
        commodity_id=commodity.pk if commodity else None,
        account_id=account.pk if account else None,
        party_id=party.pk if party else None,
        location_label=location_label or "",
        fixed_status=fixed_status or "",
        include_adjustment_accounts=include_adjustment_accounts,
        rows=tuple(rows),
        totals_by_commodity=tuple(_build_commodity_totals(rows)),
        totals_by_status=tuple(_build_status_totals(rows)),
    )


def _build_commodity_totals(
    rows: list[CommodityPositionRow],
) -> list[MetalBalanceTotal]:
    totals: dict[tuple[int, str], dict] = {}
    for row in rows:
        key = (row.commodity_id, row.uom)
        if key not in totals:
            totals[key] = {
                "commodity_id": row.commodity_id,
                "commodity_code": row.commodity_code,
                "commodity_name": row.commodity_name,
                "uom": row.uom,
                "gross_weight": Decimal("0.000"),
                "fine_weight": Decimal("0.000"),
            }
        totals[key]["gross_weight"] += row.gross_weight
        totals[key]["fine_weight"] += row.fine_weight

    return [
        MetalBalanceTotal(**total)
        for total in sorted(
            totals.values(),
            key=lambda total: (total["commodity_code"], total["uom"]),
        )
    ]


def _build_status_totals(
    rows: list[CommodityPositionRow],
) -> list[MetalBalanceStatusTotal]:
    totals: dict[tuple[int, str, str], dict] = {}
    for row in rows:
        key = (row.commodity_id, row.fixed_status, row.uom)
        if key not in totals:
            totals[key] = {
                "commodity_id": row.commodity_id,
                "commodity_code": row.commodity_code,
                "commodity_name": row.commodity_name,
                "fixed_status": row.fixed_status,
                "uom": row.uom,
                "gross_weight": Decimal("0.000"),
                "fine_weight": Decimal("0.000"),
            }
        totals[key]["gross_weight"] += row.gross_weight
        totals[key]["fine_weight"] += row.fine_weight

    return [
        MetalBalanceStatusTotal(**total)
        for total in sorted(
            totals.values(),
            key=lambda total: (
                total["commodity_code"],
                total["fixed_status"],
                total["uom"],
            ),
        )
    ]
