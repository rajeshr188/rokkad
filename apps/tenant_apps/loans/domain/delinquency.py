from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal


@dataclass(frozen=True)
class UnpaidObligation:
    due_date: date
    principal: Decimal
    interest: Decimal

    @property
    def outstanding(self):
        return self.principal + self.interest


@dataclass(frozen=True)
class DelinquencyResult:
    due: Decimal
    overdue: Decimal
    oldest_unpaid_due_date: date | None
    days_past_due: int
    dpd_bucket: str
    operational_grace_days: int
    escalation_eligible: bool


def calculate_delinquency(obligations, *, as_of_date, operational_grace_days=3):
    """Fold contractual obligations without moving their due dates for grace."""
    unpaid = tuple(row for row in obligations if row.outstanding > 0)
    due = sum((row.outstanding for row in unpaid if row.due_date <= as_of_date), Decimal("0"))
    overdue_rows = tuple(row for row in unpaid if row.due_date < as_of_date)
    overdue = sum((row.outstanding for row in overdue_rows), Decimal("0"))
    oldest = min((row.due_date for row in overdue_rows), default=None)
    dpd = (as_of_date - oldest).days if oldest else 0
    return DelinquencyResult(
        due=due,
        overdue=overdue,
        oldest_unpaid_due_date=oldest,
        days_past_due=dpd,
        dpd_bucket=_dpd_bucket(dpd),
        operational_grace_days=operational_grace_days,
        escalation_eligible=bool(oldest and as_of_date > oldest + timedelta(days=operational_grace_days)),
    )


def _dpd_bucket(dpd):
    if dpd <= 0:
        return "CURRENT"
    if dpd < 30:
        return "DPD_1_29"
    if dpd < 60:
        return "DPD_30_59"
    if dpd < 90:
        return "DPD_60_89"
    return "DPD_90_PLUS"
