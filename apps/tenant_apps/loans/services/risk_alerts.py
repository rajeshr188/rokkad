from django.utils import timezone

from apps.tenant_apps.loans.models import LoanRiskAlert, LoanRiskSnapshot


_ALERT_DETAILS = {
    LoanRiskAlert.Kind.DPD_WORSENING: (
        "HIGH", "Delinquency worsened for this PawnLoan.",
        "Review overdue obligations and begin the approved collection follow-up.",
    ),
    LoanRiskAlert.Kind.LTV_BREACH: (
        "HIGH", "Collateral coverage breached the monitoring LTV threshold.",
        "Review valuation evidence and the permitted recovery workflow.",
    ),
    LoanRiskAlert.Kind.MATURITY: (
        "MEDIUM", "This PawnLoan entered a maturity-attention state.",
        "Review repayment, renewal, or settlement readiness with the customer.",
    ),
    LoanRiskAlert.Kind.ASSESSMENT_FAILURE: (
        "HIGH", "The current risk assessment could not be completed.",
        "Open Loan health and correct the reported evidence or setup blocker.",
    ),
}


def sync_risk_alerts(snapshot, transitions_and_events):
    """Project material immutable risk transitions into open staff work items."""
    created = []
    by_kind = {}
    for transition, event in transitions_and_events:
        kind = _alert_kind(transition)
        if kind:
            by_kind.setdefault(kind, event)
        elif transition.event_type == "ASSESSMENT_INITIALIZED":
            for initial_kind in _active_kinds(snapshot):
                by_kind.setdefault(initial_kind, event)
    for kind, event in by_kind.items():
        if LoanRiskAlert.objects.filter(
            workspace_id=snapshot.workspace_id,
            loan_id=snapshot.loan_id,
            alert_kind=kind,
            status=LoanRiskAlert.Status.OPEN,
        ).exists():
            continue
        severity, message, action = _ALERT_DETAILS[kind]
        created.append(LoanRiskAlert.objects.create(
            workspace_id=snapshot.workspace_id,
            loan_id=snapshot.loan_id,
            source_event=event,
            alert_kind=kind,
            severity=severity,
            message=message,
            recommended_action=action,
        ))
    active = _active_kinds(snapshot)
    recovery_events = {kind: event for kind, event in by_kind.items() if kind not in active}
    for kind in set(LoanRiskAlert.Kind.values) - active:
        update = {"status": LoanRiskAlert.Status.RESOLVED, "resolved_at": timezone.now()}
        if kind in recovery_events:
            update["resolved_by_event"] = recovery_events[kind]
        LoanRiskAlert.objects.filter(
            workspace_id=snapshot.workspace_id,
            loan_id=snapshot.loan_id,
            alert_kind=kind,
            status=LoanRiskAlert.Status.OPEN,
        ).update(**update)
    return tuple(created)


def _alert_kind(transition):
    event_type = transition.event_type
    if event_type == "DELINQUENCY_ENTERED":
        return LoanRiskAlert.Kind.DPD_WORSENING
    if event_type == "DPD_BUCKET_CHANGED" and _dpd_rank(transition.new_value) > _dpd_rank(transition.old_value):
        return LoanRiskAlert.Kind.DPD_WORSENING
    if event_type in {"LTV_BREACH_ENTERED", "LTV_CRITICAL_ENTERED"}:
        return LoanRiskAlert.Kind.LTV_BREACH
    if event_type in {"MATURITY_WARNING_ENTERED", "PAST_MATURITY_ENTERED"}:
        return LoanRiskAlert.Kind.MATURITY
    if event_type == "ASSESSMENT_ERROR_ENTERED":
        return LoanRiskAlert.Kind.ASSESSMENT_FAILURE
    return None


def _dpd_rank(value):
    bucket = value.get("bucket") if isinstance(value, dict) else "CURRENT"
    return {"CURRENT": 0, "DPD_1_29": 1, "DPD_30_59": 2, "DPD_60_89": 3, "DPD_90_PLUS": 4}.get(bucket, 0)


def _active_kinds(snapshot):
    flags = set(snapshot.flags or ())
    active = set()
    if (snapshot.days_past_due or 0) > 0:
        active.add(LoanRiskAlert.Kind.DPD_WORSENING)
    if flags & {"LTV_BREACH", "LTV_CRITICAL"}:
        active.add(LoanRiskAlert.Kind.LTV_BREACH)
    if flags & {"MATURITY_APPROACHING", "PAST_MATURITY"}:
        active.add(LoanRiskAlert.Kind.MATURITY)
    if snapshot.status == LoanRiskSnapshot.Status.ERROR:
        active.add(LoanRiskAlert.Kind.ASSESSMENT_FAILURE)
    return active


__all__ = ["sync_risk_alerts"]
