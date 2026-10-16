"""Source-bound monitoring setup review; previews create no business evidence."""
from collections import Counter
import hashlib
import json

from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.tenant_apps.loans import models as m
from apps.tenant_apps.rates.models import Rate
from apps.tenant_apps.rates.facade import get_latest_commodity_valuation_rate
from apps.tenant_apps.loans.domain.valuation_freshness import evidence_freshness
from apps.tenant_apps.loans.selectors.monitoring_policy import resolve_monitoring_policy, LoanRiskAssessmentError
from apps.tenant_apps.loans.selectors.monitoring_inputs import monitoring_inputs_for_policy
from apps.tenant_apps.loans.selectors.collateral_valuation import get_pawn_loan_collateral_observation
from .monitoring_policies import _candidate, create_loan_monitoring_policy, POLICY_SETTINGS

SALT = 'loans.monitoring-policy-review.v1'
SAMPLE_SIZE = 25


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str, separators=(',', ':')).encode()).hexdigest()


def _setting_label(policy,name):
    if policy is None:
        return 'Not configured'
    display=getattr(policy,f'get_{name}_display',None)
    return display() if display else str(getattr(policy,name))


def _binding(policy, actor):
    """Bind source identities without putting a portfolio in the signed form."""
    workspace_id = policy.workspace_id
    active = m.PawnLoan.objects.filter(workspace_id=workspace_id, state='ACTIVE')
    digest = hashlib.sha256()
    sources = (
        m.LoanMonitoringPolicy.objects.filter(workspace_id=workspace_id),
        active,
        m.LoanPolicySnapshot.objects.filter(workspace_id=workspace_id, loan__in=active),
        m.PawnCollateralItem.objects.filter(workspace_id=workspace_id, loan__in=active),
        m.CollateralAppraisal.objects.filter(workspace_id=workspace_id, collateral_item__loan__in=active),
        m.LoanChangeLog.objects.filter(workspace_id=workspace_id, loan__in=active),
        Rate.objects.filter(workspace_id=workspace_id),
    )
    for queryset in sources:
        digest.update(queryset.model._meta.label.encode())
        for row in queryset.order_by('pk').values().iterator(chunk_size=1000):
            digest.update(_digest(row).encode())
    return dict(actor=actor.pk, workspace=workspace_id, reviewed_on=timezone.localdate().isoformat(),
        values={name:str(getattr(policy,name)) for name in
            (*POLICY_SETTINGS,'license_id','effective_from','effective_until','supersedes_id',
             'amendment_reason','replaces_scheduled','version')}, sources=digest.hexdigest())


def _affected(policy):
    active = m.PawnLoan.objects.filter(workspace_id=policy.workspace_id, state='ACTIVE')
    if policy.license_id is not None:
        return active, active.filter(license_id=policy.license_id)
    inherited = []
    for license_id in active.values_list('license_id',flat=True).distinct():
        try:
            current = resolve_monitoring_policy(workspace_id=policy.workspace_id,
                license_id=license_id, as_of_date=policy.effective_from)
        except LoanRiskAssessmentError:
            current = None
        if current is None or current.license_id is None:
            inherited.append(license_id)
    return active, active.filter(license_id__in=inherited)


def _applied_candidate(policy):
    if policy.scope_action == 'APPLY':
        return policy
    if policy.license_id is None:
        return None
    try:
        return resolve_monitoring_policy(workspace_id=policy.workspace_id,
            license_id=None, as_of_date=policy.effective_from)
    except LoanRiskAssessmentError:
        return None


@transaction.atomic
def preview_monitoring_policy(*, workspace, actor, **values):
    policy = _candidate(workspace=workspace, actor=actor, values=values)
    before = _binding(policy,actor)
    all_active, affected = _affected(policy)
    candidate = _applied_candidate(policy)
    now = timezone.now()
    today = timezone.localdate(now)
    rows, blockers = [], Counter()
    deadlines=[]
    for loan in affected.select_related('policy_snapshot').order_by('pk')[:SAMPLE_SIZE]:
        current = get_pawn_loan_collateral_observation(loan.pk, as_of_date=today, evidence_at=now)
        proposed = get_pawn_loan_collateral_observation(loan.pk, as_of_date=today, evidence_at=now,
            _inputs=monitoring_inputs_for_policy(loan, as_of_date=today, policy=candidate))
        deadlines.extend(value for value in (current.next_evidence_at,proposed.next_evidence_at) if value is not None)
        codes = sorted({code for item in proposed.items for code in item.blockers})
        blockers.update(codes)
        rows.append(dict(number=loan.loan_number, loan_id=loan.pk,
            before_usable=current.eligible_collateral_value is not None,
            after_usable=proposed.eligible_collateral_value is not None,
            blockers=codes))
    quotes = []
    for row in m.PawnCollateralItem.objects.filter(loan__in=affected,
            custody_state__in=('IN_VAULT','WITH_FUNDING_LENDER')).values('metal').annotate(count=Count('pk')).order_by('metal'):
        lookup = get_latest_commodity_valuation_rate(commodity_code=row['metal'], as_of=now)
        at = lookup.rate.effective_at if lookup.rate else None
        status, age = evidence_freshness(value=lookup.rate.buying_rate if lookup.rate else None,
            effective_date=timezone.localdate(at) if at else None, as_of_date=today,
            maximum_age_days=candidate.rate_freshness_days if candidate else None)
        quotes.append(dict(metal=row['metal'], items=row['count'], status=status, age=age))
    try:
        previous=resolve_monitoring_policy(workspace_id=policy.workspace_id,
            license_id=policy.license_id,as_of_date=policy.effective_from)
    except LoanRiskAssessmentError:
        previous=None
    changes = [dict(field=name.replace('_',' ').capitalize(),
        before=_setting_label(previous,name),after=_setting_label(candidate,name))
        for name in POLICY_SETTINGS if name!='scope_action' and
        (previous is None or candidate is None or getattr(previous,name)!=getattr(candidate,name))]
    displaced,preceding = [],[]
    if policy.supersedes_id:
        scope = m.LoanMonitoringPolicy.objects.filter(workspace_id=policy.workspace_id,
            license_id=policy.license_id)
        for row in scope.filter(effective_from__gt=today).order_by('version'):
            winner = scope.filter(effective_from__lte=row.effective_from).order_by('-version').first()
            if winner.pk == row.pk:
                target=displaced if row.effective_from>=policy.effective_from else preceding
                target.append(dict(version=row.version, effective_from=row.effective_from.isoformat()))
    review = dict(scope=str(policy.license) if policy.license_id else 'Workspace default',
        action=policy.get_scope_action_display(), effective_from=policy.effective_from.isoformat(),
        total_active=all_active.count(), affected=affected.count(), changes=changes,
        sample=rows, sample_loses_coverage=sum(row['before_usable'] and not row['after_usable'] for row in rows),
        sample_blockers=dict(blockers), quotes=quotes, displaced=displaced,
        preceding=preceding,
        fallback_unavailable=candidate is None,
        future=policy.effective_from>today)
    after = _binding(policy,actor)
    if before != after:
        raise ValidationError('Policy or portfolio evidence changed during preview. Review again.')
    # Evidence can become applicable without a new save. Include unsampled
    # portfolio metals/appraisals conservatively rather than trusting row IDs alone.
    for queryset in (Rate.objects.filter(workspace_id=workspace.pk,effective_at__gt=now),
            m.CollateralAppraisal.objects.filter(workspace_id=workspace.pk,
                collateral_item__loan__in=all_active,status='APPROVED',effective_at__gt=now)):
        value=queryset.order_by('effective_at').values_list('effective_at',flat=True).first()
        if value is not None:
            deadlines.append(value)
    valid_until=min(deadlines).isoformat() if deadlines else None
    return review, signing.dumps(dict(binding=after, review=review,valid_until=valid_until), salt=SALT, compress=True)


@transaction.atomic
def confirm_monitoring_policy(*, workspace, actor, review_token, acknowledged=False, **values):
    if acknowledged is not True:
        raise ValidationError('Confirm the monitoring policy impact review before saving.')
    try:
        signed = signing.loads(review_token or '', salt=SALT, max_age=3600)
    except signing.BadSignature as exc:
        raise ValidationError('Policy review expired or changed. Preview again.') from exc
    if signed.get('valid_until'):
        deadline=parse_datetime(signed['valid_until'])
        if deadline is None or timezone.is_naive(deadline) or deadline<=timezone.now():
            raise ValidationError('Scheduled evidence became applicable. Preview the policy impact again.')
    policy = _candidate(workspace=workspace, actor=actor, values=values, lock=True)
    if signed.get('binding') != _binding(policy,actor):
        raise ValidationError('Policy, scope or source evidence changed. Preview again.')
    return create_loan_monitoring_policy(workspace=workspace, actor=actor, **values)
