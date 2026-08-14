from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from apps.tenant_apps.dea.models import ExposureLine
from apps.tenant_apps.dea.selectors.commodity import CommodityPositionRow
from apps.tenant_apps.rates.facade import (
    RATE_FOUND,
    get_latest_commodity_valuation_rate,
)


VALUATION_VALUED = "VALUED"
VALUATION_MISSING_RATE = "MISSING_RATE"
VALUATION_UNSUPPORTED_COMMODITY = "UNSUPPORTED_COMMODITY"
VALUATION_UNSUPPORTED_CURRENCY = "UNSUPPORTED_CURRENCY"
VALUATION_UNSUPPORTED_PURITY = "UNSUPPORTED_PURITY"


@dataclass(frozen=True)
class ValuedCommodityPositionRow:
    position: CommodityPositionRow
    valuation_status: str
    valuation_currency: str
    valuation_rate: Decimal | None
    valuation_amount: Decimal | None
    rate_timestamp: object | None = None
    rate_source_name: str = ""


@dataclass(frozen=True)
class ValuedExposureLine:
    exposure: ExposureLine
    valuation_status: str
    valuation_currency: str
    valuation_rate: Decimal | None
    valuation_amount: Decimal | None
    rate_timestamp: object | None = None
    rate_source_name: str = ""


def value_position_rows(
    position_rows: list[CommodityPositionRow],
    *,
    as_of: date | datetime | None = None,
    currency: str = "INR",
    purity: str = "24k",
) -> list[ValuedCommodityPositionRow]:
    return [
        _value_position_row(
            position,
            as_of=as_of,
            currency=currency,
            purity=purity,
        )
        for position in position_rows
    ]


def value_exposure_lines(
    exposures,
    *,
    as_of: date | datetime | None = None,
    currency: str = "INR",
    purity: str = "24k",
) -> list[ValuedExposureLine]:
    return [
        _value_exposure(
            exposure,
            as_of=as_of,
            currency=currency,
            purity=purity,
        )
        for exposure in exposures
    ]


def _value_position_row(
    position: CommodityPositionRow,
    *,
    as_of: date | datetime | None,
    currency: str,
    purity: str,
) -> ValuedCommodityPositionRow:
    lookup = get_latest_commodity_valuation_rate(
        commodity_code=position.commodity_code,
        as_of=as_of,
        currency=currency,
        purity=purity,
    )
    if lookup.status != RATE_FOUND:
        return ValuedCommodityPositionRow(
            position=position,
            valuation_status=lookup.status,
            valuation_currency=currency,
            valuation_rate=None,
            valuation_amount=None,
        )

    rate = lookup.rate
    valuation_rate = rate.buying_rate
    return ValuedCommodityPositionRow(
        position=position,
        valuation_status=VALUATION_VALUED,
        valuation_currency=rate.currency,
        valuation_rate=valuation_rate,
        valuation_amount=_money_amount(position.fine_weight * valuation_rate),
        rate_timestamp=rate.timestamp,
        rate_source_name=str(rate.rate_source),
    )


def _value_exposure(
    exposure: ExposureLine,
    *,
    as_of: date | datetime | None,
    currency: str,
    purity: str,
) -> ValuedExposureLine:
    lookup = get_latest_commodity_valuation_rate(
        commodity_code=exposure.commodity.code,
        as_of=as_of,
        currency=currency,
        purity=purity,
    )
    if lookup.status != RATE_FOUND:
        return ValuedExposureLine(
            exposure=exposure,
            valuation_status=lookup.status,
            valuation_currency=currency,
            valuation_rate=None,
            valuation_amount=None,
        )

    rate = lookup.rate
    valuation_rate = (
        rate.selling_rate
        if exposure.side == ExposureLine.Side.SALE
        else rate.buying_rate
    )
    return ValuedExposureLine(
        exposure=exposure,
        valuation_status=VALUATION_VALUED,
        valuation_currency=rate.currency,
        valuation_rate=valuation_rate,
        valuation_amount=_money_amount(exposure.open_fine_weight * valuation_rate),
        rate_timestamp=rate.timestamp,
        rate_source_name=str(rate.rate_source),
    )


def _money_amount(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal("0.01"))
