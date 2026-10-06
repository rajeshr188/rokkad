"""Independent dated evidence disclosures; these never authorize an action."""
from datetime import date
from django.core.exceptions import ObjectDoesNotExist
from apps.tenant_apps.loans.models import current_tenant_workspace_id
from .risk_portfolio import snapshot_is_current
from .transaction_completeness import transaction_completeness


def loan_evidence_quality(loan, *, as_of_date, calculation_status=None, calculation_message="",
                          financial_history_from=None, principal_history_basis=None):
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None or workspace_id != loan.workspace_id or type(as_of_date) is not date:
        raise ValueError("Evidence quality requires the loan's Workspace and a reporting date.")
    try:
        snapshot = loan.risk_snapshot
    except ObjectDoesNotExist:
        snapshot = None
    current = snapshot_is_current(snapshot, as_of_date)
    assessment = ("UNASSESSED" if snapshot is None else "ERROR" if snapshot.status == "ERROR"
        else "CURRENT" if current else "STALE")
    source = snapshot.source_provenance if snapshot and current else {}
    financial, coverage = source.get("financial", {}), source.get("coverage", {})
    financial = financial if isinstance(financial, dict) else {}
    coverage = coverage if isinstance(coverage, dict) else {}
    calculation = calculation_status or ("INCONSISTENT" if financial.get("integrity_findings") else
        financial.get("calculation_status") or ("SUPPORTED" if current and "recorded_total_due" in financial
        else "UNAVAILABLE" if current or assessment == "ERROR" else "UNASSESSED"))
    if not calculation_message and assessment == "ERROR" and calculation_status is None:
        calculation_message = snapshot.error_message
    eligible = bool(current and snapshot.ltv_ratio is not None and not coverage.get("blockers")
        and coverage.get("status") in ("WITHIN_LIMIT", "BREACH"))
    if financial_history_from is None:
        events = getattr(loan, "_prefetched_objects_cache", {}).get("loan_events")
        opening = (next((e for e in events if e.event_kind == "MIGRATION_OPENING"), None) if events is not None
            else loan.loan_events.filter(event_kind="MIGRATION_OPENING").first())
        admitted = opening or (any(e.event_kind in {"DISBURSAL", "RENEWAL_OPENING"} for e in events)
            if events is not None else loan.loan_events.filter(event_kind__in=("DISBURSAL", "RENEWAL_OPENING")).exists())
        if admitted:
            financial_history_from = opening.effective_date if opening else loan.loan_date
            principal_history_basis = ("VERIFIED_TERMINAL_POSITION" if opening and opening.payload.get("opening", {}).get("profile") == "loan-terminal-evidence/1"
                else "OPENING_CHECKPOINT" if opening else "ORIGINAL_PAYOUT")
    return dict(
        assessment=dict(status=assessment, as_of_date=snapshot.as_of_date if snapshot else None),
        transactions=transaction_completeness(loan, as_of_date).evidence(),
        valuation=dict(status="ELIGIBLE" if eligible else "UNAVAILABLE" if current else "UNASSESSED",
            blockers=coverage.get("blockers", []), items=source.get("evidence", [])),
        calculation=dict(status=calculation, message=calculation_message,
            profile=financial.get("servicing_profile")),
        history=dict(from_date=financial_history_from or financial.get("history_from"),
            principal_basis=principal_history_basis or financial.get("principal_history_basis")),
    )
