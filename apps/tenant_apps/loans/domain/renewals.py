"""PawnLoan renewal modes."""

from enum import Enum


class PawnLoanRenewalMode(str, Enum):
    PAY_AND_RENEW = "PAY_AND_RENEW"
    TOP_UP_RENEW = "TOP_UP_RENEW"


__all__ = ["PawnLoanRenewalMode"]
