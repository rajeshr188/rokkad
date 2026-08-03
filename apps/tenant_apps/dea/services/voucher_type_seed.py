"""Idempotent DEA voucher type seed helpers."""

from apps.tenant_apps.dea.models import VoucherType


SEEDED_VOUCHER_TYPES = {
    "PAWN_LOAN_DISBURSAL": "PawnLoan principal paid to borrower",
    "PAWN_LOAN_REPAYMENT": "PawnLoan repayment received from borrower",
    "PAWN_LOAN_RELEASE": "PawnLoan final settlement and collateral release",
    "PAWN_LOAN_INTEREST_ACCRUAL": "PawnLoan interest receivable recognized",
    "PAWN_LOAN_INTEREST_CAPITALIZATION": "PawnLoan interest capitalized into principal",
    "GIVENLOAN_RECEIPT": "GivenLoan repayment receipt (cash received from borrower)",
    "GIVENLOAN_PAYMENT": "GivenLoan disbursal payment (cash paid to borrower)",
    "TAKENLOAN_RECEIPT": "TakenLoan disbursal receipt (cash received from lender)",
    "TAKENLOAN_PAYMENT": "TakenLoan repayment payment (cash paid to lender)",
    "GIVENLOAN_RELEASE": "GivenLoan release write-off / closure entry",
    "GIVENLOAN_AUCTION": "GivenLoan auction recovery receipt",
    "GIVENLOAN_SOLD": "GivenLoan collateral sale recovery receipt",
    "EXPENSE_EMP_CLAIM": "Expense voucher for employee claims (reimbursements)",
    "EXPENSE_VENDOR_BILL": "Expense voucher for vendor bills (accounts payable)",
    "EXPENSE_DIRECT_PAYMENT": "Expense voucher for direct payments/cash expenses",
    "EXPENSE_REIMBURSEMENT": "Expense voucher for reimbursement requests",
    "EXPENSE_OTHER": "Expense voucher for other miscellaneous expenses",
}


def ensure_seeded_voucher_type(name: str) -> VoucherType:
    """Return a known seeded VoucherType, creating it when an older tenant lacks it."""
    if name not in SEEDED_VOUCHER_TYPES:
        raise VoucherType.DoesNotExist

    voucher_type, _created = VoucherType.objects.update_or_create(
        name=name,
        defaults={"description": SEEDED_VOUCHER_TYPES[name]},
    )
    return voucher_type


def seed_voucher_types():
    """Seed all canonical DEA voucher types for the current tenant schema."""
    for name in SEEDED_VOUCHER_TYPES:
        ensure_seeded_voucher_type(name)
