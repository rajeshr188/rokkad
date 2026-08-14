from django.db import transaction
from django.db.models import Max

from apps.tenant_apps.loans.models import LoanMonitoringPolicy


@transaction.atomic
def create_loan_monitoring_policy(*, workspace, actor=None, **values):
    """Create the next immutable version for a workspace/license scope."""

    license = values.get("license")
    if license is not None and license.workspace_id != workspace.pk:
        raise ValueError("Monitoring-policy license must belong to the workspace.")
    scope = LoanMonitoringPolicy.objects.select_for_update().filter(
        workspace=workspace, license=license
    )
    version = (scope.aggregate(value=Max("version"))["value"] or 0) + 1
    policy = LoanMonitoringPolicy(
        workspace=workspace,
        version=version,
        created_by=actor,
        eligible_custody_states=["IN_VAULT", "WITH_FUNDING_LENDER"],
        severity_mapping={"strategy": "derived-v1"},
        **values,
    )
    policy.save()
    return policy


__all__ = ["create_loan_monitoring_policy"]
