from django.db import transaction
from django.utils import timezone

from apps.tenant_apps.loans.domain import PawnLoanNoticeChannel
from apps.tenant_apps.loans.models import PawnLoanCommunicationConsent, current_tenant_workspace_id
from apps.tenant_apps.party.models import Party


class CommunicationConsentError(ValueError):
    pass


@transaction.atomic
def set_pawn_loan_communication_consent(
    party_id, *, channel, decision, evidence, actor=None
):
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise CommunicationConsentError("Communication consent requires an active tenant schema.")
    try:
        channel = PawnLoanNoticeChannel(channel).value
    except ValueError as exc:
        raise CommunicationConsentError("Unsupported communication channel.") from exc
    if decision not in {"ALLOW", "BLOCK", "OPT_OUT"}:
        raise CommunicationConsentError("Unsupported consent decision.")
    evidence = str(evidence or "").strip()
    if not evidence:
        raise CommunicationConsentError("Consent evidence or reason is required.")
    party = Party.objects.select_for_update().get(pk=party_id)
    consent, _ = PawnLoanCommunicationConsent.objects.update_or_create(
        workspace_id=workspace_id,
        party=party,
        channel=channel,
        defaults={
            "service_notices_allowed": decision == "ALLOW",
            "opted_out_at": timezone.now() if decision == "OPT_OUT" else None,
            "evidence": evidence,
            "updated_by": actor,
        },
    )
    return consent


__all__ = ["CommunicationConsentError", "set_pawn_loan_communication_consent"]
