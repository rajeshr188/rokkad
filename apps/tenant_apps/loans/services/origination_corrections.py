"""Explicit actual-paper correction of retained, fully reversed native attempts."""
from django.db.models import Q

from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.access import LOANS_ADMIN_ACTION
from .action_access import require_loan_action

PROFILE = "recorded-origination-correction/1"


def reversed_native_attempts(loan):
    """Validate only the bounded graph, never mutate or choose a fallback writer."""
    events = list(loan.loan_events.select_related("reversed_by_event").order_by("pk")[:42])
    payouts = [event for event in events if event.event_kind == "DISBURSAL"]
    reversals = [event for event in events if event.event_kind == "REVERSAL"]
    snapshots = list(loan.disbursal_snapshots.select_related("policy_snapshot"))
    if (not payouts or len(payouts) > 20 or len(events) != 2 * len(payouts)
            or len(reversals) != len(payouts)
            or {event.reversal_of_id for event in reversals} != {event.pk for event in payouts}
            or {snapshot.loan_event_id for snapshot in snapshots} != {event.pk for event in payouts}
            or len(snapshots) != len(payouts)
            or any(snapshot.basis != "APPROVED" or snapshot.policy_snapshot.basis != "ORIGINATION"
                   for snapshot in snapshots)):
        raise ValueError("This correction requires only fully reversed native payouts and their retained approved snapshots.")
    pairs = []
    for payout in payouts:
        reversal = next(event for event in reversals if event.reversal_of_id == payout.pk)
        # This first profile preserves the effective-date fold without suppressing
        # debt from attempts that were outstanding across different business days.
        if payout.effective_date != reversal.effective_date:
            raise ValueError("A payout reversed on a different date needs a broader history correction.")
        if (reversal.payload.get("values") != payout.payload.get("values")
                or reversal.pk <= payout.pk or payout.effective_date < loan.loan_date):
            raise ValueError("Retained payout/reversal dates or amounts do not reconcile.")
        pairs.append(dict(payout_id=payout.pk, reversal_id=reversal.pk,
            date=payout.effective_date.isoformat(), payout_sha256=payout.payload_fingerprint,
            reversal_sha256=reversal.payload_fingerprint))
    return pairs


def correction_source(loan, *, actor):
    require_loan_action(loan, actor, LOANS_ADMIN_ACTION, "data.edit", "loan.disburse")
    if loan.state != "DRAFT":
        raise ValueError("Reopen the fully reversed loan as a draft before reviewing its actual paper origination.")
    attempts = reversed_native_attempts(loan)
    if (loan.collateral_items.exclude(custody_state="IN_VAULT").exists()
            or loan.collateral_items.filter(renewed_from__isnull=False).exists()
            or m.PawnCollateralCustodyEvent.objects.filter(collateral_item__loan=loan).exists()
            or m.PawnLoanRenewal.objects.filter(Q(source_loan=loan) | Q(successor_loan=loan)).exists()
            or m.FundingLoanDraftCollateral.objects.filter(collateral_item__loan=loan).exists()
            or m.FundingPledgeItem.objects.filter(collateral_item__loan=loan).exists()
            or loan.interest_accruals.exists()):
        raise ValueError("Review servicing and collateral dependencies before correcting origination.")
    return attempts


def retained_attempt_event_ids(loan):
    """Validated, neutral retained attempts are evidence, not later servicing."""
    snapshot = loan.disbursal_snapshot
    if snapshot is None:
        return ()
    validate_correction_evidence(snapshot)
    evidence = snapshot.evidence.get("recording", {}).get("origination_correction")
    if evidence is None:
        return ()
    return tuple(ident for row in evidence["attempts"] for ident in (row["payout_id"], row["reversal_id"]))


def validate_correction_evidence(snapshot):
    recording = snapshot.evidence.get("recording", {})
    if not isinstance(recording, dict):
        raise ValueError("Recorded origination evidence is malformed.")
    evidence = recording.get("origination_correction")
    if evidence is None:
        return
    if (not isinstance(evidence, dict) or set(evidence) != {"profile", "reason", "attempts"}
            or evidence.get("profile") != PROFILE or snapshot.basis != "RECORDED"
            or not isinstance(evidence.get("reason"), str) or not evidence["reason"].strip()
            or len(evidence["reason"]) > 500):
        raise ValueError("Actual-paper origination correction requires its supported evidence and reason.")
    # Later legitimate servicing is outside the retained attempt set. Validate
    # each referenced pair directly rather than treating it as another origin.
    attempts = evidence.get("attempts")
    fields = {"payout_id", "reversal_id", "date", "payout_sha256", "reversal_sha256"}
    if (not isinstance(attempts, list) or not 1 <= len(attempts) <= 20
            or any(not isinstance(row, dict) or set(row) != fields
                   or any(type(row[name]) is not int or row[name] <= 0 for name in ("payout_id", "reversal_id"))
                   or any(not isinstance(row[name], str) for name in ("date", "payout_sha256", "reversal_sha256"))
                   for row in attempts)):
        raise ValueError("Correction must identify its supported retained attempts.")
    expected_ids = [ident for row in attempts
                    for ident in (row["payout_id"], row["reversal_id"])]
    if not expected_ids or len(expected_ids) != len(set(expected_ids)):
        raise ValueError("Correction must identify its distinct retained attempts.")
    events = {event.pk: event for event in snapshot.loan.loan_events.filter(pk__in=expected_ids)}
    native_ids = set(snapshot.loan.disbursal_snapshots.filter(basis="APPROVED",
        loan_event_id__lt=snapshot.loan_event_id).values_list("loan_event_id", flat=True))
    if native_ids != {row["payout_id"] for row in attempts}:
        raise ValueError("Correction must retain every earlier native payout attempt.")
    for row in evidence["attempts"]:
        payout, reversal = events.get(row["payout_id"]), events.get(row["reversal_id"])
        if (payout is None or reversal is None or payout.event_kind != "DISBURSAL"
                or reversal.event_kind != "REVERSAL" or reversal.reversal_of_id != payout.pk
                or payout.effective_date != reversal.effective_date
                or payout.effective_date.isoformat() != row["date"]
                or payout.payload_fingerprint != row["payout_sha256"]
                or reversal.payload_fingerprint != row["reversal_sha256"]
                or payout.payload.get("values") != reversal.payload.get("values")
                or payout.effective_date < snapshot.loan_event.effective_date
                or reversal.pk <= payout.pk
                or reversal.pk >= snapshot.loan_event_id
                or not snapshot.loan.disbursal_snapshots.filter(loan_event=payout,
                    basis="APPROVED", policy_snapshot__basis="ORIGINATION").exists()):
            raise ValueError("Origination correction differs from its retained native payout/reversal evidence.")
