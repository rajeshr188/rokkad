"""Independent dated evidence disclosures; these never authorize an action."""
from datetime import date
from django.core.exceptions import ObjectDoesNotExist
from apps.tenant_apps.loans.models import current_tenant_workspace_id
from .risk_portfolio import snapshot_is_current
from .transaction_completeness import transaction_completeness, capture_expectation
from .transaction_coverage import recorded_position_coverage, POSITION_COVERAGE_CONTRACT
from .assessment_evidence import snapshot_financial_usable, snapshot_coverage_usable


def loan_evidence_quality(loan, *, as_of_date, calculation_status=None, calculation_message="",
                          financial_history_from=None, principal_history_basis=None, exposure=None,
                          observation=None, risk=None, live_error="", transaction_coverage=None):
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None or workspace_id != loan.workspace_id or type(as_of_date) is not date:
        raise ValueError("Evidence quality requires the loan's Workspace and a reporting date.")
    try:
        snapshot = loan.risk_snapshot
    except ObjectDoesNotExist:
        snapshot = None
    not_required = loan.state == "CLOSED" or getattr(loan, "is_imported_closed_position", False)
    current = snapshot_is_current(snapshot, as_of_date) and not not_required
    assessment = ("UNASSESSED" if snapshot is None else "ERROR" if snapshot.status == "ERROR"
        else "CURRENT" if current else "STALE")
    source = snapshot.source_provenance if snapshot and (current or assessment == "ERROR") else {}
    source = source if isinstance(source, dict) else {}
    financial, coverage = source.get("financial", {}), source.get("coverage", {})
    financial = financial if isinstance(financial, dict) else {}
    coverage = coverage if isinstance(coverage, dict) else {}
    calculation = calculation_status or ("INCONSISTENT" if financial.get("integrity_findings") else
        financial.get("calculation_status") or ("SUPPORTED" if current and "recorded_total_due" in financial
        else "UNAVAILABLE" if current or assessment == "ERROR" else "UNASSESSED"))
    if not calculation_message and assessment == "ERROR" and calculation_status is None:
        calculation_message = snapshot.error_message
    if current and calculation_status is None and not snapshot_financial_usable(snapshot):
        calculation = "INCONSISTENT" if financial.get("integrity_findings") else "UNAVAILABLE"
    eligible = bool(current and snapshot_coverage_usable(snapshot))
    basis = "LIVE" if exposure is not None or observation is not None or risk is not None or live_error else "SAVED"
    valuation = dict(status="ELIGIBLE" if eligible else "UNAVAILABLE" if current else "UNASSESSED",
        basis="SAVED", blockers=coverage.get("blockers", []) if current else [],
        items=source.get("evidence", []) if current else [])
    if exposure is not None:
        calculation = "INCONSISTENT" if exposure.integrity_findings else "SUPPORTED"
        calculation_message = " ".join(exposure.integrity_findings)
        financial_history_from = exposure.financial_history_from
        principal_history_basis = exposure.principal_history_basis
    elif live_error and calculation_status is None:
        calculation, calculation_message = "UNAVAILABLE", live_error
    if observation is not None:
        ltv = getattr(observation, "ltv", None)
        usable_ltv = ltv is not None and ltv.ltv_ratio is not None and not ltv.blockers
        valuation = dict(status="ELIGIBLE" if usable_ltv else "OBSERVED" if observation.eligible_collateral_value is not None else "UNAVAILABLE",
            basis="LIVE", blockers=list(dict.fromkeys(code for row in observation.items for code in row.blockers)),
            items=[dict(item_id=row.collateral_item_id, rate_status=row.rate_status,
                appraisal_status=row.appraisal_status, rate_at=row.rate_effective_at,
                appraisal_at=row.appraisal_effective_at) for row in observation.items])
    saved_valuation = source.get("valuation", {})
    saved_valuation = saved_valuation if isinstance(saved_valuation, dict) else {}
    method = (getattr(observation, "valuation_method", None)
        or getattr(getattr(observation, "inputs", None), "method", None)) if observation is not None else saved_valuation.get("method")
    valuation["rate_required"] = method != "LATEST_APPRAISAL"
    valuation["appraisal_required"] = method != "CALCULATED_METAL_VALUE"
    result = risk if risk is not None else snapshot if current and not live_error and snapshot_financial_usable(snapshot) else None
    flags = tuple(result.flags) if result is not None else ()
    evidence_flags = tuple(flag for flag in flags if flag in
        {"VALUATION_UNKNOWN", "TRANSACTIONS_UNCONFIRMED", "OVERDUE_INTERPRETATION_VARIANCE"})
    measured_flags = tuple(flag for flag in flags if flag not in evidence_flags)
    risk_label = ("Measured risk and evidence need attention" if evidence_flags and measured_flags
        else "Evidence needs attention" if evidence_flags else "Measured risk needs attention" if measured_flags
        else "No identified risk flags" if result is not None else "Risk unavailable")
    if not_required:
        risk_label = "Monitoring not required for a closed loan"
    book_review = transaction_coverage.book_review if transaction_coverage else transaction_completeness(loan, as_of_date)
    if transaction_coverage is not None:
        transactions = transaction_coverage.evidence()
    elif basis == "SAVED" and calculation_status is None:
        # Portfolio/report GETs disclose saved evidence; do not recalculate every
        # loan's finances merely to render a completeness label.
        saved_transactions = source.get("transactions", {})
        if (current and snapshot_financial_usable(snapshot) and isinstance(saved_transactions, dict)
                and saved_transactions.get("contract") == POSITION_COVERAGE_CONTRACT
                and type(saved_transactions.get("complete")) is bool):
            transactions = saved_transactions.copy()
        else:
            transactions = dict(status="UNAVAILABLE" if current or assessment == "ERROR" else "UNASSESSED",
                complete=False, message="Refresh a supported financial assessment to establish saved position coverage.")
        if book_review.status == "INCOMPLETE":
            transactions.update(status="INCOMPLETE", complete=False, message=book_review.message)
    else:
        transactions = recorded_position_coverage(loan, as_of_date, book_review=book_review).evidence()
    book_evidence = book_review.evidence()
    if book_review.status in {"UNCONFIRMED", "BEHIND", "CHANGED"}:
        book_evidence["message"] = "No current complete external book check is recorded. This optional assurance is separate from usability of the represented position."
    if financial_history_from is None:
        events = getattr(loan, "_prefetched_objects_cache", {}).get("loan_events")
        opening = (next((e for e in events if e.event_kind == "MIGRATION_OPENING"), None) if events is not None
            else loan.loan_events.filter(event_kind="MIGRATION_OPENING").first())
        admitted = opening or (any(e.event_kind in {"DISBURSAL", "RENEWAL_OPENING"} for e in events)
            if events is not None else loan.loan_events.filter(event_kind__in=("DISBURSAL", "RENEWAL_OPENING")).exists())
        if admitted:
            financial_history_from = opening.effective_date if opening else loan.loan_date
            principal_history_basis = ("VERIFIED_TERMINAL_POSITION" if opening and opening.payload.get("opening", {}).get("profile") in {"loan-terminal-evidence/1", "loan-closed-position-evidence/1", "loan-closed-position-evidence/2"}
                else "OPENING_CHECKPOINT" if opening else "ORIGINAL_PAYOUT")
    return dict(
        risk=dict(label=risk_label, basis="LIVE" if risk is not None else "SAVED",
            severity=result.severity if result is not None else "UNKNOWN", measured_flags=measured_flags,
            evidence_flags=evidence_flags, message=live_error),
        basis=basis,
        capture=capture_expectation(loan, book_review),
        assessment=dict(status="NOT_REQUIRED" if not_required else assessment, as_of_date=snapshot.as_of_date if snapshot else None,
            last_severity=snapshot.severity if snapshot and assessment == "STALE" else ""),
        transactions=transactions,
        book_review=book_evidence,
        valuation=dict(valuation, status="NOT_REQUIRED" if not_required else valuation["status"]),
        calculation=dict(status=calculation, message=calculation_message,
            basis="LIVE" if exposure is not None or calculation_status is not None or live_error else "SAVED",
            profile=financial.get("servicing_profile")),
        history=dict(from_date=financial_history_from or financial.get("history_from"),
            principal_basis=principal_history_basis or financial.get("principal_history_basis")),
    )
