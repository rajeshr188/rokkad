# accounting/posting/engine.py
from .context import PostingContext, compute_fingerprint
from .registry import registry
from .validate import assert_balanced, assert_non_empty, assert_currency_fields
from ..models import (
    JournalEntry,
    Voucher,
    VoucherStatus,
    LedgerTransaction,
    AccountTransaction,
)

from abc import ABC
from django.utils import timezone
from django.db import transaction
import logging

from apps.tenant_apps.dea.posting.types import PostingBundle, PostingError, Side

logger = logging.getLogger(__name__)


"""
Posting Engine Algorithm (ERP Standard)

Step by step:

Lock voucher row
SELECT ... FOR UPDATE so two workers cannot post same voucher simultaneously.

Generate “posting fingerprint”
A hash of current voucher’s economic state.
Used for idempotency.

Check if voucher is already posted

If there is a last JE with same fingerprint → DO NOTHING RETURN IT
(this means voucher did not change economically)

If voucher was posted but changed → reverse last JE
create new JE that negates all lines of last JE

Run posting rule for voucher type
(sales logic, purchase logic, loan disbursement logic… etc)
This returns a PostingBundle of ledger_lines + account_lines.

Balance validation
SUM(debit_base) == SUM(credit_base)
If not → raise error (posting never allowed)

Create new JournalEntry and insert ledger/account lines under it.

Save new JE fingerprint on JE so next call is idempotent

Update voucher status → POSTED or CORRECTED

Commit transaction
"""


class BasePostingEngine(ABC):
    """
    Template method with idempotency, locking, validations, and reversal.
    """

    def post(self, ctx: PostingContext):
        with transaction.atomic():
            try:
                # lock the voucher we will post
                voucher = self._lock_voucher(ctx)
                rule = registry.get(
                    getattr(voucher.voucher_type, "name", voucher.voucher_type)
                )

                # build hybrid fingerprint payload and compute fingerprint
                payload = self._build_fingerprint_payload(ctx, rule)
                new_fp = self._compute_fingerprint(payload, rule.rule_version)

                # Locate previous posted voucher for the same business doc (supersede semantics)
                prev_voucher = None
                try:
                    prev_voucher = (
                        Voucher.objects.filter(
                            doc_content_type=voucher.doc_content_type,
                            doc_object_id=voucher.doc_object_id,
                        )
                        .exclude(pk=voucher.pk)
                        .filter(
                            status__in=(
                                VoucherStatus.POSTED.value,
                                VoucherStatus.CORRECTED.value,
                            )
                        )
                        .order_by("-last_posted_at")
                        .select_related("voucher_type")
                        .first()
                    )
                except Exception:
                    prev_voucher = None

                # Idempotent fast-path: if previous voucher (for same doc) already has same fingerprint
                if (
                    prev_voucher
                    and getattr(prev_voucher, "fingerprint", None) == new_fp
                ):
                    # return its journal entry if exists
                    try:
                        return getattr(prev_voucher, "journal_entry")
                    except Exception:
                        return None

                # If there is a previous posted voucher and fingerprint changed, reverse it
                if (
                    prev_voucher
                    and getattr(prev_voucher, "fingerprint", None) != new_fp
                ):
                    # lock the previous voucher row before mutating its JE/status
                    try:
                        prev_voucher = Voucher.objects.select_for_update().get(
                            pk=prev_voucher.pk
                        )
                    except Voucher.DoesNotExist:
                        prev_voucher = None

                    prev_je = (
                        getattr(prev_voucher, "journal_entry", None)
                        if prev_voucher
                        else None
                    )
                    if prev_je:
                        # create reversing JE (attached to previous voucher) and mark previous voucher corrected
                        self._reverse_journal_entry(prev_je, ctx)
                        prev_voucher.status = VoucherStatus.REVERSED.value
                        prev_voucher.save(update_fields=["status"])

                # build lines via rule for current voucher
                bundle: PostingBundle = rule.build_posting(ctx)

                # validations
                assert_non_empty(bundle)
                assert_currency_fields(bundle)
                assert_balanced(bundle)

                # write JE and lines onto current voucher
                je = self._write_journal_entry(ctx, bundle)

                # update voucher fingerprint AFTER successful posting
                voucher.fingerprint = new_fp
                voucher.last_posted_at = timezone.now()
                voucher.status = (
                    VoucherStatus.POSTED.value
                    if voucher.status
                    in (VoucherStatus.DRAFT.value, VoucherStatus.REVERSED.value, "")
                    else VoucherStatus.CORRECTED.value
                )
                voucher.save(update_fields=["fingerprint", "last_posted_at", "status"])
                return je
            except Exception as e:
                # Log exception or handle as needed
                logger.error(
                    f"Posting failed for voucher {getattr(ctx.voucher, 'id', None)}: {e}"
                )
                raise PostingError(f"Posting failed: {str(e)}") from e

    def reverse_voucher(self, voucher_id, user):
        voucher = Voucher.objects.get(pk=voucher_id)
        last_je = voucher.journal_entries.order_by("-id").first()
        if not last_je:
            return None

        ctx = PostingContext(voucher=voucher, doc=voucher.business_doc, user_id=user.id)
        rev = self._reverse_journal_entry(last_je, ctx)
        voucher.status = VoucherStatus.REVERSED.value
        voucher.save(update_fields=["status"])
        return rev

    def _validate_business_rules(self, ctx: PostingContext):
        """Domain-specific validations"""
        if ctx.voucher.status == VoucherStatus.CANCELLED:
            raise PostingError("Cannot post cancelled voucher")

    # hooks
    def _lock_voucher(self, ctx: PostingContext) -> Voucher:
        return Voucher.objects.select_for_update().get(pk=ctx.voucher.pk)

    def _build_fingerprint_payload(self, ctx: PostingContext, rule) -> dict:
        """
        Hybrid payload:
          - voucher-minimal (id, type, updated_at)
          - document economic payload (if provided by doc)
          - rule overlay (if provided by rule)
        All parts must be JSON-serializable by compute_fingerprint.
        """
        v = ctx.voucher
        base = {
            "voucher": {
                "id": getattr(v, "id", None),
                "type": getattr(getattr(v, "voucher_type", None), "name", None),
                "updated_at": getattr(v, "updated_at", None),
            }
        }
        # document economic payload
        d = getattr(ctx, "doc", None)
        if d and hasattr(d, "get_economic_payload"):
            try:
                doc_payload = d.get_economic_payload() or {}
            except Exception:
                doc_payload = {}
            if not isinstance(doc_payload, dict):
                doc_payload = {"value": doc_payload}
            base["doc"] = doc_payload

        # rule overlay (e.g., scenario) – optional
        overlay = {}
        fp_payload = getattr(rule, "fingerprint_payload", None)
        if callable(fp_payload):
            try:
                overlay = fp_payload(ctx) or {}
            except Exception:
                overlay = {}
        if not isinstance(overlay, dict):
            overlay = {"value": overlay}

        if overlay:
            base["rule"] = overlay
        return base

    def _compute_fingerprint(self, payload, rule_version: str) -> str:
        return compute_fingerprint(payload, rule_version)

    def _get_latest_je(self, voucher: Voucher) -> JournalEntry | None:
        return voucher.journal_entries.order_by("-id").first()

    def _write_journal_entry(
        self, ctx: PostingContext, bundle: PostingBundle
    ) -> JournalEntry:
        je = JournalEntry.objects.create(
            voucher=ctx.voucher,
            posted_by_id=ctx.user_id,
        )
        self._bulk_create_lines(je, bundle)
        return je

    def _bulk_create_lines(self, je: JournalEntry, bundle: PostingBundle):
        # Direct mapping to your dual-ledger model
        if bundle.ledger_lines:
            LedgerTransaction.objects.bulk_create(
                [
                    LedgerTransaction(
                        journal_entry=je,
                        ledgerno_dr_id=dl.debit_ledger_id,  # FK to Ledger
                        ledgerno_id=dl.credit_ledger_id,  # FK to Ledger
                        amount=dl.amount,  # MoneyField
                    )
                    for dl in bundle.ledger_lines
                ]
            )

        # Account lines with proper FK relationships
        if bundle.account_lines:
            AccountTransaction.objects.bulk_create(
                [
                    AccountTransaction(
                        journal_entry=je,
                        ledgerno_id=a.ledger_id,  # FK to Ledger
                        Account_id=a.account_id,  # FK to Account
                        XactTypeCode_id=self._get_transaction_type_id(
                            a.side
                        ),  # FK to TransactionType_DE
                        XactTypeCode_ext_id=a.xact_type_ext,
                        amount=a.amount,  # MoneyField
                    )
                    for a in bundle.account_lines
                ]
            )

    def _get_transaction_type_id(self, side: Side) -> str:
        """Return the XactTypeCode PK (str) — XactTypeCode IS the primary_key on TransactionType_DE."""
        from ..models.account import TransactionType_DE

        return TransactionType_DE.objects.get(XactTypeCode=side).pk

    def _reverse_journal_entry(
        self, original: JournalEntry, ctx: PostingContext
    ) -> JournalEntry:
        has_ledger = LedgerTransaction.objects.filter(journal_entry=original).exists()
        has_account = AccountTransaction.objects.filter(journal_entry=original).exists()

        if not has_ledger and not has_account:
            return None

        rev = JournalEntry.objects.create(
            voucher=original.voucher,
            posted_by_id=getattr(ctx, "user_id", None),
            is_reversal_of=original,
        )

        # Dual-ledger reversal: swap debit/credit ledgers (like your untransact method)
        if has_ledger:
            orig_ledger_txns = LedgerTransaction.objects.filter(journal_entry=original)
            LedgerTransaction.objects.bulk_create(
                [
                    LedgerTransaction(
                        journal_entry=rev,
                        ledgerno_dr_id=txn.ledgerno_id,  # Swap: credit becomes debit
                        ledgerno_id=txn.ledgerno_dr_id,  # Swap: debit becomes credit
                        amount=txn.amount,  # Same amount
                    )
                    for txn in orig_ledger_txns
                ]
            )

        # Account reversal: flip sides (like your untransact method)
        if has_account:
            orig_account_txns = AccountTransaction.objects.filter(
                journal_entry=original
            )
            reversed_txns = []
            for txn in orig_account_txns:
                # Flip the transaction type
                old_side = txn.XactTypeCode.XactTypeCode  # "Dr" or "Cr"
                new_side = "Cr" if old_side == "Dr" else "Dr"

                reversed_txns.append(
                    AccountTransaction(
                        journal_entry=rev,
                        ledgerno_id=txn.ledgerno_id,
                        Account_id=txn.Account_id,
                        XactTypeCode_id=self._get_transaction_type_id(new_side),
                        XactTypeCode_ext_id=txn.XactTypeCode_ext_id,  # Keep same ext type
                        amount=txn.amount,
                    )
                )

            if reversed_txns:
                AccountTransaction.objects.bulk_create(reversed_txns)

        return rev


class DjangoPostingEngine(BasePostingEngine):
    """
    Concrete final engine used by Django deployment.
    Right now we don't override any hook because BasePostingEngine default hooks are correct.
    Later if we need: tenant routing, audit logging, permission checks etc
    we override here.
    """

    pass
