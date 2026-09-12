"""Worker-only bounded refresh with one committed Workspace context per loan."""
from django.db import connection

from apps.tenancy.context import current_workspace_id, workspace_context
from apps.tenant_apps.loans.models import PawnLoan
from .risk_snapshots import (
    RiskSnapshotRefreshError, _pending_loans, _require_active_workspace,
    reassess_pawn_loans_batch,
)


def reassess_pawn_loans_pass(*, workspace_id, as_of_date, batch_size=100):
    """Select bounded candidates, then claim/recheck each inside its own transaction.

    A claim is the loan row lock, held through calculation and projection writes.
    Crash/rollback releases it and leaves the loan due; no external queue needed.
    This entry point cannot be wrapped in a request or caller transaction.
    """
    if connection.in_atomic_block or current_workspace_id() is not None:
        raise RiskSnapshotRefreshError("Worker pass requires no surrounding transaction or Workspace context.")
    workspace_id, batch_size = int(workspace_id), int(batch_size)
    if workspace_id < 1 or not 1 <= batch_size <= 1000:
        raise RiskSnapshotRefreshError("Use a positive Workspace ID and batch size from 1 to 1000.")
    with workspace_context(workspace_id):
        _require_active_workspace(workspace_id)
        candidates = tuple(_pending_loans(PawnLoan.objects.all(), workspace_id, as_of_date)
                           .values_list("pk", flat=True)[:batch_size])
    result = {"selected": 0, "current": 0, "errors": []}
    for loan_id in candidates:
        # Another worker may have assessed it, or servicing may have closed it,
        # since selection. The batch service rechecks state/currentness and skips
        # locked loans. Each candidate is attempted at most once in this pass.
        with workspace_context(workspace_id):
            row = reassess_pawn_loans_batch(workspace_id=workspace_id,
                as_of_date=as_of_date, batch_size=1, loan_ids=(loan_id,))
        result["selected"] += row["selected"]
        result["current"] += row["current"]
        result["errors"].extend(row["errors"])
    return result
