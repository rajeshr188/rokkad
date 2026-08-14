from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from apps.tenant_apps.dea.models import Commodity, CommodityAccount
from apps.tenant_apps.dea.services.exposure_report import (
    ACTIVE_EXPOSURE_STATUSES,
    ExposureReportRow,
    build_exposure_report,
)
from apps.tenant_apps.dea.services.metal_balance_report import build_metal_balance_report
from apps.tenant_apps.dea.services.valuation import (
    ValuedCommodityPositionRow,
    value_position_rows,
)
from apps.tenant_apps.party.models import Party


@dataclass(frozen=True)
class ValuationReportStatusTotal:
    valuation_status: str
    valuation_currency: str
    row_count: int
    valuation_amount: Decimal | None


@dataclass(frozen=True)
class ValuationReport:
    as_of: date | None
    commodity_id: int | None
    party_id: int | None
    location_label: str
    exposure_side: str
    exposure_statuses: tuple[str, ...]
    valuation_currency: str
    valuation_purity: str
    include_positions: bool
    include_exposures: bool
    position_rows: tuple[ValuedCommodityPositionRow, ...]
    exposure_rows: tuple[ExposureReportRow, ...]
    totals_by_status: tuple[ValuationReportStatusTotal, ...]


def build_valuation_report(
    *,
    as_of: date | None = None,
    commodity: Commodity | None = None,
    account: CommodityAccount | None = None,
    party: Party | None = None,
    location_label: str | None = None,
    exposure_side: str | None = None,
    exposure_statuses: tuple[str, ...] | list[str] | None = None,
    valuation_currency: str = "INR",
    valuation_purity: str = "24k",
    include_positions: bool = True,
    include_exposures: bool = True,
) -> ValuationReport:
    normalized_currency = (valuation_currency or "").strip().upper()
    selected_exposure_statuses = tuple(exposure_statuses or ACTIVE_EXPOSURE_STATUSES)

    position_rows: tuple[ValuedCommodityPositionRow, ...] = ()
    if include_positions:
        metal_report = build_metal_balance_report(
            as_of=as_of,
            commodity=commodity,
            account=account,
            party=party,
            location_label=location_label,
        )
        position_rows = tuple(
            value_position_rows(
                list(metal_report.rows),
                as_of=as_of,
                currency=normalized_currency,
                purity=valuation_purity,
            )
        )

    exposure_rows: tuple[ExposureReportRow, ...] = ()
    if include_exposures:
        exposure_report = build_exposure_report(
            as_of=as_of,
            party=party,
            commodity=commodity,
            side=exposure_side,
            statuses=selected_exposure_statuses,
            include_valuation=True,
            valuation_currency=normalized_currency,
            valuation_purity=valuation_purity,
        )
        exposure_rows = exposure_report.rows

    return ValuationReport(
        as_of=as_of,
        commodity_id=commodity.pk if commodity else None,
        party_id=party.pk if party else None,
        location_label=location_label or "",
        exposure_side=exposure_side or "",
        exposure_statuses=selected_exposure_statuses,
        valuation_currency=normalized_currency,
        valuation_purity=valuation_purity,
        include_positions=include_positions,
        include_exposures=include_exposures,
        position_rows=position_rows,
        exposure_rows=exposure_rows,
        totals_by_status=tuple(_build_totals_by_status(position_rows, exposure_rows)),
    )


def _build_totals_by_status(
    position_rows: tuple[ValuedCommodityPositionRow, ...],
    exposure_rows: tuple[ExposureReportRow, ...],
) -> list[ValuationReportStatusTotal]:
    totals: dict[tuple[str, str], dict] = {}

    for row in position_rows:
        _add_status_total(
            totals,
            status=row.valuation_status,
            currency=row.valuation_currency,
            amount=row.valuation_amount,
        )

    for row in exposure_rows:
        _add_status_total(
            totals,
            status=row.valuation_status,
            currency=row.valuation_currency,
            amount=row.valuation_amount,
        )

    return [
        ValuationReportStatusTotal(**total)
        for total in sorted(
            totals.values(),
            key=lambda total: (total["valuation_status"], total["valuation_currency"]),
        )
    ]


def _add_status_total(
    totals: dict[tuple[str, str], dict],
    *,
    status: str,
    currency: str,
    amount: Decimal | None,
) -> None:
    key = (status, currency)
    if key not in totals:
        totals[key] = {
            "valuation_status": status,
            "valuation_currency": currency,
            "row_count": 0,
            "valuation_amount": Decimal("0.00") if amount is not None else None,
        }

    totals[key]["row_count"] += 1
    if amount is not None:
        if totals[key]["valuation_amount"] is None:
            totals[key]["valuation_amount"] = Decimal("0.00")
        totals[key]["valuation_amount"] += amount
