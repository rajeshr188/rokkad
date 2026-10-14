import hashlib
import json
from django.utils import timezone

from apps.tenant_apps.loans.models import LoanRiskAlert, LoanRiskSnapshot, LoanRiskEvent


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
    recovery_events = {}
    assessment_recovery = None
    for transition, event in transitions_and_events:
        kind = _alert_kind(transition)
        if kind:
            by_kind.setdefault(kind, event)
        elif transition.event_type == "ASSESSMENT_INITIALIZED":
            for initial_kind in _active_kinds(snapshot):
                by_kind.setdefault(initial_kind, event)
        recovery_kind = _recovery_kind(transition.event_type)
        if recovery_kind:
            recovery_events[recovery_kind] = event
        if transition.event_type == "ASSESSMENT_ERROR_RECOVERED":
            assessment_recovery = event
    active = _active_kinds(snapshot)
    open_alerts = {row.alert_kind: row for row in LoanRiskAlert.objects.filter(
        workspace_id=snapshot.workspace_id, loan_id=snapshot.loan_id,
        status=LoanRiskAlert.Status.OPEN,
    )}
    for kind, event in by_kind.items():
        if kind not in active or kind in open_alerts:
            continue
        severity, message, action = _ALERT_DETAILS[kind]
        created.append(LoanRiskAlert.objects.create(
            workspace_id=snapshot.workspace_id,
            loan_id=snapshot.loan_id,
            source_event=event,
            alert_kind=kind,
            severity=_severity(kind, snapshot),
            message=message,
            recommended_action=action,
        ))
    for kind, alert in open_alerts.items():
        if kind in active:
            if snapshot.status == LoanRiskSnapshot.Status.CURRENT:
                severity = _severity(kind, snapshot)
                if alert.severity != severity:
                    alert.severity = severity
                    alert.save(update_fields=["severity"])
        elif _can_resolve(kind, snapshot):
            event = recovery_events.get(kind) or assessment_recovery
            if event is None:
                event = _confirmed_recovery(snapshot, alert)
            alert.status = LoanRiskAlert.Status.RESOLVED
            alert.resolved_at = timezone.now()
            alert.resolved_by_event = event
            alert.save(update_fields=["status", "resolved_at", "resolved_by_event"])
    return tuple(created)


def _recovery_kind(event_type):
    return {
        "DELINQUENCY_CURED": LoanRiskAlert.Kind.DPD_WORSENING,
        "LTV_BREACH_CURED": LoanRiskAlert.Kind.LTV_BREACH,
        "LTV_CRITICAL_CURED": LoanRiskAlert.Kind.LTV_BREACH,
        "VALUATION_ERROR_CURED": LoanRiskAlert.Kind.LTV_BREACH,
        "MATURITY_WARNING_EXITED": LoanRiskAlert.Kind.MATURITY,
        "PAST_MATURITY_CURED": LoanRiskAlert.Kind.MATURITY,
        "ASSESSMENT_ERROR_RECOVERED": LoanRiskAlert.Kind.ASSESSMENT_FAILURE,
    }.get(event_type)


def _can_resolve(kind, snapshot):
    if snapshot.status != LoanRiskSnapshot.Status.CURRENT:
        return False
    if kind == LoanRiskAlert.Kind.DPD_WORSENING:
        return snapshot.days_past_due is not None and snapshot.days_past_due == 0
    if kind == LoanRiskAlert.Kind.LTV_BREACH:
        return snapshot.ltv_ratio is not None and "VALUATION_UNKNOWN" not in (snapshot.flags or ())
    return True


def _severity(kind, snapshot):
    flags = set(snapshot.flags or ())
    if kind == LoanRiskAlert.Kind.LTV_BREACH and "LTV_CRITICAL" in flags:
        return "CRITICAL"
    if kind == LoanRiskAlert.Kind.DPD_WORSENING and "DPD_SUBSTANDARD" in flags:
        return "CRITICAL"
    if kind == LoanRiskAlert.Kind.MATURITY and "PAST_MATURITY" in flags:
        return "HIGH"
    return _ALERT_DETAILS[kind][0]


def _confirmed_recovery(snapshot, alert):
    """A retained alert may outlive its old flags; capture today's actual clearance."""
    trigger = hashlib.sha256(json.dumps({
        "type": "ALERT_CONDITION_CLEARED", "alert_id": alert.pk,
        "assessment": snapshot.assessment_fingerprint, "as_of": snapshot.as_of_date.isoformat(),
    }, sort_keys=True).encode()).hexdigest()
    return LoanRiskEvent.objects.get_or_create(
        workspace_id=snapshot.workspace_id, loan_id=snapshot.loan_id, trigger_key=trigger,
        defaults={
            "snapshot": snapshot, "event_type": "ALERT_CONDITION_CLEARED", "as_of_date": snapshot.as_of_date,
            "old_value": {"alert_id": alert.pk, "kind": alert.alert_kind},
            "new_value": {"cleared": True, "days_past_due": snapshot.days_past_due,
                          "ltv_ratio": str(snapshot.ltv_ratio) if snapshot.ltv_ratio is not None else None,
                          "flags": snapshot.flags},
            "new_fingerprint": snapshot.assessment_fingerprint, "policy_identity": snapshot.policy_identity,
            "metadata": {"projection_status": snapshot.status},
        },
    )[0]


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
