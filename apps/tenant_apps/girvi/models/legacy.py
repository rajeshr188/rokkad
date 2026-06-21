"""
Explicit compatibility imports for deprecated Girvi models.

Runtime code should use GivenLoan/TakenLoan and PaymentVoucher-backed services.
Import from this module only for historical data access, migration helpers, and
clearly labelled legacy import/export surfaces.
"""

from .loan import Loan, LoanPayment

__all__ = ["Loan", "LoanPayment"]
