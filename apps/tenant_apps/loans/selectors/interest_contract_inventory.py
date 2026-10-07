"""Read-only rollout inventory; it never adopts a contract or corrects a loan."""
from datetime import date
from django.utils import timezone
from apps.tenant_apps.loans.models import PawnLoan, LoanDocumentIssue, current_tenant_workspace_id
from .servicing_contract import resolve_servicing_contract, ServicingContractError
from .continuation import resolve_loan_continuation


def interest_contract_inventory(*, as_of_date=None):
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise ValueError("Interest contract inventory requires an active Workspace context.")
    as_of_date = timezone.localdate() if as_of_date is None else as_of_date
    if type(as_of_date) is not date:
        raise ValueError("Interest contract inventory requires a reporting date.")
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
        shared = (profile in ("loan-opening-review/3", "loan-opening-review/4", "loan-opening-review/5") if origin and origin.event_kind == "MIGRATION_OPENING"
                  else profile == "recorded-anniversary/3" if policy and policy.basis == "RECORDED_CONTRACT"
                  else bool(policy and policy.policy_version == 2))
        terminal = profile == "loan-terminal-review/1"
        financial = [event for event in events if event.event_kind not in ("DISBURSAL", "RENEWAL_OPENING", "MIGRATION_OPENING")]
        blocker, contract = None, None
        if origin:
            try:
                contract = resolve_servicing_contract(loan, as_of_date=max(loan.loan_date, origin.effective_date))
            except (ServicingContractError, ValueError) as exc:
                blocker = str(exc)
        status = ("INVALID_ORIGIN" if origin is None else "INVALID_CONTRACT" if blocker else
            "VERIFIED_TERMINAL_POSITION" if terminal else "SHARED_CONTRACT" if shared else "REVIEW_CORRECTION")
        continuation_status, continuation_blocker = "NOT_ACTIVE", None
        if loan.state == "ACTIVE":
            continuation_status = "SUPPORTED"
            try:
                resolve_loan_continuation(loan, as_of_date=as_of_date)
            except ValueError as exc:
                continuation_status, continuation_blocker = "HELD", str(exc)
        # Contract compatibility is not current posting readiness. In particular,
        # a retained reversed native charge must not appear ready for collection.
        disposition = ("HOLD_AND_REVIEW" if blocker or origin is None or continuation_status == "HELD" else
            "PRESERVE_TERMINAL_POSITION" if terminal else "CONTINUE_CAPTURED_CONTRACT" if shared else
            "KEEP_FROZEN_TERMS_OR_EXPLICITLY_CORRECT")
        quantum = contract.currency_quantum if contract else getattr(policy, "currency_quantum", None)
        rows.append(dict(loan_id=loan.pk, number=loan.loan_number, state=loan.state,
            profile=profile or (f"native-policy/{policy.policy_version}" if policy else "MISSING"),
            status=status, as_of_date=as_of_date.isoformat(),
            blocker=blocker,
            continuation_status=continuation_status, continuation_blocker=continuation_blocker,
            disposition=disposition,
            anniversary_rule=contract.anniversary_rule if contract else None,
            principal_reduction_rule=contract.principal_reduction_rule if contract else None,
            rounding_scope=contract.rounding_scope if contract else None,
            rounding_mode=contract.rounding_mode if contract else None,
            currency_quantum=str(quantum.normalize()) if quantum is not None else None,
            policy_currency_quantum=str(policy.currency_quantum.normalize()) if policy else None,
            origin_event_id=origin.pk if origin else None, servicing_events=len(financial),
            saved_accruals=loan.interest_accruals.count(), issued_documents=LoanDocumentIssue.objects.filter(
                workspace_id=workspace_id, source_type="PawnLoan", source_id=str(loan.pk)).count(),
            correction="EARLIER_HISTORY_UNAVAILABLE" if terminal else "REVIEW_DEPENDENCIES_AND_COMPENSATION" if financial else "REVIEW_FROZEN_ORIGIN",
            automatic_conversion=False))
    return rows
