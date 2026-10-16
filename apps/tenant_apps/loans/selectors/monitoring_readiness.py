"""Active-portfolio monitoring readiness, separate from permission to lend."""
import os

from django.db.models import Count, Max, Min, Q
from django.utils import timezone

from apps.tenant_apps.loans import models as m
from apps.tenant_apps.rates.facade import get_latest_commodity_valuation_rate
from apps.tenant_apps.loans.domain.valuation_freshness import evidence_freshness
from .monitoring_policy import resolve_monitoring_policy, LoanRiskAssessmentError
from .risk_portfolio import current_snapshot_filter, get_risk_portfolio_summary


def configured_worker_assignment(workspace_id, environ=None):
    """Configuration visibility is not a worker heartbeat or proof of liveness."""
    environ = os.environ if environ is None else environ
    raw = environ.get('ROKKAD_MONITOR_WORKSPACE_IDS', environ.get('ROKKAD_MONITOR_WORKSPACE_ID'))
    if raw is None:
        return 'UNVERIFIED'
    try:
        ids = tuple(int(value) for value in raw.split())
        if not ids or any(value < 1 for value in ids):
            return 'INVALID'
    except (ValueError, TypeError):
        return 'INVALID'
    return 'CONFIGURED' if workspace_id in ids else 'NOT_LISTED'


def get_monitoring_readiness(*, workspace, environ=None):
    if m.current_tenant_workspace_id() != workspace.pk:
        raise ValueError("Monitoring readiness requires the active Workspace.")
    now, today = timezone.now(), timezone.localdate()
    active = m.PawnLoan.objects.filter(workspace_id=workspace.pk, state='ACTIVE')
    summary = get_risk_portfolio_summary(as_of_date=today)
    scope_rows = []
    licenses = {row.pk:row for row in m.LoanLicense.objects.filter(workspace_id=workspace.pk,
        pk__in=active.values('license_id'))}
    quotes = {}
    for group in active.values('license_id').annotate(count=Count('pk')).order_by('license_id'):
        license_id = group['license_id']
        try:
            policy = resolve_monitoring_policy(workspace_id=workspace.pk,
                license_id=license_id, as_of_date=today)
            error = ''
        except LoanRiskAssessmentError as exc:
            policy, error = None, str(exc)
        methods = ({policy.valuation_basis} if policy and policy.valuation_basis!='ORIGINAL_AGREEMENT'
            else set(active.filter(license_id=license_id).values_list('policy_snapshot__valuation_method',flat=True)))
        needs_rate = any(method != 'LATEST_APPRAISAL' for method in methods)
        needs_appraisal = any(method != 'CALCULATED_METAL_VALUE' for method in methods)
        metal_rows = []
        metals = m.PawnCollateralItem.objects.filter(workspace_id=workspace.pk,
            loan__in=active.filter(license_id=license_id),
            custody_state__in=('IN_VAULT','WITH_FUNDING_LENDER')).values('metal').annotate(count=Count('pk')).order_by('metal')
        for metal in metals:
            if metal['metal'] not in quotes:
                quotes[metal['metal']] = get_latest_commodity_valuation_rate(commodity_code=metal['metal'],as_of=now)
            lookup = quotes[metal['metal']]
            at = lookup.rate.effective_at if lookup.rate else None
            status, age = evidence_freshness(value=lookup.rate.buying_rate if lookup.rate else None,
                effective_date=timezone.localdate(at) if at else None, as_of_date=today,
                maximum_age_days=policy.rate_freshness_days if policy else None)
            metal_rows.append(dict(metal=metal['metal'], items=metal['count'], price_status=status,
                price_age=age, price_required=needs_rate))
        scope_rows.append(dict(license=licenses.get(license_id), loans=group['count'],
            policy=policy, error=error, metals=metal_rows, appraisal_required=needs_appraisal))
    current_ids = m.LoanRiskSnapshot.objects.filter(current_snapshot_filter(today),
        workspace_id=workspace.pk).values('loan_id')
    pending = active.exclude(pk__in=current_ids)
    attempts = m.LoanRiskSnapshot.objects.filter(workspace_id=workspace.pk,loan__in=active).aggregate(
        last_attempt=Max('assessed_at'),
        last_success=Max('assessed_at',filter=~Q(status='ERROR')))
    return dict(summary=summary, scopes=scope_rows, assignment=configured_worker_assignment(workspace.pk,environ),
        pending_count=pending.count(),
        oldest_pending_assessment=pending.aggregate(value=Min('risk_snapshot__assessed_at'))['value'],
        oldest_unassessed_loan=active.filter(risk_snapshot__isnull=True).aggregate(value=Min('created_at'))['value'],
        **attempts)
