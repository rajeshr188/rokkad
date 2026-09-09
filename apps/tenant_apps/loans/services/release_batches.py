"""Exact full releases grouped atomically; individual releases remain authoritative."""

import hashlib
import json
import uuid
from decimal import Decimal

from django.core import signing
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.tenancy.context import current_workspace_id
from apps.tenant_apps.loans.models import PawnLoan, PawnReleaseBatch, PawnReleaseBatchLine
from apps.tenant_apps.loans.selectors import get_pawn_loan_balance
from .action_access import require_workspace_action
from .pawn_release import preview_pawn_loan_full_release, release_pawn_loan_in_full


MAX_BATCH_LOANS = 20
QUOTE_SALT = "loans.full-release-batch.v1"
QUOTE_SECONDS = 600


def _authorize(workspace, actor):
    if current_workspace_id() != workspace.pk:
        raise PermissionDenied("Release requires the matching active workspace.")
    require_workspace_action(workspace, actor, "loan.release")


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def _ids(values):
    try:
        ids = [int(value) for value in values]
    except (TypeError, ValueError) as exc:
        raise ValueError("Select valid loan IDs.") from exc
    if not 1 <= len(ids) <= MAX_BATCH_LOANS or len(set(ids)) != len(ids) or min(ids) < 1:
        raise ValueError(f"Select 1–{MAX_BATCH_LOANS} different loans.")
    return sorted(ids)


def _loans(workspace, ids, *, lock=False):
    queryset = PawnLoan.objects.filter(workspace=workspace, pk__in=ids).order_by("pk")
    if lock:
        queryset = queryset.select_for_update(of=("self",))
    loans = list(queryset.select_related("borrower", "license", "series").prefetch_related("collateral_items__photos"))
    if len(loans) != len(ids):
        raise ValueError("One or more loans are unavailable in this workspace.")
    return loans


def _quote_row(loan):
    quote = preview_pawn_loan_full_release(loan.pk)
    if quote.blockers or quote.minimum_settlement is None:
        raise ValueError("; ".join(blocker.message for blocker in quote.blockers) or "Settlement is unavailable.")
    # A changed financial event or collateral record requires another review even
    # when its net effect leaves the combined settlement unchanged.
    revision = _digest({
        "date": timezone.localdate(), "loan": loan.pk, "updated": loan.updated_at,
        "borrower": (loan.borrower_id, loan.borrower.display_name),
        "events": list(loan.loan_events.order_by("pk").values_list("pk", "payload_fingerprint")),
        "items": list(loan.collateral_items.order_by("pk").values_list("pk", "updated_at", "custody_state")),
        "amount": quote.minimum_settlement,
    })
    return {"loan_id": loan.pk, "amount": str(quote.minimum_settlement), "revision": revision}, quote


def preview_release_batch(*, workspace, actor, loan_ids):
    _authorize(workspace, actor)
    rows, signed_rows = [], []
    total = Decimal("0")
    for loan in _loans(workspace, _ids(loan_ids)):
        row = {"loan": loan}
        try:
            evidence, quote = _quote_row(loan)
            balance = get_pawn_loan_balance(loan.pk, as_of_date=timezone.localdate())
            row.update(quote=quote, amount=quote.minimum_settlement,
                       fees=balance.fees_outstanding,
                       interest=quote.fees_and_interest_settlement - balance.fees_outstanding)
            signed_rows.append(evidence)
            total += quote.minimum_settlement
        except (ValueError, ObjectDoesNotExist, ValidationError) as exc:
            row["error"] = str(exc)
        rows.append(row)
    ready = len(signed_rows) == len(rows)
    token = signing.dumps({"workspace_id": workspace.pk, "date": str(timezone.localdate()), "rows": signed_rows}, salt=QUOTE_SALT) if ready else ""
    return {"rows": rows, "total": total, "ready": ready, "quote_token": token, "date": timezone.localdate()}


def decode_quote(token, *, workspace):
    try:
        data = signing.loads(token, salt=QUOTE_SALT)
        if data["workspace_id"] != workspace.pk:
            raise ValueError("The release quote belongs to another workspace.")
        _ids([row["loan_id"] for row in data["rows"]])
        return data
    except (signing.BadSignature, KeyError, TypeError) as exc:
        raise ValueError("The release quote is invalid. Select the loans again.") from exc


def _text(value, label, limit, *, required=True):
    if not isinstance(value, str) or len(value.strip()) > limit or (required and not value.strip()):
        raise ValueError(f"Enter a valid {label} (up to {limit} characters).")
    return value.strip()


@transaction.atomic
def complete_release_batch(*, workspace, actor, request_key, quote_token, paid_by,
                           payment_reference, collectors, payment_confirmed):
    _authorize(workspace, actor)
    if payment_confirmed is not True:
        raise ValueError("Confirm collection of the exact combined settlement.")
    try:
        request_key = uuid.UUID(str(request_key))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("Invalid batch request key.") from exc
    data = decode_quote(quote_token, workspace=workspace)
    ids = _ids([row["loan_id"] for row in data["rows"]])
    if not isinstance(collectors, (list, tuple)) or any(not isinstance(row, dict) for row in collectors):
        raise ValueError("Confirm one collector for every selected loan.")
    if _ids([row.get("loan_id") for row in collectors]) != ids:
        raise ValueError("Confirm one collector for every selected loan.")
    normalized = []
    for row in sorted(collectors, key=lambda row: int(row["loan_id"])):
        if row.get("handover_confirmed") is not True:
            raise ValueError("Verify each collector and confirm all items are ready for handover.")
        borrower = row.get("collector_is_borrower")
        if not isinstance(borrower, bool):
            raise ValueError("Select borrower or another collector for each loan.")
        normalized.append({
            "loan_id": int(row["loan_id"]), "collector_is_borrower": borrower,
            "collector_name": "" if borrower else _text(row.get("collector_name"), "collector name", 255),
            "relationship": "" if borrower else _text(row.get("relationship"), "relationship", 100),
            "authorization_note": "" if borrower else _text(row.get("authorization_note"), "authorization confirmation", 500),
        })
    paid_by = _text(paid_by, "payer name", 255)
    payment_reference = _text(payment_reference, "payment reference", 100, required=False)
    fingerprint = _digest({"quote": data, "collectors": normalized, "paid_by": paid_by, "payment_reference": payment_reference})
    total = sum((Decimal(row["amount"]) for row in data["rows"]), Decimal("0"))
    # The unique key serializes identical concurrent submissions. Incomplete headers
    # are never committed: any error below rolls back this whole transaction.
    batch, created = PawnReleaseBatch.objects.get_or_create(
        workspace=workspace, request_key=request_key,
        defaults={"request_fingerprint": fingerprint, "effective_date": data["date"],
                  "total_amount": total, "paid_by": paid_by, "payment_reference": payment_reference, "created_by": actor},
    )
    if not created:
        if batch.request_fingerprint != fingerprint:
            raise ValueError("This batch request was already used with different details.")
        return batch
    try:
        signing.loads(quote_token, salt=QUOTE_SALT, max_age=QUOTE_SECONDS)
    except signing.SignatureExpired as exc:
        raise ValueError("The quote has expired. Review the refreshed settlement and confirm again.") from exc
    if data["date"] != str(timezone.localdate()):
        raise ValueError("The release date has changed. Refresh and confirm today's settlement.")
    loans = _loans(workspace, ids, lock=True)
    quoted = {row["loan_id"]: row for row in data["rows"]}
    for loan in loans:
        current, _ = _quote_row(loan)
        if current != quoted[loan.pk]:
            raise ValueError(f"Loan {loan.loan_number} changed. Review the refreshed settlement and confirm again.")
    for loan, collector in zip(loans, normalized):
        result = release_pawn_loan_in_full(
            loan.pk, settlement_amount=quoted[loan.pk]["amount"],
            request_key=f"batch:{request_key}:{loan.pk}", actor=actor,
        )
        if str(result.release.effective_date) != data["date"]:
            raise ValueError("The date changed during release. Review the batch again.")
        PawnReleaseBatchLine.objects.create(
            workspace=workspace, batch=batch, release=result.release,
            borrower_name=loan.borrower.display_name,
            collector_name=loan.borrower.display_name if collector["collector_is_borrower"] else collector["collector_name"],
            collector_is_borrower=collector["collector_is_borrower"],
            relationship=collector["relationship"], authorization_note=collector["authorization_note"],
        )
    return batch
