"""DEA facade adapter for Girvi posting services."""

from apps.tenant_apps.dea.facade import (
    create_and_post_payment,
    find_payment_by_marker,
    has_other_posted_payments,
    post_payment_voucher,
    reverse_payment_by_marker,
)

create_and_post_voucher_for_doc = create_and_post_payment

__all__ = [
    "create_and_post_voucher_for_doc",
    "find_payment_by_marker",
    "has_other_posted_payments",
    "post_payment_voucher",
    "reverse_payment_by_marker",
]
