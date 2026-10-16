"""Current monitoring choices and explicit compatibility references, never approval."""
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal

from apps.tenant_apps.loans.domain import ValuationMethod
from apps.tenant_apps.loans.models import LoanMonitoringPolicy, current_tenant_workspace_id
from .monitoring_policy import LoanRiskAssessmentError, resolve_monitoring_policy


@dataclass(frozen=True)
class MonitoringValuationInputs:
    loan_id: int
    as_of_date: date
    policy: LoanMonitoringPolicy | None
    method: ValuationMethod | None
    valuation_basis: str
    saved_method: str
    currency_quantum: Decimal
    precision_source: str
    reference_ltv_ratio: Decimal | None
    reference_limit_source: str
    compatibility_identity: str
    policy_error: str


def resolve_monitoring_valuation_inputs(loan, *, as_of_date: date) -> MonitoringValuationInputs:
    """Keep saved numerical defaults without requiring a historical decision.

    The saved method is a compatibility fallback, not original approval proof.
    Precision follows the saved agreement where available, preserving results;
    without one, current observations use paise, not invented interest terms.
    A missing saved reference limit stays unknown, never a monitoring threshold.
    """
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None or loan.workspace_id != workspace_id:
        raise ValueError("Monitoring inputs require the loan's active Workspace context.")
    if type(as_of_date) is not date:
        raise ValueError("Monitoring inputs require a reporting date.")
    saved = loan.policy_snapshot if loan.policy_snapshot_id else None
    try:
        policy = resolve_monitoring_policy(workspace_id=workspace_id,
            license_id=loan.license_id, as_of_date=as_of_date)
        policy_error = ""
    except LoanRiskAssessmentError as exc:
        policy, policy_error = None, str(exc)
    basis = policy.valuation_basis if policy else "ORIGINAL_AGREEMENT"
    saved_method = saved.valuation_method if saved else ""
    selected = saved_method if basis == "ORIGINAL_AGREEMENT" else basis
    recorded = saved is not None and saved.basis == "RECORDED_CONTRACT"
    identity = (f"{'recorded-monitoring-basis' if recorded else 'loan-policy-snapshot'}:{saved.pk}"
        if saved else "current-monitoring:no-saved-loan-policy")
    return MonitoringValuationInputs(loan.pk, as_of_date, policy,
        ValuationMethod(selected) if selected else None, basis, saved_method,
        Decimal(str(saved.currency_quantum)).normalize() if saved else Decimal("0.01"),
        "SAVED_AGREEMENT" if saved else "MONITORING_PAISE_DEFAULT",
        Decimal(saved.maximum_ltv_ratio) if saved else None,
        "RECORDED_MONITORING_REFERENCE" if recorded else "SAVED_LENDING_REFERENCE" if saved else "UNAVAILABLE",
        identity, policy_error)


def monitoring_inputs_for_policy(loan, *, as_of_date, policy):
    """Read-only proposed-policy inputs; saved numerical references are retained."""
    inputs = resolve_monitoring_valuation_inputs(loan, as_of_date=as_of_date)
    if policy is not None and (policy.workspace_id != loan.workspace_id
            or policy.license_id not in (None, loan.license_id) or policy.scope_action != 'APPLY'):
        raise ValueError("Proposed monitoring policy must apply to this loan's Workspace and licence.")
    basis = policy.valuation_basis if policy else 'ORIGINAL_AGREEMENT'
    selected = inputs.saved_method if basis == 'ORIGINAL_AGREEMENT' else basis
    return replace(inputs, policy=policy, valuation_basis=basis,
        method=ValuationMethod(selected) if selected else None,
        policy_error='' if policy else 'No monitoring policy applies after this change.')
