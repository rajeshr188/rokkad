"""Explicit non-cash settlement adjustment boundaries for Girvi loans."""

from dataclasses import dataclass, field as dc_field
from decimal import Decimal, InvalidOperation


class SettlementAdjustmentType:
    WRITE_OFF = "WRITE_OFF"
    INTEREST_WAIVER = "INTEREST_WAIVER"
    SETTLEMENT_DISCOUNT = "SETTLEMENT_DISCOUNT"
    AUCTION_SHORTFALL_WRITE_OFF = "AUCTION_SHORTFALL_WRITE_OFF"
    ADMIN_CORRECTION = "ADMIN_CORRECTION"

    CHOICES = {
        WRITE_OFF: "Write-off",
        INTEREST_WAIVER: "Interest waiver",
        SETTLEMENT_DISCOUNT: "Settlement discount",
        AUCTION_SHORTFALL_WRITE_OFF: "Auction shortfall write-off",
        ADMIN_CORRECTION: "Admin correction",
    }


@dataclass
class SettlementAdjustmentCommand:
    loan: object
    adjustment_type: str
    created_by: object
    reason: str
    principal_amount: object = Decimal("0.00")
    interest_amount: object = Decimal("0.00")


@dataclass
class SettlementAdjustmentResult:
    success: bool = False
    message: str = ""
    errors: list[str] = dc_field(default_factory=list)
    adjustment_type: str = ""


class SettlementAdjustmentService:
    """Fail-closed boundary for closing loans without cash receipts.

    Non-cash closure must not be hidden behind generic lifecycle transitions.
    Each adjustment type needs a source document, approval/audit trail, and DEA
    posting before it can reduce dues or close a loan.
    """

    @classmethod
    def execute(cls, command: SettlementAdjustmentCommand) -> SettlementAdjustmentResult:
        errors = cls._validation_errors(command)
        if errors:
            return SettlementAdjustmentResult(
                success=False,
                message="; ".join(errors),
                errors=errors,
                adjustment_type=command.adjustment_type,
            )

        label = SettlementAdjustmentType.CHOICES[command.adjustment_type]
        message = (
            f"{label} requires an explicit settlement adjustment document and "
            "DEA posting before this loan can be closed without cash."
        )
        return SettlementAdjustmentResult(
            success=False,
            message=message,
            errors=[message],
            adjustment_type=command.adjustment_type,
        )

    @staticmethod
    def _validation_errors(command: SettlementAdjustmentCommand):
        errors = []
        if command.adjustment_type not in SettlementAdjustmentType.CHOICES:
            errors.append("Unsupported settlement adjustment type.")
        if not str(command.reason or "").strip():
            errors.append("Adjustment reason is required.")

        for field_name in ("principal_amount", "interest_amount"):
            value = getattr(command, field_name)
            try:
                if Decimal(str(value or "0.00")) < 0:
                    errors.append(f"{field_name} cannot be negative.")
            except (InvalidOperation, TypeError, ValueError):
                errors.append(f"{field_name} must be a valid amount.")

        return errors
