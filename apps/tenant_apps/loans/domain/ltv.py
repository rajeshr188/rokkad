from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class LtvAssessment:
    exposure: Decimal
    collateral_value: Decimal | None
    allowed_ltv_ratio: Decimal
    ltv_ratio: Decimal | None
    headroom: Decimal | None
    full_shortfall: Decimal | None
    status: str
    blockers: tuple[str, ...]


def calculate_ltv(*, exposure, collateral_value, allowed_ltv_ratio, blockers=()):
    exposure = Decimal(str(exposure))
    allowed = Decimal(str(allowed_ltv_ratio))
    value = Decimal(str(collateral_value)) if collateral_value is not None else None
    blockers = tuple(blockers)
    if blockers or value is None or value <= 0:
        return LtvAssessment(exposure, value, allowed, None, None, None, "UNKNOWN", blockers or ("COLLATERAL_VALUE_UNAVAILABLE",))
    ratio = exposure / value
    headroom = value * allowed - exposure
    shortfall = max(exposure - value, Decimal("0"))
    status = "BREACH" if ratio > allowed else "WITHIN_LIMIT"
    return LtvAssessment(exposure, value, allowed, ratio, headroom, shortfall, status, ())
