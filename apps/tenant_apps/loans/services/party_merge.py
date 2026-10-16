"""Consolidate duplicate borrower identities without replaying financial actions."""
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.orgs.audit import AuditLog
from apps.tenant_apps.loans.models import PawnLoan, KhataAccount, LoanChangeLog
from apps.tenant_apps.party.access import PARTY_ACTION_PERMISSIONS
from apps.tenant_apps.party.services.action_access import require_party_service_permission
from .recorded_history import _digest


@transaction.atomic
def transfer_merged_party_accounts(*, source, target, actor):
    """Caller holds both Party locks and has recorded the archived merge link."""
    require_party_service_permission(target.workspace_id, actor, *PARTY_ACTION_PERMISSIONS["edit"])
    if (source.workspace_id != target.workspace_id or source.status != "ARCHIVED"
            or source.metadata.get("merged_into_party_id") != target.pk
            or target.status == "ARCHIVED" or source.pk not in target.metadata.get("merged_from_party_ids", [])):
        raise ValidationError("Account transfer requires the recorded duplicate merge in this Workspace.")
    loans = list(PawnLoan.objects.select_for_update().filter(
        workspace_id=source.workspace_id, borrower=source).order_by("pk"))
    accounts = list(KhataAccount.objects.select_for_update().filter(
        workspace_id=source.workspace_id, borrower=source).order_by("pk"))
    reason = "Consolidate duplicate Party into its retained identity."
    facts = dict(borrower_id=target.pk, reference=f"Party merge {source.pk} into {target.pk}",
        reason=reason, request_key=f"party-merge:{source.pk}:{target.pk}")
    for loan in loans:
        LoanChangeLog.objects.create(workspace_id=loan.workspace_id, loan=loan,
            event_kind="BORROWER_CORRECTED", from_state=loan.state, to_state=loan.state,
            actor=actor, reason=reason, metadata=dict(borrower_correction=dict(
                schema="recorded-borrower-correction/1", party_merge=True,
                request_key=facts["request_key"], request_sha256=_digest(facts),
                reference=facts["reference"], reason=reason,
                source_fingerprint=_digest(dict(loan=loan.pk, borrower=source.pk,
                    state=loan.state, updated_at=loan.updated_at.isoformat())),
                before=_party_facts(source), after=_party_facts(target), loan_number=loan.loan_number,
                receipt_count=loan.loan_events.filter(event_kind="REPAYMENT").count())))
        # Preserve every other current field, including the original recorder.
        loan.borrower = target
        # Ordinary save keeps the existing monitoring invalidation signal. Limit
        # the write to the borrower so historical/current financial fields stay exact.
        loan.save(update_fields=["borrower"])
    for account in accounts:
        AuditLog.log("DATA_UPDATE", user=actor, company=target.workspace, content_object=account,
            description=reason, data=dict(party_merge=dict(source_id=source.pk,
                target_id=target.pk, khata_account_id=account.pk)))
        KhataAccount.objects.filter(pk=account.pk, workspace_id=account.workspace_id).update(borrower=target)
    if loans or accounts:
        AuditLog.log("DATA_UPDATE", user=actor, company=target.workspace, content_object=target,
            description=reason, data=dict(party_merge=dict(source_id=source.pk, target_id=target.pk,
                loan_ids=[loan.pk for loan in loans], khata_account_ids=[account.pk for account in accounts])))
    return len(loans), len(accounts)


def _party_facts(party):
    return dict(id=party.pk, name=party.display_name, code=party.party_code, status=party.status)
