from django.db import transaction
from django.db.models import Max
from django.db.models import Q
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.orgs.models import Company

from .action_access import require_setup_administration
from apps.tenant_apps.loans.models import LoanMonitoringPolicy, current_tenant_workspace_id


@transaction.atomic
def create_loan_monitoring_policy(*, workspace, actor=None, **values):
    """Create the next immutable version for a workspace/license scope."""
    policy = _candidate(workspace=workspace, actor=actor, values=values, lock=True)
    policy.save()
    return policy


def _candidate(*, workspace, actor, values, lock=False):
    """Shared validation for read-only preview and the serialized writer."""
    values = dict(values)
    if values.pop('cancel_scheduled', False):
        raise ValidationError('Preview the cancellation through its reviewed setup action.')
    # Serialize even the first policy in a scope; an empty row set cannot lock.
    # Serialize setup writers without blocking KEY SHARE checks on new risk
    # evidence. A stronger parent lock can deadlock with scope invalidation
    # while a worker owns the snapshot. The database guard uses the same mode.
    companies = Company.all_objects.select_for_update(no_key=True) if lock else Company.all_objects
    workspace = companies.get(pk=workspace.pk)
    if workspace.lifecycle_state != Company.LifecycleState.ACTIVE:
        raise ValidationError("Monitoring setup requires an ACTIVE Workspace.")
    require_setup_administration(workspace.pk, actor)

    license = values.get("license")
    if license is not None and license.workspace_id != workspace.pk:
        raise ValueError("Monitoring-policy license must belong to the workspace.")
    policies = LoanMonitoringPolicy.objects.select_for_update(of=("self",)) if lock else LoanMonitoringPolicy.objects
    scope = policies.filter(
        workspace=workspace, license=license
    )
    predecessor = values.get("supersedes")
    if predecessor is not None:
        predecessor = scope.filter(pk=predecessor.pk, successor__isnull=True).first()
        if predecessor is None:
            raise ValidationError("This policy has already changed. Reload and review its latest version.")
        if values["effective_from"] < timezone.localdate():
            raise ValidationError("Monitoring amendments cannot be backdated.")
        values["supersedes"] = predecessor
        replacing = values.get("replaces_scheduled", False)
        if type(replacing) is not bool:
            raise ValidationError("Choose whether to replace the scheduled changes.")
        if values["effective_from"] < predecessor.effective_from and not replacing:
            raise ValidationError("A future change is scheduled. Explicitly replace or cancel it before applying an earlier change.")
        if replacing and values["effective_from"] > predecessor.effective_from:
            raise ValidationError("There is no later scheduled change to replace from this date.")
        values.setdefault("scope_action", predecessor.scope_action)
        if values.get("scope_action") == LoanMonitoringPolicy.ScopeAction.RETIRE and license is None:
            active = scope.filter(effective_from__lte=values["effective_from"]).order_by("-version").first()
            if not replacing or (active and active.scope_action == LoanMonitoringPolicy.ScopeAction.APPLY):
                raise ValidationError("Only a licence override can be retired. A Workspace's first future setup can be cancelled.")
        # Older callers that do not expose these settings must retain them.
        values.setdefault("valuation_basis", predecessor.valuation_basis)
        values.setdefault("operational_grace_days", predecessor.operational_grace_days)
    version = (scope.aggregate(value=Max("version"))["value"] or 0) + 1
    policy = LoanMonitoringPolicy(
        workspace=workspace,
        version=version,
        created_by=actor,
        eligible_custody_states=values.pop("eligible_custody_states", predecessor.eligible_custody_states if predecessor else ["IN_VAULT", "WITH_FUNDING_LENDER"]),
        severity_mapping=values.pop("severity_mapping", predecessor.severity_mapping if predecessor else {"strategy": "derived-v1"}),
        **values,
    )
    policy.full_clean()
    return policy


POLICY_SETTINGS = ("compliance_profile", "valuation_basis", "maturity_warning_days",
    "operational_grace_days", "dpd_watch_threshold", "dpd_substandard_threshold",
    "ltv_warning_ratio", "ltv_breach_ratio", "ltv_critical_ratio", "rate_freshness_days",
    "appraisal_freshness_days", "scope_action", "eligible_custody_states", "severity_mapping")


def cancellation_values(policy, *, as_of_date=None):
    """Values for a reviewed cancellation; commit still locks/rechecks lineage."""
    if current_tenant_workspace_id() != policy.workspace_id:
        raise ValidationError("Select the policy's Workspace before reviewing its schedule.")
    day = as_of_date or timezone.localdate()
    if policy.effective_from <= day:
        raise ValidationError("This policy has already started; amend it instead.")
    current = LoanMonitoringPolicy.objects.filter(workspace_id=policy.workspace_id,
        license_id=policy.license_id, effective_from__lte=day).filter(
            Q(effective_until__isnull=True) | Q(effective_until__gte=day)).order_by("-version").first()
    source = current or policy
    return dict({name: getattr(source, name) for name in POLICY_SETTINGS},
        license=policy.license, supersedes=policy, effective_from=day, replaces_scheduled=True,
        scope_action=current.scope_action if current else LoanMonitoringPolicy.ScopeAction.RETIRE)


__all__ = ["create_loan_monitoring_policy", "cancellation_values"]
