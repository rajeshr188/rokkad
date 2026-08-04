"""
DEA public facade.

Other apps should import DEA capabilities from this module only. The concrete
implementation lives in apps.tenant_apps.dea.facades.* so the public API stays
stable while the internal use cases remain small.
"""

from apps.tenant_apps.dea.facades.accounts import (
    ensure_customer_account,
    resolve_customer_account,
    resolve_party_account,
)
from apps.tenant_apps.dea.facades.journals import (
    post_interest_accrual_batch,
    post_journal_entry_voucher,
)
from apps.tenant_apps.dea.facades.loan_readiness import (
    LoanPostingPrerequisites,
    get_loan_posting_prerequisites,
)
from apps.tenant_apps.dea.facades.loan_events import (
    LoanEventPostingReceipt,
    post_pawn_loan_disbursal_event,
    post_pawn_loan_interest_accrual_event,
    post_pawn_loan_interest_capitalization_event,
    post_pawn_loan_repayment_event,
    post_pawn_loan_release_event,
    post_pawn_loan_auction_recovery_event,
    post_pawn_loan_renewal_event,
    reverse_pawn_loan_accounting_event,
)
from apps.tenant_apps.dea.facades.loan_reconciliation import (
    LoanAccountingReference,
    inspect_pawn_loan_accounting_reference,
)
from apps.tenant_apps.dea.facades.payments import (
    create_and_post_payment,
    find_payment_by_marker,
    has_other_posted_payments,
    post_payment_voucher,
    reverse_payment_by_marker,
)
from apps.tenant_apps.dea.facades.reads import (
    Balance,
    get_account_transactions_for_journal_entries,
    get_ledger_transactions_for_journal_entries,
    get_loan_journal_entries,
    resolve_posted_journal_entry,
)

__all__ = [
    "Balance",
    "LoanPostingPrerequisites",
    "LoanEventPostingReceipt",
    "LoanAccountingReference",
    "create_and_post_payment",
    "ensure_customer_account",
    "find_payment_by_marker",
    "get_account_transactions_for_journal_entries",
    "get_ledger_transactions_for_journal_entries",
    "get_loan_posting_prerequisites",
    "get_loan_journal_entries",
    "inspect_pawn_loan_accounting_reference",
    "has_other_posted_payments",
    "post_interest_accrual_batch",
    "post_pawn_loan_disbursal_event",
    "post_pawn_loan_interest_accrual_event",
    "post_pawn_loan_interest_capitalization_event",
    "post_pawn_loan_repayment_event",
    "post_pawn_loan_release_event",
    "post_pawn_loan_auction_recovery_event",
    "post_pawn_loan_renewal_event",
    "reverse_pawn_loan_accounting_event",
    "post_journal_entry_voucher",
    "post_payment_voucher",
    "resolve_customer_account",
    "resolve_party_account",
    "resolve_posted_journal_entry",
    "reverse_payment_by_marker",
]
