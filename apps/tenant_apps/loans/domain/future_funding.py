"""Post-MVP FundingLoan vocabulary.

This module is descriptive compatibility vocabulary only. It must not be used
to expose FundingLoan persistence, services, routes, or UI before the complete
post-MVP vertical slice is approved.
"""

from enum import Enum


FUNDING_LOAN_RUNTIME_SUPPORTED = False


class FundingLoanState(str, Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    SETTLEMENT_PENDING = "SETTLEMENT_PENDING"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"

    def __str__(self):
        return self.value
