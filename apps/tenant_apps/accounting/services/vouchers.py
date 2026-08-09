from datetime import date, datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction as db_transaction

from ..models import (
    AccountTransaction,
    AccountingBook,
    AccountingTransaction,
    ExternalAccount,
    Ledger,
    LedgerSide,
    LedgerTransaction,
    PersistedVoucherState,
    TransactionDiscriminator,
    Voucher,
    VoucherPurpose,
    VoucherNumberSequence,
)
from ..selectors import resolve_external_account_classification


@db_transaction.atomic
def create_draft_voucher(
    *,
    book: AccountingBook,
    voucher_key: str,
    idempotency_key: str,
    effective_date: date,
    source_system: str,
    source_type: str,
    source_id: str,
    source_version: str,
    rule_key: str,
    rule_version: str,
    purpose: str = VoucherPurpose.ORDINARY,
    voucher_number: str = "",
    narration: str = "",
    correction_group_key: str = "",
    created_by_id: int | None = None,
    created_by_identity: str = "",
) -> Voucher:
    if not isinstance(book, AccountingBook):
        raise ValidationError("book must be an AccountingBook")
    return Voucher.objects.create(
        book=book,
        voucher_key=voucher_key,
        voucher_number=voucher_number,
        effective_date=effective_date,
        purpose=purpose,
        idempotency_key=idempotency_key,
        source_system=source_system,
        source_type=source_type,
        source_id=source_id,
        source_version=source_version,
        rule_key=rule_key,
        rule_version=rule_version,
        narration=narration,
        correction_group_key=correction_group_key,
        created_by_id=created_by_id,
        created_by_identity=(
            created_by_identity
            or (f"user:{created_by_id}" if created_by_id else "legacy:service-unattributed")
        ),
    )


@db_transaction.atomic
def allocate_voucher_number(*, book: AccountingBook, effective_date: date) -> str:
    periods = list(
        book.periods.select_for_update().filter(
            start_date__lte=effective_date, end_date__gte=effective_date
        )
    )
    if len(periods) != 1:
        raise ValidationError("Exactly one accounting period must cover the voucher date.")
    sequence_year = periods[0].start_date.year
    sequence, _ = VoucherNumberSequence.objects.select_for_update().get_or_create(
        book=book, sequence_year=sequence_year, defaults={"next_number": 1}
    )
    number = sequence.next_number
    sequence.next_number = number + 1
    sequence.save(update_fields=("next_number",))
    return f"{book.book_key}-{sequence_year}-{number:06d}"


def _locked_draft(voucher: Voucher) -> Voucher:
    if not isinstance(voucher, Voucher):
        raise ValidationError("voucher must be a Voucher")
    locked = Voucher.objects.select_for_update().select_related("book").get(pk=voucher.pk)
    if locked.state != PersistedVoucherState.DRAFT:
        raise ValidationError("Only a draft voucher may be changed.")
    return locked


@db_transaction.atomic
def add_ledger_transaction(
    *,
    voucher: Voucher,
    sequence: int,
    debit_ledger: Ledger,
    credit_ledger: Ledger,
    amount: Decimal,
    currency: str,
    base_amount: Decimal,
    base_currency: str,
    exchange_rate: Decimal,
    rate_source: str,
    narration: str = "",
) -> AccountingTransaction:
    locked = _locked_draft(voucher)
    base = AccountingTransaction.objects.create(
        voucher=locked,
        sequence=sequence,
        discriminator=TransactionDiscriminator.LEDGER,
        amount=amount,
        currency=currency,
        base_amount=base_amount,
        base_currency=base_currency,
        exchange_rate=exchange_rate,
        rate_source=rate_source,
        narration=narration,
    )
    LedgerTransaction.objects.create(
        transaction=base,
        debit_ledger=debit_ledger,
        credit_ledger=credit_ledger,
    )
    return base


@db_transaction.atomic
def add_account_transaction(
    *,
    voucher: Voucher,
    sequence: int,
    ledger: Ledger,
    external_account: ExternalAccount,
    ledger_side: str,
    amount: Decimal,
    currency: str,
    base_amount: Decimal,
    base_currency: str,
    exchange_rate: Decimal,
    rate_source: str,
    narration: str = "",
) -> AccountingTransaction:
    if ledger_side not in LedgerSide.values:
        raise ValidationError("ledger_side is invalid")
    locked = _locked_draft(voucher)
    classification = resolve_external_account_classification(
        external_account=external_account,
        effective_date=locked.effective_date,
    )
    base = AccountingTransaction.objects.create(
        voucher=locked,
        sequence=sequence,
        discriminator=TransactionDiscriminator.ACCOUNT,
        amount=amount,
        currency=currency,
        base_amount=base_amount,
        base_currency=base_currency,
        exchange_rate=exchange_rate,
        rate_source=rate_source,
        narration=narration,
    )
    AccountTransaction.objects.create(
        transaction=base,
        ledger=ledger,
        external_account=external_account,
        ledger_side=ledger_side,
        classification=classification,
    )
    return base


@db_transaction.atomic
def authorize_voucher(
    *, voucher: Voucher, actor_id: int, authorized_at: datetime, actor_identity: str = ""
) -> Voucher:
    locked = _locked_draft(voucher)
    transactions = list(
        locked.transactions.select_related("ledger_detail", "account_detail")
        .order_by("sequence")
    )
    if not transactions:
        raise ValidationError("Voucher must contain at least one atomic transaction.")
    for item in transactions:
        if item.discriminator == TransactionDiscriminator.LEDGER:
            if not hasattr(item, "ledger_detail") or hasattr(item, "account_detail"):
                raise ValidationError("Ledger transaction subtype is incomplete.")
        elif item.discriminator == TransactionDiscriminator.ACCOUNT:
            if not hasattr(item, "account_detail") or hasattr(item, "ledger_detail"):
                raise ValidationError("Account transaction subtype is incomplete.")
        else:
            raise ValidationError("Transaction discriminator is invalid.")
    locked.state = PersistedVoucherState.AUTHORIZED
    locked.authorized_by_id = actor_id
    locked.authorized_by_identity = actor_identity or f"user:{actor_id}"
    locked.authorized_at = authorized_at
    locked.save(update_fields=("state", "authorized_by_id", "authorized_by_identity", "authorized_at", "updated_at"))
    return locked
