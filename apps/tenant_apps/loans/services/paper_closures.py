"""Paper-first closure recording using ordinary immutable release evidence."""
import uuid
from datetime import date
from decimal import Decimal

from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.configuration.models import PreferenceAuditLog
from apps.tenant_apps.loans.models import (
    PaperClosureTransition, PawnCollateralCustodyEvent, PawnLoan,
    PawnReleaseBatch, PawnReleaseBatchLine, current_tenant_workspace_id,
)
from .action_access import require_workspace_action
from .pawn_release import preview_pawn_loan_full_release, _release_pawn_loan_in_full_at, _money_amount
from .release_batches import _digest, _text

MAX_PAPER_LOANS = 50
SALT = "loans.paper-closures.v1"


def _access(workspace, actor):
    if current_tenant_workspace_id() != workspace.pk:
        raise PermissionDenied("Select the matching workspace.")
    require_workspace_action(workspace, actor, "loan.release")


def transition_for(workspace, *, lock=False):
    if current_tenant_workspace_id() != workspace.pk:
        raise PermissionDenied("Select the matching workspace.")
    if lock:
        row, _ = PaperClosureTransition.objects.get_or_create(workspace=workspace)
        return PaperClosureTransition.objects.select_for_update().get(pk=row.pk)
    return PaperClosureTransition.objects.filter(workspace=workspace).first()


@transaction.atomic
def set_paper_transition(*, workspace, actor, system_first_date, retired, reason):
    _access(workspace, actor)
    require_workspace_action(workspace, actor, "workspace.transfer")
    reason = _text(reason, "reason", 255)
    if system_first_date is not None and type(system_first_date) is not date:
        raise ValueError("Choose a valid system-first date.")
    if not isinstance(retired, bool) or (retired and (system_first_date is None or system_first_date > timezone.localdate())):
        raise ValueError("Retirement requires a system-first date on or before today.")
    row = transition_for(workspace, lock=True)
    previous = {"system_first_date": str(row.system_first_date or ""), "retired": row.retired}
    row.system_first_date, row.retired, row.updated_by = system_first_date, retired, actor
    row.save()
    PreferenceAuditLog.objects.create(scope="workspace", key="loans.paper_closures", workspace=workspace,
        changed_by=actor, old_value=previous,
        new_value={"system_first_date": str(system_first_date or ""), "retired": retired, "reason": reason})
    return row


def _day(value):
    if type(value) is not date or value > timezone.localdate():
        raise ValueError("Actual closure date must be today or earlier.")
    return value


def _transition_access(workspace, actor, settings, day, exception_reason):
    required = settings and (settings.retired or (settings.system_first_date and day >= settings.system_first_date))
    if required or exception_reason:
        require_workspace_action(workspace, actor, "workspace.settings.manage")
    if required and not exception_reason:
        raise ValueError("Paper entry is restricted for this date. An administrator must give an exception reason.")


def _ids(values):
    try:
        ids = [int(value) for value in values]
    except (TypeError, ValueError) as exc:
        raise ValueError("Select valid loan numbers.") from exc
    if not 1 <= len(ids) <= MAX_PAPER_LOANS or min(ids) < 1 or len(set(ids)) != len(ids):
        raise ValueError(f"Choose 1–{MAX_PAPER_LOANS} different loans per submission.")
    return sorted(ids)


def _loans(workspace, ids, *, lock=False):
    query = PawnLoan.objects.filter(workspace=workspace, pk__in=ids).select_related("borrower", "license", "series").prefetch_related("series__number_sequences").order_by("pk")
    if lock:
        query = query.select_for_update(of=("self",))
    loans = list(query)
    if len(loans) != len(ids):
        raise ValueError("One or more loans are unavailable in this workspace.")
    return loans


def _quote(loan, day):
    if day < loan.loan_date:
        raise ValueError("Closure cannot precede the loan date.")
    if loan.loan_events.filter(effective_date__gt=day).exists():
        raise ValueError("Later financial activity exists. Review it before recording this earlier closure.")
    if loan.interest_accruals.filter(period_end__gt=day).exists():
        raise ValueError("Interest has been finalized beyond this closure date. Review the later periods first.")
    if PawnCollateralCustodyEvent.objects.filter(collateral_item__loan=loan, effective_date__gt=day).exists():
        raise ValueError("Later collateral movements exist. Review them before recording this earlier closure.")
    quote = preview_pawn_loan_full_release(loan.pk, as_of_date=day)
    if quote.blockers or quote.minimum_settlement is None:
        raise ValueError("; ".join(row.message for row in quote.blockers) or "Settlement unavailable.")
    revision = _digest({"day": day, "loan": loan.pk, "updated": loan.updated_at,
        "borrower": (loan.borrower_id, loan.borrower.display_name),
        "events": list(loan.loan_events.order_by("pk").values_list("pk", "payload_fingerprint")),
        "items": list(loan.collateral_items.order_by("pk").values_list("pk", "updated_at", "custody_state")),
        "amount": quote.minimum_settlement})
    return {"loan_id": loan.pk, "amount": str(quote.minimum_settlement), "revision": revision}, quote


def preview_paper_closures(*, workspace, actor, loan_ids, closure_date, exception_reason=""):
    _access(workspace, actor)
    day = _day(closure_date)
    exception_reason = _text(exception_reason, "exception reason", 255, required=False)
    _transition_access(workspace, actor, transition_for(workspace), day, exception_reason)
    rows, signed = [], []
    for loan in _loans(workspace, _ids(loan_ids)):
        row = {"loan": loan}
        try:
            evidence, quote = _quote(loan, day)
            row.update(amount=quote.minimum_settlement, quote=quote)
            signed.append(evidence)
        except (ValueError, ValidationError) as exc:
            row["error"] = str(exc)
        rows.append(row)
    return {"rows": rows, "date": day, "token": signing.dumps({"workspace": workspace.pk,
        "date": day.isoformat(), "rows": signed, "exception_reason": exception_reason}, salt=SALT),
        "ready_count": len(signed)}


def _decode(token, workspace, *, max_age=None):
    try:
        data = signing.loads(token, salt=SALT, max_age=max_age)
        if data["workspace"] != workspace.pk:
            raise ValueError("This review belongs to another workspace.")
        return data
    except (signing.BadSignature, KeyError, TypeError) as exc:
        raise ValueError("Review expired or invalid. Review the rows and confirm again.") from exc


@transaction.atomic
def complete_paper_closures(*, workspace, actor, request_key, quote_token, rows,
                            paper_reference="", confirmed=False):
    _access(workspace, actor)
    if confirmed is not True:
        raise ValueError("Confirm that the selected rows match the paper closures and all collateral was returned.")
    try:
        request_key = uuid.UUID(str(request_key))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("Invalid submission key.") from exc
    if not isinstance(rows, (list, tuple)) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("Review the selected rows.")
    ids = _ids([row.get("loan_id") for row in rows])
    data = _decode(quote_token, workspace)
    day = _day(date.fromisoformat(data["date"]))
    settings = transition_for(workspace, lock=True)
    _transition_access(workspace, actor, settings, day, data["exception_reason"])
    paper_reference = _text(paper_reference, "book/page reference", 100, required=False)
    loans = _loans(workspace, ids, lock=True)
    inputs = {int(row["loan_id"]): row for row in rows}
    normalized = []
    for loan in loans:
        row = inputs[loan.pk]
        cash = _money_amount(row.get("amount"), loan)
        concession = _money_amount(row.get("concession", 0), loan)
        reason = _text(row.get("concession_reason", ""), "concession reason", 255, required=bool(concession))
        if concession:
            require_workspace_action(workspace, actor, "workspace.settings.manage")
        other = row.get("collector_is_borrower", True)
        if not isinstance(other, bool):
            raise ValueError("Confirm who received the collateral.")
        normalized.append({"loan_id": loan.pk, "amount": str(cash), "concession": str(concession),
            "concession_reason": reason, "paid_by": _text(row.get("paid_by"), "payer", 255),
            "collector_is_borrower": other,
            "collector_name": _text(row.get("collector_name"), "recipient", 255),
            "relationship": _text(row.get("relationship", ""), "relationship", 100, required=not other),
            "authorization_note": _text(row.get("authorization_note", ""), "authority to collect", 500, required=not other),
            "paper_reference": _text(row.get("paper_reference") or paper_reference, "book/page reference", 100, required=False)})
    fingerprint = _digest({"quote": data, "rows": normalized, "paper_reference": paper_reference})
    total = sum((Decimal(row["amount"]) for row in normalized), Decimal("0"))
    batch, created = PawnReleaseBatch.objects.get_or_create(workspace=workspace, request_key=request_key,
        defaults={"mode": "PAPER", "effective_date": day, "request_fingerprint": fingerprint,
            "total_amount": total, "paid_by": "Individual collections", "paper_reference": paper_reference,
            "exception_reason": data["exception_reason"], "created_by": actor})
    if not created:
        if batch.mode != "PAPER" or batch.request_fingerprint != fingerprint:
            raise ValueError("This submission was already recorded with different details.")
        return batch
    _decode(quote_token, workspace, max_age=600)
    quoted = {row["loan_id"]: row for row in data["rows"]}
    for loan, row in zip(loans, normalized):
        current, _ = _quote(loan, day)
        if current != quoted.get(loan.pk):
            raise ValueError(f"Loan {loan.loan_number} changed or was not ready. Review it again.")
        if row["collector_is_borrower"] and row["collector_name"] != loan.borrower.display_name:
            raise ValueError("Select another recipient when someone other than the borrower received the items.")
        evidence = {"profile": "paper-closure/1", "batch_id": batch.pk, "date_precision": "DAY",
            "paid_by": row["paid_by"], "collector_name": row["collector_name"],
            "paper_reference": row["paper_reference"], "exception_reason": data["exception_reason"]}
        result = _release_pawn_loan_in_full_at(loan.pk, settlement_amount=row["amount"],
            request_key=f"paper:{request_key}:{loan.pk}", actor=actor, effective_date=day,
            interest_concession=row["concession"], concession_reason=row["concession_reason"], paper_evidence=evidence)
        PawnReleaseBatchLine.objects.create(workspace=workspace, batch=batch, release=result.release,
            borrower_name=loan.borrower.display_name, **{key: row[key] for key in
                ("paid_by", "paper_reference", "collector_name", "collector_is_borrower", "relationship", "authorization_note")})
    return batch
