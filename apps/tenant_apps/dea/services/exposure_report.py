from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from apps.tenant_apps.dea.models import Commodity, ExposureLine
from apps.tenant_apps.dea.services.valuation import (
    ValuedExposureLine,
    value_exposure_lines,
)
from apps.tenant_apps.party.models import Party


ACTIVE_EXPOSURE_STATUSES = (
    ExposureLine.Status.OPEN,
    ExposureLine.Status.PARTIALLY_FIXED,
)


@dataclass(frozen=True)
class ExposureReportRow:
    exposure_id: int
    exposure_no: str
    party_id: int
    party_name: str
    commodity_id: int
    commodity_code: str
    commodity_name: str
    side: str
    status: str
    fixed_status: str
    original_fine_weight: Decimal
    open_fine_weight: Decimal
    uom: str
    rate_basis: str
    valuation_currency: str
    last_valuation_rate: Decimal | None
    last_valuation_amount: Decimal | None
    valuation_status: str
    valuation_rate: Decimal | None
    valuation_amount: Decimal | None
    rate_source_name: str


@dataclass(frozen=True)
class ExposureReportTotal:
    commodity_id: int
    commodity_code: str
    commodity_name: str
    side: str
    status: str
    uom: str
    original_fine_weight: Decimal
    open_fine_weight: Decimal
    valuation_currency: str
    valuation_amount: Decimal | None


@dataclass(frozen=True)
class ExposureReport:
    as_of: date | None
    party_id: int | None
    commodity_id: int | None
    side: str
    statuses: tuple[str, ...]
    include_valuation: bool
    valuation_currency: str
    valuation_purity: str
    rows: tuple[ExposureReportRow, ...]
    totals: tuple[ExposureReportTotal, ...]


def build_exposure_report(
    *,
    as_of: date | None = None,
    party: Party | None = None,
    commodity: Commodity | None = None,
    side: str | None = None,
    statuses: tuple[str, ...] | list[str] | None = None,
    include_valuation: bool = False,
    valuation_currency: str = "INR",
    valuation_purity: str = "24k",
) -> ExposureReport:
    selected_statuses = tuple(statuses or ACTIVE_EXPOSURE_STATUSES)
    exposures = ExposureLine.objects.select_related("party", "commodity").filter(
        status__in=selected_statuses,
    )
    if as_of is not None:
        exposures = exposures.filter(created_at__date__lte=as_of)
    if party is not None:
        exposures = exposures.filter(party=party)
    if commodity is not None:
        exposures = exposures.filter(commodity=commodity)
    if side:
        exposures = exposures.filter(side=side)

    exposure_list = list(
        exposures.order_by(
            "commodity__code",
            "party__display_name",
            "side",
            "exposure_no",
        )
    )
    valued_by_id: dict[int, ValuedExposureLine] = {}
    if include_valuation:
        valued_by_id = {
            valued.exposure.pk: valued
            for valued in value_exposure_lines(
                exposure_list,
                as_of=as_of,
                currency=valuation_currency,
                purity=valuation_purity,
            )
        }

    rows = tuple(_build_row(exposure, valued_by_id.get(exposure.pk)) for exposure in exposure_list)
    return ExposureReport(
        as_of=as_of,
        party_id=party.pk if party else None,
        commodity_id=commodity.pk if commodity else None,
        side=side or "",
        statuses=selected_statuses,
        include_valuation=include_valuation,
        valuation_currency=(valuation_currency or "").strip().upper(),
        valuation_purity=valuation_purity,
        rows=rows,
        totals=tuple(_build_totals(rows)),
    )


def _build_row(
    exposure: ExposureLine,
    valued: ValuedExposureLine | None,
) -> ExposureReportRow:
    return ExposureReportRow(
        exposure_id=exposure.pk,
        exposure_no=exposure.exposure_no,
        party_id=exposure.party_id,
        party_name=exposure.party.display_name,
        commodity_id=exposure.commodity_id,
        commodity_code=exposure.commodity.code,
        commodity_name=exposure.commodity.name,
        side=exposure.side,
        status=exposure.status,
        fixed_status=exposure.fixed_status,
        original_fine_weight=exposure.original_fine_weight,
        open_fine_weight=exposure.open_fine_weight,
        uom=exposure.uom,
        rate_basis=exposure.rate_basis,
        valuation_currency=exposure.valuation_currency,
        last_valuation_rate=exposure.last_valuation_rate,
        last_valuation_amount=exposure.last_valuation_amount,
        valuation_status=valued.valuation_status if valued else "",
        valuation_rate=valued.valuation_rate if valued else None,
        valuation_amount=valued.valuation_amount if valued else None,
        rate_source_name=valued.rate_source_name if valued else "",
    )


def _build_totals(rows: tuple[ExposureReportRow, ...]) -> list[ExposureReportTotal]:
    totals: dict[tuple[int, str, str, str], dict] = {}
    for row in rows:
        key = (row.commodity_id, row.side, row.status, row.uom)
        if key not in totals:
            totals[key] = {
                "commodity_id": row.commodity_id,
                "commodity_code": row.commodity_code,
                "commodity_name": row.commodity_name,
                "side": row.side,
                "status": row.status,
                "uom": row.uom,
                "original_fine_weight": Decimal("0.000"),
                "open_fine_weight": Decimal("0.000"),
                "valuation_currency": row.valuation_currency,
                "valuation_amount": Decimal("0.00") if row.valuation_amount is not None else None,
            }
        totals[key]["original_fine_weight"] += row.original_fine_weight
        totals[key]["open_fine_weight"] += row.open_fine_weight
        if row.valuation_amount is not None:
            if totals[key]["valuation_amount"] is None:
                totals[key]["valuation_amount"] = Decimal("0.00")
            totals[key]["valuation_amount"] += row.valuation_amount

    return [
        ExposureReportTotal(**total)
        for total in sorted(
            totals.values(),
            key=lambda total: (
                total["commodity_code"],
                total["side"],
                total["status"],
                total["uom"],
            ),
        )
    ]

