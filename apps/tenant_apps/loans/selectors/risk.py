from datetime import date
from decimal import Decimal

from apps.tenant_apps.loans.domain import RiskPolicy, assess_pawn_loan_risk
from apps.tenant_apps.loans.models import PawnLoan, current_tenant_workspace_id
from .collateral_valuation import get_pawn_loan_collateral_valuation
from .delinquency import get_pawn_loan_delinquency
from .balances import get_pawn_loan_balance
from .obligation_state import get_active_repayment_schedule_as_of


from .monitoring_policy import LoanRiskAssessmentError, resolve_monitoring_policy


def get_pawn_loan_risk_assessment(loan_id: int, *, as_of_date: date, _delinquency=None, _collateral=None):
    """Private prepared inputs are reused only within one source-checked refresh."""
    workspace_id = current_tenant_workspace_id()
    try:
        loan = PawnLoan.objects.get(pk=loan_id, workspace_id=workspace_id)
    except PawnLoan.DoesNotExist as exc:
        raise LoanRiskAssessmentError("PawnLoan was not found in the active workspace.") from exc
    for prepared in (_delinquency, _collateral):
        if prepared is not None and (prepared.loan_id != loan.pk or prepared.as_of_date != as_of_date):
            raise LoanRiskAssessmentError("Prepared assessment must match the scoped loan and date.")
    model = resolve_monitoring_policy(workspace_id=workspace_id, license_id=loan.license_id, as_of_date=as_of_date)
    policy = RiskPolicy(
        identity=f"monitoring-policy:{model.pk}:v{model.version}:{model.compliance_profile}",
        maturity_warning_days=model.maturity_warning_days,
        dpd_watch_threshold=model.dpd_watch_threshold,
        dpd_substandard_threshold=model.dpd_substandard_threshold,
        ltv_warning_ratio=Decimal(model.ltv_warning_ratio),
        ltv_breach_ratio=Decimal(model.ltv_breach_ratio),
        ltv_critical_ratio=Decimal(model.ltv_critical_ratio),
    )
    delinquency = _delinquency if _delinquency is not None else get_pawn_loan_delinquency(loan.pk, as_of_date=as_of_date)
    collateral = _collateral if _collateral is not None else get_pawn_loan_collateral_valuation(loan.pk, as_of_date=as_of_date)
    schedule = get_active_repayment_schedule_as_of(loan, as_of_date)
    maturity_date = (
        schedule.maturity_date
        if schedule is not None
        else get_pawn_loan_balance(loan, as_of_date=as_of_date).due_date
    )
    return assess_pawn_loan_risk(
        as_of_date=as_of_date,
        maturity_date=maturity_date,
        days_past_due=delinquency.assessment.days_past_due,
        ltv_ratio=collateral.ltv.ltv_ratio,
        valuation_blockers=collateral.ltv.blockers,
        overdue_interpretation_variance=delinquency.overdue_variance,
        policy=policy,
    )
