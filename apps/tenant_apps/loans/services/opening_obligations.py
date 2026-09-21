"""Persist reviewed remaining obligations against an existing migration opening.

This is a Loans-owned building block used by the atomic opening importer. It
does not create or approve an opening, activate servicing, or infer due dates.
"""
import hashlib
import json
from datetime import date
from decimal import Decimal

from django.db import transaction

from apps.tenant_apps.loans.models import (
    PawnLoan, RepaymentScheduleVersion, RepaymentObligation, current_tenant_workspace_id,
)
from .history_setup import require_history_setup_access
from .opening_evidence import OpeningEvidenceError, read_opening_evidence
from .pawn_tranches import get_pawn_principal_tranche_balances

CONTRACT = "loan-opening-obligations/1"


@transaction.atomic
def persist_opening_repayment_schedule(loan_id, *, actor):
    workspace_id = current_tenant_workspace_id()
    require_history_setup_access(workspace_id, actor)
    try:
        loan = PawnLoan.objects.select_for_update().get(pk=loan_id, workspace_id=workspace_id)
    except PawnLoan.DoesNotExist as exc:
        raise OpeningEvidenceError("Opening loan was not found in the active Workspace.") from exc
    events = tuple(loan.loan_events.order_by("pk"))
    if loan.state != "ACTIVE" or len(events) != 1 or events[0].event_kind != "MIGRATION_OPENING":
        raise OpeningEvidenceError("Remaining obligations require a sole active migration opening before servicing.")
    origin = events[0]
    opening = read_opening_evidence(loan, origin)
    get_pawn_principal_tranche_balances(loan, as_of_date=origin.effective_date)
    review = opening["review"]
    rows = sorted(review["obligations"], key=lambda row: (row["due"], row["id"]))
    principal = Decimal(review["balances"]["principal"])
    remaining = principal
    expected = []
    for sequence, row in enumerate(rows, 1):
        amount, interest = Decimal(row["principal"]), Decimal(row["interest"])
        if amount + interest == 0:
            raise OpeningEvidenceError("Remaining obligation rows must contain a positive amount.")
        expected.append((sequence, date.fromisoformat(row["due"]), amount, interest, remaining, remaining - amount))
        remaining -= amount
    fingerprint = hashlib.sha256(json.dumps(
        {"contract": CONTRACT, "opening": opening}, sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()
    fields = {
        "contract_version": CONTRACT, "fingerprint": fingerprint,
        # This existing field anchors the original contract; no disbursal event is created.
        "disbursed_on": loan.loan_date, "maturity_date": date.fromisoformat(review["terms"]["maturity_date"]),
        "principal": principal, "contractual_interest": sum(row[3] for row in expected),
        "rounding_adjustment": Decimal("0"),
    }
    existing = loan.repayment_schedules.first()
    columns = ("sequence", "due_date", "principal_due", "interest_due", "opening_principal", "closing_principal")
    if existing:
        if (loan.repayment_schedules.count() != 1 or existing.source_event_id != origin.pk or
                existing.version != 1 or existing.supersedes_id is not None or
                any(getattr(existing, key) != value for key, value in fields.items()) or
                tuple(existing.obligations.order_by("sequence").values_list(*columns)) != tuple(expected)):
            raise OpeningEvidenceError("Existing schedule differs from the frozen opening obligations.")
        return existing
    schedule = RepaymentScheduleVersion.objects.create(
        workspace_id=workspace_id, loan=loan, source_event=origin, version=1, created_by=actor, **fields,
    )
    for row in expected:
        RepaymentObligation.objects.create(
            workspace_id=workspace_id, loan=loan, schedule_version=schedule, **dict(zip(columns, row)),
        )
    return schedule
