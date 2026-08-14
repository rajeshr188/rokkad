from decimal import Decimal

from django.utils import timezone
from moneyed import Money

from apps.tenant_apps.dea.models import JournalEntryLineItem, JournalEntryVoucher, VoucherType
from apps.tenant_apps.dea.posting.engine import DjangoPostingEngine
from apps.tenant_apps.dea.posting.resolver import get_ledger_id_by_key
from apps.tenant_apps.dea.services.post_doc import create_and_post_voucher_for_doc


_MONEY_PLACES = Decimal("0.01")


def post_journal_entry_voucher(doc, user) -> tuple:
    """Post an already-created JournalEntryVoucher to accounting."""
    return create_and_post_voucher_for_doc(
        doc=doc,
        user=user,
        voucher_type_input=doc.get_voucher_type(),
        engine=DjangoPostingEngine(),
    )


def post_interest_accrual_batch(
    command,
    preview,
    created_rows,
    *,
    posted_status_value,
) -> tuple:
    """Create and post a JournalEntryVoucher for a batch of interest accruals."""
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
    effective_date = (
        preview.effective_end_date or preview.as_of_date or timezone.localdate()
    )

    accrual_doc = JournalEntryVoucher.objects.create(
        je_date=effective_date,
        entry_type="ACCRUAL",
        description=(
            f"Loan interest accrual for {preview.loan_id} through {effective_date}"
        ),
        memo="LOAN_INTEREST_ACCRUAL",
        reference=(
            f"LOAN-ACCRUAL:{getattr(command.loan, 'pk', 'new')}:"
            f"{effective_date.isoformat()}"
        ),
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
