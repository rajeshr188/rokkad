"""Backward-compatible facade for Girvi payment/accounting helpers.

Prefer importing from `apps.tenant_apps.girvi.service_modules.payment` for new code.
This module intentionally preserves the old patch/import surface for existing
callers and tests.
"""

from apps.tenant_apps.girvi.service_modules import payment as _payment

ContentType = getattr(_payment, "ContentType", None)
PaymentVoucher = getattr(_payment, "PaymentVoucher", None)
Voucher = getattr(_payment, "Voucher", None)
VoucherStatus = getattr(_payment, "VoucherStatus", None)
DjangoPostingEngine = getattr(_payment, "DjangoPostingEngine", None)
create_and_post_voucher_for_doc = _payment.create_and_post_voucher_for_doc
GivenLoan = _payment.GivenLoan
TakenLoan = _payment.TakenLoan


def _sync_patchable_globals():
    _payment.ContentType = ContentType
    _payment.PaymentVoucher = PaymentVoucher
    _payment.Voucher = Voucher
    _payment.VoucherStatus = VoucherStatus
    _payment.DjangoPostingEngine = DjangoPostingEngine
    _payment.create_and_post_voucher_for_doc = create_and_post_voucher_for_doc
    _payment.GivenLoan = GivenLoan
    _payment.TakenLoan = TakenLoan


def record_loan_disbursal(loan, user):
    _sync_patchable_globals()
    return _payment.record_loan_disbursal(loan, user)


def record_loan_release(release, created_by):
    _sync_patchable_globals()
    return _payment.record_loan_release(release, created_by)


def reverse_loan_disbursal(loan, user):
    _sync_patchable_globals()
    return _payment.reverse_loan_disbursal(loan, user)


def reverse_loan_release(loan, user):
    _sync_patchable_globals()
    return _payment.reverse_loan_release(loan, user)


__all__ = [
    "record_loan_disbursal",
    "record_loan_release",
    "reverse_loan_disbursal",
    "reverse_loan_release",
]

