from django.core.exceptions import ValidationError
from django.db import transaction

from .action_access import require_setup_administration
from apps.tenant_apps.loans.models import PawnLoanCommunicationPolicy, current_tenant_workspace_id


class CommunicationPolicyError(ValueError):
    pass


@transaction.atomic
def set_pawn_loan_communication_policy(*, actor=None, **values):
    require_setup_administration(current_tenant_workspace_id(), actor)
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise CommunicationPolicyError("Communication policy requires an active tenant schema.")
    try:
        policy, _ = PawnLoanCommunicationPolicy.objects.select_for_update().get_or_create(
            workspace_id=workspace_id,
            defaults={**values, "updated_by": actor},
        )
        for field, value in values.items():
            setattr(policy, field, value)
        policy.updated_by = actor
        policy.save()
    except ValidationError as exc:
        raise CommunicationPolicyError(" ".join(exc.messages)) from exc
    return policy


def get_pawn_loan_communication_policy():
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise CommunicationPolicyError("Communication policy requires an active tenant schema.")
    return PawnLoanCommunicationPolicy.objects.filter(workspace_id=workspace_id).first()


__all__ = ["CommunicationPolicyError", "get_pawn_loan_communication_policy", "set_pawn_loan_communication_policy"]
