"""Immutable, database-free loan policy contracts."""

from dataclasses import dataclass, fields
from decimal import Decimal

from .vocabulary import StringEnum


class InterestMethod(StringEnum):
    SIMPLE = "SIMPLE"
    COMPOUND = "COMPOUND"


class PartialMonthMethod(StringEnum):
    FULL_MONTH = "FULL_MONTH"
    SLAB = "SLAB"


class AccountingRecognition(StringEnum):
    CASH = "CASH"
    ACCRUAL = "ACCRUAL"


class ValuationMethod(StringEnum):
    CALCULATED_METAL_VALUE = "CALCULATED_METAL_VALUE"
    LATEST_APPRAISAL = "LATEST_APPRAISAL"
    LOWER_OF_CALCULATED_AND_APPRAISAL = "LOWER_OF_CALCULATED_AND_APPRAISAL"


class RoundingMethod(StringEnum):
    PER_ACCRUAL_PERIOD = "PER_ACCRUAL_PERIOD"


def _validate_policy_values(policy):
    if not 1 <= policy.partial_month_cutoff_days <= 30:
        raise ValueError("Partial-month cutoff days must be between 1 and 30.")
    if not Decimal("0") < policy.partial_month_lower_fraction <= Decimal("1"):
        raise ValueError("Partial-month lower fraction must be above 0 and at most 1.")
    if policy.capitalization_interval_periods < 1:
        raise ValueError("Capitalization interval must be at least one period.")
    if not Decimal("0") < policy.maximum_ltv_ratio <= Decimal("1"):
        raise ValueError("Maximum LTV ratio must be above 0 and at most 1.")
    if policy.currency_quantum <= Decimal("0"):
        raise ValueError("Currency quantum must be positive.")


@dataclass(frozen=True)
class WorkspacePolicyDefaults:
    interest_method: InterestMethod = InterestMethod.SIMPLE
    partial_month_method: PartialMonthMethod = PartialMonthMethod.FULL_MONTH
    partial_month_cutoff_days: int = 15
    partial_month_lower_fraction: Decimal = Decimal("0.5")
    capitalization_interval_periods: int = 12
    accounting_recognition: AccountingRecognition = AccountingRecognition.CASH
    valuation_method: ValuationMethod = ValuationMethod.CALCULATED_METAL_VALUE
    maximum_ltv_ratio: Decimal = Decimal("0.80")
    rounding_method: RoundingMethod = RoundingMethod.PER_ACCRUAL_PERIOD
    currency_quantum: Decimal = Decimal("0.01")

    def __post_init__(self):
        _validate_policy_values(self)


@dataclass(frozen=True)
class LicensePolicyOverrides:
    interest_method: InterestMethod | None = None
    partial_month_method: PartialMonthMethod | None = None
    partial_month_cutoff_days: int | None = None
    partial_month_lower_fraction: Decimal | None = None
    capitalization_interval_periods: int | None = None
    accounting_recognition: AccountingRecognition | None = None
    valuation_method: ValuationMethod | None = None
    maximum_ltv_ratio: Decimal | None = None
    rounding_method: RoundingMethod | None = None
    currency_quantum: Decimal | None = None

    def __post_init__(self):
        defaults = WorkspacePolicyDefaults()
        candidate = ResolvedLoanPolicy(
            **{
                field.name: (
                    getattr(self, field.name)
                    if getattr(self, field.name) is not None
                    else getattr(defaults, field.name)
                )
                for field in fields(WorkspacePolicyDefaults)
            }
        )
        _validate_policy_values(candidate)


@dataclass(frozen=True)
class ResolvedLoanPolicy:
    interest_method: InterestMethod
    partial_month_method: PartialMonthMethod
    partial_month_cutoff_days: int
    partial_month_lower_fraction: Decimal
    capitalization_interval_periods: int
    accounting_recognition: AccountingRecognition
    valuation_method: ValuationMethod
    maximum_ltv_ratio: Decimal
    rounding_method: RoundingMethod
    currency_quantum: Decimal

    def __post_init__(self):
        _validate_policy_values(self)

    def to_disbursal_snapshot(self):
        return DisbursalPolicySnapshot(**self.__dict__)


@dataclass(frozen=True)
class DisbursalPolicySnapshot(ResolvedLoanPolicy):
    policy_version: int = 1

    def __post_init__(self):
        super().__post_init__()
        if self.policy_version < 1:
            raise ValueError("Policy snapshot version must be positive.")

    def to_dict(self):
        return {
            "policy_version": self.policy_version,
            "interest_method": self.interest_method.value,
            "partial_month_method": self.partial_month_method.value,
            "partial_month_cutoff_days": self.partial_month_cutoff_days,
            "partial_month_lower_fraction": str(self.partial_month_lower_fraction),
            "capitalization_interval_periods": self.capitalization_interval_periods,
            "accounting_recognition": self.accounting_recognition.value,
            "valuation_method": self.valuation_method.value,
            "maximum_ltv_ratio": str(self.maximum_ltv_ratio),
            "rounding_method": self.rounding_method.value,
            "currency_quantum": str(self.currency_quantum),
        }

    @classmethod
    def from_dict(cls, payload):
        return cls(
            policy_version=int(payload["policy_version"]),
            interest_method=InterestMethod(payload["interest_method"]),
            partial_month_method=PartialMonthMethod(payload["partial_month_method"]),
            partial_month_cutoff_days=int(payload["partial_month_cutoff_days"]),
            partial_month_lower_fraction=Decimal(
                payload["partial_month_lower_fraction"]
            ),
            capitalization_interval_periods=int(
                payload["capitalization_interval_periods"]
            ),
            accounting_recognition=AccountingRecognition(
                payload["accounting_recognition"]
            ),
            valuation_method=ValuationMethod(payload["valuation_method"]),
            maximum_ltv_ratio=Decimal(payload["maximum_ltv_ratio"]),
            rounding_method=RoundingMethod(payload["rounding_method"]),
            currency_quantum=Decimal(payload["currency_quantum"]),
        )


def resolve_policy(workspace_defaults=None, license_overrides=None):
    """Resolve workspace defaults with optional license-level overrides."""

    workspace_defaults = workspace_defaults or WorkspacePolicyDefaults()
    license_overrides = license_overrides or LicensePolicyOverrides()
    return ResolvedLoanPolicy(
        **{
            field.name: (
                getattr(license_overrides, field.name)
                if getattr(license_overrides, field.name) is not None
                else getattr(workspace_defaults, field.name)
            )
            for field in fields(WorkspacePolicyDefaults)
        }
    )
