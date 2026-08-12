from datetime import date
from decimal import Decimal

from apps.tenant_apps.loans.domain import RiskPolicy, assess_pawn_loan_risk
from apps.tenant_apps.loans.models import LoanMonitoringPolicy, PawnLoan, current_tenant_workspace_id
from .collateral_valuation import get_pawn_loan_collateral_valuation
from .delinquency import get_pawn_loan_delinquency
from .balances import get_pawn_loan_balance
from .exposure import _active_schedule_as_of


class LoanRiskAssessmentError(ValueError):
    pass


def resolve_monitoring_policy(*, workspace_id, license_id, as_of_date):
    base = LoanMonitoringPolicy.objects.filter(workspace_id=workspace_id, effective_from__lte=as_of_date).filter(effective_until__isnull=True) | LoanMonitoringPolicy.objects.filter(workspace_id=workspace_id, effective_from__lte=as_of_date, effective_until__gte=as_of_date)
    for scope_license in (license_id, None):
        matches = tuple(base.filter(license_id=scope_license).order_by("-effective_from", "-version")[:2])
        if len(matches) > 1 and matches[0].effective_from == matches[1].effective_from:
            raise LoanRiskAssessmentError("Monitoring policy resolution is ambiguous for this date.")
        if matches:
            return matches[0]
    raise LoanRiskAssessmentError("No monitoring policy applies to this loan and date.")


def get_pawn_loan_risk_assessment(loan_id: int, *, as_of_date: date):
    workspace_id = current_tenant_workspace_id()
    try:
        loan = PawnLoan.objects.get(pk=loan_id, workspace_id=workspace_id)
    except PawnLoan.DoesNotExist as exc:
        raise LoanRiskAssessmentError("PawnLoan was not found in the active workspace.") from exc
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
    delinquency = get_pawn_loan_delinquency(loan.pk, as_of_date=as_of_date)
    collateral = get_pawn_loan_collateral_valuation(loan.pk, as_of_date=as_of_date)
    schedule = _active_schedule_as_of(loan, as_of_date)
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
        accounting_variance=delinquency.overdue_variance,
        policy=policy,
    )
