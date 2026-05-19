"""
DEA Public Facade — the ONLY module other apps should import from.

All other DEA modules (models, posting engine, services) are internal.
Callers pass primitives + a generic source object; this module handles
all PaymentVoucher creation and accounting engine calls.

Usage from girvi (or any other app):
    from apps.tenant_apps.dea.facade import create_and_post_payment, reverse_payment_by_marker
"""

from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from moneyed import Money

from apps.tenant_apps.dea.models import (
    JournalEntryLineItem,
    JournalEntryVoucher,
    PaymentVoucher,
    VoucherType,
)
from apps.tenant_apps.dea.models.journal import JournalEntry
from apps.tenant_apps.dea.models.voucher import Voucher, VoucherStatus
from apps.tenant_apps.dea.posting.engine import DjangoPostingEngine
from apps.tenant_apps.dea.posting.resolver import get_ledger_id_by_key
from apps.tenant_apps.dea.services.post_doc import create_and_post_voucher_for_doc
from apps.tenant_apps.dea.utils.currency import Balance  # re-exported utility


def create_and_post_payment(
    source_obj,
    *,
    direction: str,
    payment_type: str,
    total_amount,
    amount_in_base_currency,
    payment_date,
    payment_method: str = "CASH",
    reference_number: str,
    description: str,
    created_by,
    updated_by=None,
    create_release: bool = False,
    # Optional fields
    principal_amount=None,
    interest_amount=None,
    is_final_payment: bool = False,
) -> tuple:
    """
    Create a PaymentVoucher for source_obj and immediately post it to accounting.

    Idempotent: if a PaymentVoucher with the same reference_number already exists
    for source_obj, it is returned without re-posting.

    Returns:
        (PaymentVoucher, created: bool)

    Args:
        source_obj:         The domain object this payment relates to (GivenLoan, Release, etc.)
        direction:          "PAYMENT" (cash out) or "RECEIPT" (cash in)
        payment_type:       "DISBURSAL", "RECEIPT", "REFUND", or "OTHER"
        total_amount:       Money amount (djmoney Money instance)
        amount_in_base_currency: Money amount in base currency
        payment_date:       date of cash movement
        payment_method:     "CASH", "BANK", "CHEQUE", "UPI", "CARD", "OTHER"
        reference_number:   deterministic idempotency key (caller constructs this)
        description:        human-readable label for the voucher
        created_by:         User who triggered the action
        updated_by:         User to record as updater (defaults to created_by)
        create_release:     True when this receipt represents a GivenLoan release
        principal_amount:   optional principal portion (Money)
        interest_amount:    optional interest portion (Money)
        is_final_payment:   True if this closes the source document
    """
    if updated_by is None:
        updated_by = created_by

    ct = ContentType.objects.get_for_model(source_obj)
    existing = PaymentVoucher.objects.filter(
        source_content_type=ct,
        source_object_id=source_obj.pk,
        reference_number=reference_number,
    ).first()
    if existing:
        return existing, False

    create_kwargs = dict(
        source_document=source_obj,
        direction=direction,
        payment_type=payment_type,
        total_amount=total_amount,
        amount_in_base_currency=amount_in_base_currency,
        payment_date=payment_date,
        payment_method=payment_method,
        reference_number=reference_number,
        description=description,
        is_final_payment=is_final_payment,
        create_release=create_release,
        created_by=created_by,
        updated_by=updated_by,
    )
    if principal_amount is not None:
        create_kwargs["principal_amount"] = principal_amount
    if interest_amount is not None:
        create_kwargs["interest_amount"] = interest_amount

    payment = PaymentVoucher.objects.create(**create_kwargs)

    create_and_post_voucher_for_doc(
        doc=payment,
        user=created_by,
        voucher_type_input=payment.get_voucher_type(),
        engine=DjangoPostingEngine(),
    )

    payment.posted = True
    payment.save(update_fields=["posted"])
    return payment, True


def reverse_payment_by_marker(source_obj, marker: str, user) -> "PaymentVoucher":
    """
    Find a posted PaymentVoucher by its idempotency marker and reverse it.

    Raises:
        ValueError: if no matching PaymentVoucher is found, or it has no posted
                    accounting voucher.

    Returns:
        PaymentVoucher (now de-posted)
    """
    ct = ContentType.objects.get_for_model(source_obj)
    payment = PaymentVoucher.objects.filter(
        source_content_type=ct,
        source_object_id=source_obj.pk,
        reference_number=marker,
    ).first()
    if not payment:
        raise ValueError(
            f"No PaymentVoucher found for {source_obj.__class__.__name__} "
            f"pk={source_obj.pk} with marker '{marker}'."
        )

    pv_ct = ContentType.objects.get_for_model(PaymentVoucher)
    try:
        accounting_voucher = Voucher.objects.get(
            doc_content_type=pv_ct,
            doc_object_id=payment.pk,
            status=VoucherStatus.POSTED,
        )
    except Voucher.DoesNotExist:
        raise ValueError(
            f"No POSTED accounting voucher found for PaymentVoucher {payment.pk}."
        )

    DjangoPostingEngine().reverse_voucher(accounting_voucher.pk, user)
    payment.posted = False
    payment.save(update_fields=["posted"])
    return payment


def has_other_posted_payments(source_obj, exclude_marker: str) -> bool:
    """
    Return True if source_obj has posted PaymentVouchers other than the one
    identified by exclude_marker. Used as a guard before reversing a disbursal.
    """
    ct = ContentType.objects.get_for_model(source_obj)
    exclude_payment = PaymentVoucher.objects.filter(
        source_content_type=ct,
        source_object_id=source_obj.pk,
        reference_number=exclude_marker,
    ).values_list("pk", flat=True).first()

    qs = PaymentVoucher.objects.filter(
        source_content_type=ct,
        source_object_id=source_obj.pk,
        posted=True,
    )
    if exclude_payment:
        qs = qs.exclude(pk=exclude_payment)
    return qs.exists()


def resolve_posted_journal_entry(doc):
    """
    Return the most-recent JournalEntry for doc's posted Voucher, or None.

    Used by sales (Invoice, Receipt) and any other domain that needs to read
    the accounting ledger entry for a document without importing DEA internals.
    """
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


def post_payment_voucher(payment, user) -> None:
    """
    Post an already-created PaymentVoucher to accounting.

    Use this when you have constructed a PaymentVoucher externally (e.g. via
    loan.create_payment()) and need to push it through the accounting engine.

    Marks payment.posted = True and saves update_fields=["posted"] on success.
    Raises on posting failure — the caller is responsible for atomic wrapping.
    """
    create_and_post_voucher_for_doc(
        doc=payment,
        user=user,
        voucher_type_input=payment.get_voucher_type(),
        engine=DjangoPostingEngine(),
    )
    payment.posted = True
    payment.save(update_fields=["posted"])


def post_journal_entry_voucher(doc, user) -> tuple:
    """
    Post an already-created JournalEntryVoucher to accounting.

    Used by interest accrual and other internal DEA journal creation flows
    where the voucher document has already been constructed.

    Returns:
        (accounting_voucher, journal_entry) as returned by create_and_post_voucher_for_doc
    """
    return create_and_post_voucher_for_doc(
        doc=doc,
        user=user,
        voucher_type_input=doc.get_voucher_type(),
        engine=DjangoPostingEngine(),
    )


def ensure_customer_account(customer) -> None:
    """
    Ensure a DEA Account exists for a Contact Customer.

    Creates or updates the Account with the correct AccountType_Ext based on
    customer_type:
    - "W" or "R" → Debtor
    - anything else → Creditor

    Idempotent: safe to call on every Customer save.
    """
    from apps.tenant_apps.dea.models import Account, AccountType_Ext, EntityType

    entity_t = EntityType.objects.get(name="Person")
    if customer.customer_type in ("W", "R"):
        acct_type = AccountType_Ext.objects.get(description="Debtor")
    else:
        acct_type = AccountType_Ext.objects.get(description="Creditor")

    Account.objects.update_or_create(
        contact=customer,
        entity=entity_t,
        defaults={"AccountType_Ext": acct_type},
    )


_MONEY_PLACES = Decimal("0.01")


def get_loan_journal_entries(loan):
    """
    Resolve JournalEntry records linked to a loan via its PaymentVouchers:
      Loan -> PaymentVoucher -> Voucher -> JournalEntry

    Returns a JournalEntry queryset ordered by most-recently-posted first.
    """
    from django.contrib.contenttypes.models import ContentType

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


def post_interest_accrual_batch(
    command,
    preview,
    created_rows,
    *,
    posted_status_value,
) -> tuple:
    """
    Create and post a JournalEntryVoucher to accounting for a batch of accrual rows.

    This is the DEA-internal implementation of interest accrual posting, extracted
    from InterestAccrualService._post_accrual_batch_to_accounting so that the
    girvi accrual service no longer needs to import DEA model constructors.

    Args:
        command:             InterestAccrualCommand with .loan, .created_by
        preview:             InterestAccrualPreview with .effective_end_date, .as_of_date, .loan_id
        created_rows:        Iterable of LoanInterestAccrual rows with .accrued_amount
        posted_status_value: Status value to set on each accrual row after posting.

    Returns:
        (accrual_doc, accounting_voucher, journal_entry) — all None if total_amount <= 0
    """
    total_amount = Decimal(
        str(
            sum(
                (
                    Decimal(str(getattr(row, "accrued_amount", Decimal("0.00"))))
                    for row in created_rows
                ),
                Decimal("0.00"),
            )
        )
    ).quantize(_MONEY_PLACES)

    if total_amount <= 0:
        return None, None, None

    interest_receivable_id = get_ledger_id_by_key("INTEREST_RECEIVABLE")
    interest_income_id = get_ledger_id_by_key("INTEREST_INCOME")
    effective_date = preview.effective_end_date or preview.as_of_date or timezone.localdate()

    accrual_doc = JournalEntryVoucher.objects.create(
        je_date=effective_date,
        entry_type="ACCRUAL",
        description=(
            f"Loan interest accrual for {preview.loan_id} through {effective_date}"
        ),
        memo="LOAN_INTEREST_ACCRUAL",
        reference=f"LOAN-ACCRUAL:{getattr(command.loan, 'pk', 'new')}:{effective_date.isoformat()}",
        total_debit=Money(total_amount, "INR"),
        total_credit=Money(total_amount, "INR"),
        reviewed_by=command.created_by,
        reviewed_at=timezone.now() if command.created_by else None,
        created_by=command.created_by,
        updated_by=command.created_by,
        auto_post_to_accounting=False,
    )
    JournalEntryLineItem.objects.bulk_create(
        [
            JournalEntryLineItem(
                journal_entry=accrual_doc,
                line_number=1,
                ledger_id=interest_receivable_id,
                ledger_name="INTEREST_RECEIVABLE",
                side="DR",
                amount=Money(total_amount, "INR"),
                description=f"Interest receivable recognition for {preview.loan_id}",
            ),
            JournalEntryLineItem(
                journal_entry=accrual_doc,
                line_number=2,
                ledger_id=interest_income_id,
                ledger_name="INTEREST_INCOME",
                side="CR",
                amount=Money(total_amount, "INR"),
                description=f"Interest income recognition for {preview.loan_id}",
            ),
        ]
    )

    VoucherType.objects.get_or_create(
        name=accrual_doc.get_voucher_type(),
        defaults={"description": "System-posted loan interest accrual"},
    )
    accounting_voucher, journal_entry = create_and_post_voucher_for_doc(
        doc=accrual_doc,
        user=command.created_by,
        voucher_type_input=accrual_doc.get_voucher_type(),
        engine=DjangoPostingEngine(),
    )

    for row in created_rows:
        update_fields = []
        if getattr(row, "status", None) != posted_status_value:
            row.status = posted_status_value
            update_fields.append("status")
        if getattr(row, "journal_entry_voucher", None) != accrual_doc:
            row.journal_entry_voucher = accrual_doc
            update_fields.append("journal_entry_voucher")
        if update_fields and hasattr(row, "save"):
            row.save(update_fields=update_fields)

    return accrual_doc, accounting_voucher, journal_entry


__all__ = [
    "Balance",
    "create_and_post_payment",
    "ensure_customer_account",
    "get_loan_journal_entries",
    "has_other_posted_payments",
    "post_interest_accrual_batch",
    "post_journal_entry_voucher",
    "post_payment_voucher",
    "resolve_posted_journal_entry",
    "reverse_payment_by_marker",
]
