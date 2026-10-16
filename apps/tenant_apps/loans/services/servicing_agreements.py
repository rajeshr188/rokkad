"""Source-local checks before remapping retained agreement revisions."""
from decimal import Decimal
from .servicing_bundle_contract import require
from .agreement_corrections import PROFILE
from .recorded_history import _digest


def validate_source_agreements(document):
    tables = document["tables"]
    snapshots = {r["id"]: r for r in tables["PawnLoanDisbursalSnapshot"]}
    events = {r["id"]: r for r in tables["PawnLoanEvent"]}
    policies = {r["id"]: r for r in tables["LoanPolicySnapshot"]}
    loans = {r["id"]: r for r in tables["PawnLoan"]}
    reverse = {r["reversal_of_id"]: r for r in events.values() if r["reversal_of_id"]}
    revisions = set()
    for snapshot in snapshots.values():
        correction = snapshot["evidence"].get("agreement_correction")
        require((snapshot["basis"] == "CORRECTED") == bool(correction), "Agreement correction basis/evidence differs.")
        if not correction:
            continue
        previous = snapshots.get(correction.get("disbursal_snapshot_id"))
        event = events[snapshot["loan_event_id"]]
        revision = correction.get("revision")
        require(previous and previous["loan_id"] == snapshot["loan_id"] and previous["id"] < snapshot["id"],
            "Agreement correction has a foreign or missing retained source.")
        require(correction.get("schema") == PROFILE and correction.get("role") == "AGREEMENT"
            and type(revision) is int and revision == previous["evidence"].get("agreement_correction", {}).get("revision", 1) + 1
            and (snapshot["loan_id"], revision) not in revisions, "Agreement revision chain differs.")
        revisions.add((snapshot["loan_id"], revision))
        require(correction.get("source_event_id") == previous["loan_event_id"]
            and event["payload"].get("agreement_correction") == correction
            and previous["loan_event_id"] in reverse
            and reverse[previous["loan_event_id"]]["payload"].get("agreement_correction", {}).get("request_key") == correction.get("request_key")
            and snapshot["approval_snapshot_id"] == previous["approval_snapshot_id"]
            and policies[snapshot["policy_snapshot_id"]]["basis"] == "ORIGINATION", "Agreement correction source/compensation differs.")
        values = event["payload"]["values"]
        require(all(Decimal(snapshot[field]) == Decimal(values[key]) for field, key in (
            ("gross_principal", "principal"), ("advance_interest", "advance_interest"), ("deducted_fees", "fees"), ("net_disbursed", "net_cash"))),
            "Agreement correction amounts differ from its event.")
        loan = loans[snapshot["loan_id"]]
        if loan["disbursal_snapshot_id"] == snapshot["id"]:
            require(Decimal(loan["principal_amount"]) == Decimal(snapshot["gross_principal"])
                and Decimal(loan["monthly_interest_rate"]) == Decimal(correction["rate"])
                and loan["loan_date"] == correction["original_date"] and loan["policy_snapshot_id"] == snapshot["policy_snapshot_id"],
                "Current agreement differs from its retained correction.")
    for accrual in tables["PawnLoanInterestAccrual"]:
        revision = accrual["agreement_revision"]
        require(type(revision) is int and revision >= 1 and (revision == 1 or (accrual["loan_id"], revision) in revisions),
            "Monthly recognition references an unknown agreement revision.")
    from .opening_corrections import _validate_change
    for loan in loans.values():
        origins = [e for e in events.values() if e["loan_id"] == loan["id"] and e["event_kind"] == "MIGRATION_OPENING"]
        corrections = [e for e in events.values() if e["loan_id"] == loan["id"] and e["event_kind"] == "OPENING_CORRECTION"]
        if not corrections:
            continue
        require(len(origins) == 1, "Checkpoint correction requires one original opening.")
        original = previous = origins[0]
        for revision, event in enumerate(sorted(corrections, key=lambda e: e["id"]), 1):
            evidence = event["payload"].get("agreement_correction", {})
            require(evidence.get("schema") == PROFILE and evidence.get("operation") == "CHECKPOINT"
                and evidence.get("revision") == revision and evidence.get("original_event_id") == original["id"]
                and evidence.get("source_event_id") == previous["id"] and previous["id"] < event["id"]
                and evidence.get("before_sha256") == _digest(previous["payload"]["opening"])
                and evidence.get("before_values") == previous["payload"]["values"]
                and event["effective_date"] == original["effective_date"]
                and event["payload"]["opening"]["item_mapping"] == original["payload"]["opening"]["item_mapping"],
                "Checkpoint correction source chain differs.")
            _validate_change(previous["payload"]["opening"]["review"], event["payload"]["opening"]["review"])
            require(event["payload"]["values"] == {k: event["payload"]["opening"]["review"]["balances"][k] for k in ("principal", "interest", "fees")},
                "Checkpoint correction values differ from its reviewed balances.")
            previous = event
