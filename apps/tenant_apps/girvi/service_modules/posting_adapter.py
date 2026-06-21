"""Compatibility import path for Girvi posting services.

New code should import from `apps.tenant_apps.girvi.integrations.dea_adapter`.
"""

from apps.tenant_apps.girvi.integrations.dea_adapter import (
    create_and_post_voucher_for_doc,
    find_payment_by_marker,
    get_loan_journal_entries,
    has_other_posted_payments,
    post_interest_accrual_batch,
    post_payment_voucher,
    resolve_customer_account,
    reverse_payment_by_marker,
)

__all__ = [
    "create_and_post_voucher_for_doc",
    "find_payment_by_marker",
    "get_loan_journal_entries",
    "has_other_posted_payments",
    "post_interest_accrual_batch",
    "post_payment_voucher",
    "resolve_customer_account",
    "reverse_payment_by_marker",
]
