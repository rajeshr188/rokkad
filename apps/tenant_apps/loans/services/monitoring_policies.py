from django.db import transaction
from django.db.models import Max
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.orgs.models import Company

from .action_access import require_setup_administration
from apps.tenant_apps.loans.models import LoanMonitoringPolicy


@transaction.atomic
def create_loan_monitoring_policy(*, workspace, actor=None, **values):
    """Create the next immutable version for a workspace/license scope."""
    # Serialize even the first policy in a scope; an empty row set cannot lock.
    workspace = Company.all_objects.select_for_update().get(pk=workspace.pk)
    if workspace.lifecycle_state != Company.LifecycleState.ACTIVE:
        raise ValidationError("Monitoring setup requires an ACTIVE Workspace.")
    require_setup_administration(workspace.pk, actor)

    license = values.get("license")
    if license is not None and license.workspace_id != workspace.pk:
        raise ValueError("Monitoring-policy license must belong to the workspace.")
    scope = LoanMonitoringPolicy.objects.select_for_update(of=("self",)).filter(
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
    version = (scope.aggregate(value=Max("version"))["value"] or 0) + 1
    policy = LoanMonitoringPolicy(
        workspace=workspace,
        version=version,
        created_by=actor,
        eligible_custody_states=predecessor.eligible_custody_states if predecessor else ["IN_VAULT", "WITH_FUNDING_LENDER"],
        severity_mapping=predecessor.severity_mapping if predecessor else {"strategy": "derived-v1"},
        **values,
    )
    policy.save()
    return policy


__all__ = ["create_loan_monitoring_policy"]
