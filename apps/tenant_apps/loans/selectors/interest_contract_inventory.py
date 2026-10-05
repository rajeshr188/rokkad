"""Read-only rollout inventory; it never adopts a contract or corrects a loan."""
from apps.tenant_apps.loans.models import PawnLoan, LoanDocumentIssue, current_tenant_workspace_id
from .servicing_contract import resolve_servicing_contract, ServicingContractError


def interest_contract_inventory():
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise ValueError("Interest contract inventory requires an active Workspace context.")
    rows = []
    for loan in PawnLoan.objects.filter(workspace_id=workspace_id, state__in=("ACTIVE", "CLOSED")).select_related("policy_snapshot").order_by("pk"):
        events = list(loan.loan_events.order_by("effective_date", "pk"))
        reversed_ids = {event.reversal_of_id for event in events if event.event_kind == "REVERSAL"}
        origins = [event for event in events if event.event_kind in ("DISBURSAL", "RENEWAL_OPENING", "MIGRATION_OPENING") and event.pk not in reversed_ids]
        origin = origins[0] if len(origins) == 1 else None
        policy = loan.policy_snapshot
        recording = origin.payload.get("recording", {}) if origin else {}
        profile = (origin.payload.get("opening", {}).get("review", {}).get("profile")
                   if origin and origin.event_kind == "MIGRATION_OPENING" else recording.get("collection_profile"))
        shared = (profile == "loan-opening-review/3" if origin and origin.event_kind == "MIGRATION_OPENING"
                  else profile == "recorded-anniversary/3" if policy and policy.basis == "RECORDED_CONTRACT"
                  else bool(policy and policy.policy_version == 2))
        financial = [event for event in events if event.event_kind not in ("DISBURSAL", "RENEWAL_OPENING", "MIGRATION_OPENING")]
        blocker = None
        if origin:
            try:
                resolve_servicing_contract(loan, as_of_date=max(loan.loan_date, origin.effective_date))
            except (ServicingContractError, ValueError) as exc:
                blocker = str(exc)
        rows.append(dict(loan_id=loan.pk, number=loan.loan_number, state=loan.state,
            profile=profile or (f"native-policy/{policy.policy_version}" if policy else "MISSING"),
            status="INVALID_ORIGIN" if origin is None else "INVALID_CONTRACT" if blocker else "SHARED_CONTRACT" if shared else "REVIEW_CORRECTION",
            blocker=blocker,
            currency_quantum=str(policy.currency_quantum.normalize()) if policy else None,
            origin_event_id=origin.pk if origin else None, servicing_events=len(financial),
            saved_accruals=loan.interest_accruals.count(), issued_documents=LoanDocumentIssue.objects.filter(
                workspace_id=workspace_id, source_type="PawnLoan", source_id=str(loan.pk)).count(),
            correction="REVIEW_DEPENDENCIES_AND_COMPENSATION" if financial else "REVIEW_FROZEN_ORIGIN",
            automatic_conversion=False))
    return rows
