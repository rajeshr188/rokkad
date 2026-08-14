"""Database-free PawnLoan auction/recovery vocabulary."""

from .vocabulary import StringEnum


class PawnLoanAuctionState(StringEnum):
    INITIATED = "INITIATED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


__all__ = ["PawnLoanAuctionState"]
