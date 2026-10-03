"""Current financial presentation of immutable release/renewal documents.

Document identities, agreements and custody evidence remain original. Only an
explicit canonical settlement correction supplies revised financial particulars.
Returned copies are read projections; the immutable model save guards still apply.
"""
from copy import copy, deepcopy
from decimal import Decimal

from apps.tenant_apps.loans.models import PawnLoanEvent


def current_settlement(event):
    if not getattr(event, "pk", None) or not getattr(event, "loan_id", None):
        return event
    root = event.payload.get("history_correction", {}).get("root_event_id") or event.pk
    replacement = PawnLoanEvent.objects.filter(
        loan_id=event.loan_id, event_kind=event.event_kind, reversed_by_event__isnull=True,
        payload__history_correction__schema="recorded-history-correction/1",
        payload__history_correction__role="SETTLEMENT",
        payload__history_correction__root_event_id=root,
    ).first()
    return replacement or event


def correction_label(event):
    evidence = getattr(event, "payload", {}).get("history_correction", {})
    if evidence.get("role") != "SETTLEMENT":
        return ""
    batch = evidence.get("batch_correction")
    batch_label = f"batch #{batch['id']}, source {batch['reference']}; " if batch else ""
    return (f"Historical settlement correction; original event #{evidence['root_event_id']}; "
            f"recorded {event.created_at.isoformat()}; source {evidence['settlement_reference']}; "
            f"{batch_label}"
            "no new cash or collateral movement")


def restated_release(release):
    if not getattr(release, "loan_event", None):
        return release
    event = current_settlement(release.loan_event)
    if event is release.loan_event or event.pk == release.loan_event_id:
        return release
    result = copy(release)
    result.loan_event = event
    result.effective_date = event.effective_date
    for field, key in (("principal_amount", "principal"), ("interest_amount", "interest"), ("fee_amount", "fees")):
        setattr(result, field, Decimal(event.payload["values"][key]))
    result.settlement_amount = result.principal_amount + result.interest_amount + result.fee_amount
    result.correction_status = correction_label(event)
    return result


def restated_renewal(renewal):
    if not getattr(renewal, "settlement_event", None):
        return renewal
    event = current_settlement(renewal.settlement_event)
    if event is renewal.settlement_event or event.pk == renewal.settlement_event_id:
        return renewal
    result = copy(renewal)
    result.settlement_event = event
    result.renewal_date = event.effective_date
    opening = renewal.successor_loan.loan_events.filter(event_kind="RENEWAL_OPENING", reversed_by_event__isnull=True).order_by("-pk").first()
    if opening:
        result.opening_event = opening
    cash = event.payload["renewal"]["cash_evidence"]
    for field, key in (("source_principal_amount", "source_principal"), ("interest_settled", "interest_settled"),
                       ("principal_paid", "principal_paid"), ("top_up_amount", "gross_advance"),
                       ("successor_principal_amount", "successor_principal"),
                       ("successor_advance_interest", "new_advance_interest"), ("successor_deducted_fees", "new_document_charge")):
        if key not in cash:
            continue
        setattr(result, field, Decimal(cash[key]))
    result.valuation_snapshot = deepcopy(renewal.valuation_snapshot)
    result.valuation_snapshot.update(cash_evidence=cash, principal_carried=cash["principal_carried"],
        net_cash_received=str(Decimal(cash["cash_received"]) - Decimal(cash["cash_paid"])))
    result.correction_status = correction_label(event)
    return result


def opening_cash(event):
    """The unchanged successor opening links to the corrected funding settlement."""
    original = event.payload.get("recording", {}).get("cash_evidence")
    source_id = event.payload.get("renewal", {}).get("settlement_event_id")
    if not original or not source_id:
        return original, ""
    source = PawnLoanEvent.objects.get(pk=source_id, loan__workspace_id=event.loan.workspace_id)
    current = current_settlement(source)
    return current.payload.get("renewal", {}).get("cash_evidence", original), correction_label(current)
