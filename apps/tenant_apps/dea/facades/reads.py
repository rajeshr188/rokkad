from django.contrib.contenttypes.models import ContentType

from apps.tenant_apps.dea.models import PaymentVoucher
from apps.tenant_apps.dea.models.journal import JournalEntry
from apps.tenant_apps.dea.models.voucher import Voucher, VoucherStatus
from apps.tenant_apps.dea.utils.currency import Balance


def resolve_posted_journal_entry(doc):
    """Return the most-recent JournalEntry for doc's posted Voucher, or None."""
    if not getattr(doc, "pk", None):
        return None

    content_type = ContentType.objects.get_for_model(doc, for_concrete_model=False)
    voucher = (
        Voucher.objects.filter(
            doc_content_type=content_type,
            doc_object_id=doc.pk,
            status=VoucherStatus.POSTED,
        )
        .order_by("-last_posted_at", "-id")
        .first()
    )
    if not voucher:
        return None

    return voucher.journal_entries.order_by("-id").first()


def get_loan_journal_entries(loan):
    """Resolve JournalEntry records linked to a loan via its PaymentVouchers."""
    payment_ids = list(loan.payments.values_list("id", flat=True))
    if not payment_ids:
        return JournalEntry.objects.none()

    payment_ct = ContentType.objects.get_for_model(PaymentVoucher)
    vouchers = Voucher.objects.filter(
        doc_content_type=payment_ct,
        doc_object_id__in=payment_ids,
    )
    if not vouchers.exists():
        return JournalEntry.objects.none()

    return (
        JournalEntry.objects.filter(voucher__in=vouchers)
        .select_related("voucher", "posted_by")
        .order_by("-posted_at")
    )


def get_account_transactions_for_journal_entries(journal_entries):
    """Return account transactions for a journal-entry iterable/queryset."""
    from apps.tenant_apps.dea.models import AccountTransaction

    return (
        AccountTransaction.objects.filter(journal_entry__in=journal_entries)
        .select_related("Account", "ledgerno")
        .order_by("id")
    )


def get_ledger_transactions_for_journal_entries(journal_entries):
    """Return ledger transactions for a journal-entry iterable/queryset."""
    from apps.tenant_apps.dea.models import LedgerTransaction

    return (
        LedgerTransaction.objects.filter(journal_entry__in=journal_entries)
        .select_related("ledgerno", "ledgerno_dr")
        .order_by("id")
    )


__all__ = [
    "Balance",
    "get_account_transactions_for_journal_entries",
    "get_ledger_transactions_for_journal_entries",
    "get_loan_journal_entries",
    "resolve_posted_journal_entry",
]
