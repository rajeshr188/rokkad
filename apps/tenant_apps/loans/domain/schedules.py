from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum


class RepaymentScheduleContract(StrEnum):
    V1 = "REPAYMENT-SCHEDULE-V1"


class ObligationComponent(StrEnum):
    PRINCIPAL = "PRINCIPAL"
    INTEREST = "INTEREST"


@dataclass(frozen=True)
class ScheduleRateTranche:
    principal: Decimal
    monthly_interest_rate: Decimal


@dataclass(frozen=True)
class RepaymentScheduleInput:
    repayment_structure: str
    amortisation_method: str
    disbursed_on: date
    principal: Decimal
    monthly_interest_rate: Decimal
    tenure_months: int
    currency_quantum: Decimal = Decimal("0.01")
    rate_tranches: tuple[ScheduleRateTranche, ...] = ()
    contract_version: str = RepaymentScheduleContract.V1.value


@dataclass(frozen=True)
class ScheduledRepayment:
    sequence: int
    due_date: date
    principal_due: Decimal
    interest_due: Decimal
    opening_principal: Decimal
    closing_principal: Decimal

    @property
    def total_due(self):
        return self.principal_due + self.interest_due


@dataclass(frozen=True)
class RepaymentSchedule:
    contract_version: str
    disbursed_on: date
    maturity_date: date
    principal: Decimal
    contractual_interest: Decimal
    repayments: tuple[ScheduledRepayment, ...]
    rounding_adjustment: Decimal
    fingerprint: str

    @property
    def total_repayable(self):
        return self.principal + self.contractual_interest
