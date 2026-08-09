"""Authenticated, tenant-bound production boundary for accounting mutations."""

from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, transaction
from django.utils import timezone
from django_tenants.utils import get_public_schema_name

from apps.orgs.permissions import get_effective_permissions

from .models import AccountingBook, TransactionBatch, Voucher
from .services import (
    add_account_transaction,
    add_ledger_transaction,
    allocate_voucher_number,
    authorize_voucher,
    create_draft_voucher,
    post_authorized_voucher,
    reverse_posted_batch,
    bootstrap_mvp_accounting,
    transition_period,
    create_open_item,
    allocate_open_item,
    append_external_account_classification,
)
from .models import ExternalAccount, ExternalAccountPurpose, Ledger, LedgerSide, OpenItem, ReportingClass
from apps.tenant_apps.party.models import Party

CREATE = "accounting_voucher_create"
AUTHORIZE = "accounting_voucher_authorize"
POST = "accounting_voucher_post"
REVERSE = "accounting_voucher_reverse"
MANAGE_PERIOD = "accounting_period_manage"


def _identity(actor) -> str:
    return "|".join(
        (
            f"user:{actor.pk}",
            f"username:{getattr(actor, 'username', '')}",
            f"email:{getattr(actor, 'email', '')}",
        )
    )[:512]


def _assert_access(*, actor, workspace, permission: str) -> int:
    if not actor or not getattr(actor, "is_authenticated", False):
        raise PermissionDenied("Authentication is required for accounting actions.")
    if not getattr(actor, "is_active", False):
        raise PermissionDenied("An active user is required for accounting actions.")
    schema_name = getattr(workspace, "schema_name", "")
    if not schema_name or schema_name == get_public_schema_name():
        raise PermissionDenied("A tenant workspace is required for accounting actions.")
    if connection.schema_name != schema_name:
        raise PermissionDenied("The active tenant does not match the accounting workspace.")
    if permission not in get_effective_permissions(actor, workspace):
        raise PermissionDenied(f"Missing accounting permission: {permission}.")
    actor_id = getattr(actor, "pk", None)
    if not isinstance(actor_id, int) or actor_id <= 0:
        raise PermissionDenied("Accounting actors require a durable user identifier.")
    return actor_id


def _assert_book_boundary(*, book: AccountingBook, workspace) -> None:
    if not isinstance(book, AccountingBook):
        raise ValidationError("book must be an AccountingBook")
    tenant_key = book.organization.external_tenant_key
    if tenant_key and tenant_key != workspace.schema_name:
        raise PermissionDenied("Accounting book does not belong to this workspace.")


def create_draft(*, actor, workspace, book: AccountingBook, **intent) -> Voucher:
    actor_id = _assert_access(actor=actor, workspace=workspace, permission=CREATE)
    _assert_book_boundary(book=book, workspace=workspace)
    intent.pop("voucher_number", None)
    effective_date = intent["effective_date"]
    return create_draft_voucher(
        book=book,
        voucher_number=allocate_voucher_number(
            book=book, effective_date=effective_date
        ),
        created_by_id=actor_id,
        created_by_identity=_identity(actor),
        **intent,
    )


def add_ledger_line(*, actor, workspace, voucher: Voucher, **line):
    _assert_access(actor=actor, workspace=workspace, permission=CREATE)
    _assert_book_boundary(book=voucher.book, workspace=workspace)
    return add_ledger_transaction(voucher=voucher, **line)


def add_account_line(*, actor, workspace, voucher: Voucher, **line):
    _assert_access(actor=actor, workspace=workspace, permission=CREATE)
    _assert_book_boundary(book=voucher.book, workspace=workspace)
    return add_account_transaction(voucher=voucher, **line)


def authorize(*, actor, workspace, voucher: Voucher) -> Voucher:
    actor_id = _assert_access(actor=actor, workspace=workspace, permission=AUTHORIZE)
    _assert_book_boundary(book=voucher.book, workspace=workspace)
    return authorize_voucher(
        voucher=voucher,
        actor_id=actor_id,
        authorized_at=timezone.now(),
        actor_identity=_identity(actor),
    )


def post(*, actor, workspace, voucher: Voucher) -> TransactionBatch:
    actor_id = _assert_access(actor=actor, workspace=workspace, permission=POST)
    _assert_book_boundary(book=voucher.book, workspace=workspace)
    current = Voucher.objects.select_related("book__organization").get(pk=voucher.pk)
    if current.authorized_by_id == actor_id:
        raise PermissionDenied("The voucher authorizer cannot also post it.")
    return post_authorized_voucher(
        voucher=current,
        actor_id=actor_id,
        posted_at=timezone.now(),
        actor_identity=_identity(actor),
    )


@transaction.atomic
def post_receivable(*, actor, workspace, voucher: Voucher, open_item_key: str, due_date=None):
    batch = post(actor=actor, workspace=workspace, voucher=voucher)
    current = Voucher.objects.get(pk=voucher.pk)
    item = create_receivable_item(
        actor=actor,
        workspace=workspace,
        origin_transaction=current.transactions.get(sequence=1).account_detail,
        open_item_key=open_item_key,
        due_date=due_date,
    )
    return batch, item


def reverse(
    *,
    actor,
    workspace,
    original: TransactionBatch,
    voucher_key: str,
    idempotency_key: str,
    reversal_date,
    reason: str,
    correction_group_key: str = "",
    voucher_number: str = "",
) -> TransactionBatch:
    actor_id = _assert_access(actor=actor, workspace=workspace, permission=REVERSE)
    current = TransactionBatch.objects.select_related("book__organization").get(
        pk=original.pk
    )
    _assert_book_boundary(book=current.book, workspace=workspace)
    if current.posted_by_id == actor_id:
        raise PermissionDenied("The original poster cannot approve its reversal.")
    return reverse_posted_batch(
        original=current,
        voucher_key=voucher_key,
        idempotency_key=idempotency_key,
        reversal_date=reversal_date,
        actor_id=actor_id,
        occurred_at=timezone.now(),
        reason=reason,
        correction_group_key=correction_group_key,
        voucher_number=allocate_voucher_number(
            book=current.book, effective_date=reversal_date
        ),
        actor_identity=_identity(actor),
    )


def change_period(*, actor, workspace, period, to_status, reason=""):
    actor_id = _assert_access(actor=actor, workspace=workspace, permission=MANAGE_PERIOD)
    _assert_book_boundary(book=period.book, workspace=workspace)
    return transition_period(
        period=period, to_status=to_status, actor_id=actor_id,
        actor_identity=_identity(actor), occurred_at=timezone.now(), reason=reason,
    )


def bootstrap(*, actor, workspace, period_key, start_date, end_date):
    _assert_access(actor=actor, workspace=workspace, permission=MANAGE_PERIOD)
    return bootstrap_mvp_accounting(
        tenant_key=workspace.schema_name,
        tenant_name=workspace.name,
        period_key=period_key,
        start_date=start_date,
        end_date=end_date,
    )


def create_receivable_item(*, actor, workspace, origin_transaction, open_item_key, due_date=None):
    actor_id = _assert_access(actor=actor, workspace=workspace, permission=CREATE)
    _assert_book_boundary(book=origin_transaction.transaction.voucher.book, workspace=workspace)
    return create_open_item(
        origin_transaction=origin_transaction, open_item_key=open_item_key,
        created_by_id=actor_id, due_date=due_date,
    )


def allocate_receipt(*, actor, workspace, settlement_transaction, open_item, amount):
    actor_id = _assert_access(actor=actor, workspace=workspace, permission=CREATE)
    _assert_book_boundary(book=open_item.book, workspace=workspace)
    return allocate_open_item(
        settlement_transaction=settlement_transaction, open_item=open_item,
        sequence=1, amount=amount, base_amount=amount, created_by_id=actor_id,
    )


@transaction.atomic
def create_customer_receivable_account(*, actor, workspace, book, party=None, new_party_name="", effective_from):
    actor_id = _assert_access(actor=actor, workspace=workspace, permission=CREATE)
    _assert_book_boundary(book=book, workspace=workspace)
    if party is None:
        name = (new_party_name or "").strip()
        if not name:
            raise ValidationError("A Party or new Party name is required.")
        party = Party.objects.create(
            display_name=name, created_by_id=actor_id, updated_by_id=actor_id
        )
    if party.status != Party.PartyStatus.ACTIVE:
        raise ValidationError("The selected Party is not active.")
    account_key = f"PARTY-{party.pk}:AR"
    account, created = ExternalAccount.objects.get_or_create(
        book=book,
        party=party,
        purpose=ExternalAccountPurpose.CUSTOMER_RECEIVABLE,
        defaults={
            "account_key": account_key,
            "party_key": party.party_code,
            "name": party.display_name,
        },
    )
    if not account.classification_versions.exists():
        append_external_account_classification(
            external_account=account,
            version_key=f"PARTY-{party.pk}-AR-V1",
            effective_from=effective_from,
            reporting_ledger=Ledger.objects.get(book=book, ledger_key="ACCOUNTS_RECEIVABLE"),
            reporting_class=ReportingClass.ASSET,
            normal_side=LedgerSide.DEBIT,
        )
    return account


@transaction.atomic
def owner_confirm(*, actor, workspace, voucher, open_item_key="", due_date=None):
    from .feature_flags import (
        get_accounting_workflow_mode,
        is_accounting_successor_enabled,
    )

    actor_id = _assert_access(actor=actor, workspace=workspace, permission=POST)
    current = Voucher.objects.select_related("book__organization").get(pk=voucher.pk)
    _assert_book_boundary(book=current.book, workspace=workspace)
    if workspace.owner_id != actor_id:
        raise PermissionDenied("Owner-operated confirmation requires the workspace owner.")
    if not is_accounting_successor_enabled(workspace):
        raise PermissionDenied("Standalone accounting writes are disabled.")
    if get_accounting_workflow_mode(workspace) != "OWNER":
        raise PermissionDenied("Owner confirmation is unavailable in Team mode.")
    if current.state == "DRAFT":
        authorize_voucher(
            voucher=current, actor_id=actor_id, authorized_at=timezone.now(),
            actor_identity=_identity(actor),
        )
        current.refresh_from_db()
    batch = post_authorized_voucher(
        voucher=current, actor_id=actor_id, posted_at=timezone.now(),
        actor_identity=_identity(actor),
    )
    item = None
    if open_item_key:
        current.refresh_from_db()
        item = create_open_item(
            origin_transaction=current.transactions.get(sequence=1).account_detail,
            open_item_key=open_item_key, created_by_id=actor_id, due_date=due_date,
        )
    return batch, item


@transaction.atomic
def owner_reverse(*, actor, workspace, original, reversal_date, reason):
    from .feature_flags import (
        get_accounting_workflow_mode,
        is_accounting_successor_enabled,
    )
    from .selectors import open_item_outstanding

    actor_id = _assert_access(actor=actor, workspace=workspace, permission=REVERSE)
    current = TransactionBatch.objects.select_for_update().select_related(
        "book__organization", "voucher"
    ).get(pk=original.pk)
    _assert_book_boundary(book=current.book, workspace=workspace)
    if workspace.owner_id != actor_id:
        raise PermissionDenied("Owner-operated reversal requires the workspace owner.")
    if not is_accounting_successor_enabled(workspace):
        raise PermissionDenied("Standalone accounting writes are disabled.")
    if get_accounting_workflow_mode(workspace) != "OWNER":
        raise PermissionDenied("Owner reversal is unavailable in Team mode.")
    existing = current.reversal_batches.first()
    if existing is not None:
        return existing
    for item in OpenItem.objects.filter(
        origin_transaction__transaction__voucher=current.voucher
    ):
        if open_item_outstanding(item).amount != item.original_amount:
            raise ValidationError(
                "Reverse allocated receipts before reversing this credit sale."
            )
    return reverse_posted_batch(
        original=current,
        voucher_key=f"UI-REV-{current.pk}",
        idempotency_key=f"ui:reversal:{current.pk}",
        reversal_date=reversal_date,
        actor_id=actor_id,
        occurred_at=timezone.now(),
        reason=reason,
        voucher_number=allocate_voucher_number(
            book=current.book, effective_date=reversal_date
        ),
        actor_identity=_identity(actor),
    )
