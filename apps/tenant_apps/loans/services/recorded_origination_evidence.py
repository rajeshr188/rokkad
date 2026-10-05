"""Validate recorded facts against the ordinary immutable disbursal records.

This is a storage boundary, not an admission command. The history-entry command
must additionally authorize, reconcile the entire timeline, reserve numbering
and reject duplicate source loans before activating the aggregate.
"""
from datetime import date
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.tenant_apps.loans.domain.interest import calculate_period_interest


CONTRACT_POLICY_FIELDS = (
    "interest_method", "partial_month_method", "minimum_first_month",
    "partial_month_cutoff_days", "partial_month_lower_fraction",
    "capitalization_interval_periods", "rounding_method", "currency_quantum",
)


def _decimal(value):
    result = Decimal(str(value))
    if not result.is_finite() or result < 0:
        raise ValueError("Recorded amounts must be finite and non-negative.")
    return result


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_recorded_origination(snapshot):
    """No quote lookup, LTV approval or replacement of the agreed cash amount."""
    try:
        _validate(snapshot)
    except (KeyError, TypeError, AttributeError, ValueError, InvalidOperation) as exc:
        raise ValidationError(f"Invalid recorded origination: {exc}") from exc


def _validate(snapshot):
    loan, policy, event = snapshot.loan, snapshot.policy_snapshot, snapshot.loan_event
    _require(snapshot.approval_snapshot_id is None, "A recorded payout cannot claim a digital approval.")
    _require(policy.basis == "RECORDED_CONTRACT", "Recorded contract basis is required.")
    _require(snapshot.created_by_id is not None and snapshot.created_by_id == event.created_by_id,
             "The actual recording user must be retained.")
    recording = snapshot.evidence["recording"]
    _require(recording["schema"] == "recorded-origination/1", "Unsupported evidence version.")
    _require(recording["payout_already_occurred"] is True, "Confirm that the payout already occurred.")
    reference = recording["source_reference"]
    _require(isinstance(reference, str) and 0 < len(reference.strip()) <= 160,
             "A retained paper reference is required.")
    original_actor = recording["original_actor"]
    _require(original_actor is None or isinstance(original_actor, str) and bool(original_actor.strip()),
             "Original actor must be recorded explicitly or left unknown.")
    _require(recording["date_precision"] == "DAY", "This evidence profile uses a date, not an invented time.")
    occurred_on = date.fromisoformat(recording["occurred_on"])
    _require(occurred_on == event.effective_date == loan.loan_date and occurred_on <= timezone.localdate(),
             "Original loan and payout dates must agree and cannot be in the future.")
    _require(event.payload.get("recording") == recording, "Event and snapshot recording evidence must agree.")
    disbursal = event.payload["disbursal"]
    _require(disbursal.get("basis") == "RECORDED" and disbursal.get("approval_snapshot_id") is None
             and disbursal["policy_snapshot_id"] == policy.pk, "Event must identify its recorded contract basis.")

    terms = recording["terms"]
    _require(terms["loan_number"] == loan.loan_number and terms["tenure_months"] == loan.tenure_months,
             "Original number and tenure must agree with the contract.")
    _require(_decimal(terms["principal_amount"]) == loan.principal_amount == snapshot.gross_principal,
             "Original principal must agree with the contract and payout.")
    _require(_decimal(terms["monthly_interest_rate"]) == loan.monthly_interest_rate,
             "Agreed rate must agree with the contract.")
    for field in CONTRACT_POLICY_FIELDS:
        actual = terms["interest_policy"][field]
        expected = getattr(policy, field)
        if isinstance(expected, Decimal):
            actual = _decimal(actual)
        _require(actual == expected, f"Agreed interest rule differs: {field}.")
    monitoring = recording["monitoring"]
    _require(monitoring["valuation_method"] == policy.valuation_method
             and _decimal(monitoring["maximum_ltv_ratio"]) == policy.maximum_ltv_ratio,
             "Current monitoring selection must agree with its saved basis.")
    _require(isinstance(monitoring["reason"], str) and bool(monitoring["reason"].strip()),
             "Explain the monitoring selection separately from the original lending decision.")
    selected_on = date.fromisoformat(monitoring["selected_on"])
    _require(occurred_on <= selected_on <= timezone.localdate(), "Invalid monitoring selection date.")

    _require(policy.interest_method == "SIMPLE" and snapshot.advance_interest_periods in (0, 1),
             "This recorded profile supports simple interest and zero or one advance month.")
    fees = snapshot.evidence["fees"]
    valid_fees = (not fees if not snapshot.deducted_fees else
                  len(fees) == 1 and set(fees[0]) == {"kind", "amount", "deducted"}
                  and fees[0]["kind"] == "DOCUMENT_CHARGE" and fees[0]["deducted"] is True
                  and _decimal(fees[0]["amount"]) == snapshot.deducted_fees)
    _require(valid_fees and disbursal["fees"] == fees,
             "Only an identified, fully deducted document charge is supported.")
    funding = recording.get("funding")
    if funding:
        _require(funding["basis"] in ("CASH", "PROCEEDS")
                 and _decimal(funding["proceeds_after_deductions"]) == snapshot.net_disbursed
                 and _decimal(funding["document_charge"]) == snapshot.deducted_fees,
                 "Paper proceeds and deductions must match the saved contract.")
        _require(funding["actual_cash_paid"] is None if funding["basis"] == "PROCEEDS"
                 else _decimal(funding["actual_cash_paid"]) == snapshot.net_disbursed,
                 "Unknown physical cash must remain unknown.")
    quantum = policy.currency_quantum.normalize()
    from apps.tenant_apps.loans.domain.monthly_contract import RECORDED_PROFILE, POLICY_VERSION
    corrected = recording.get("collection_profile") == RECORDED_PROFILE
    _require((quantum in (Decimal("0.01"), Decimal("1")) and policy.policy_version == POLICY_VERSION)
             if corrected else quantum == Decimal("0.01"), "Unsupported captured rounding policy.")
    tranches = snapshot.evidence["tranches"]
    _require(disbursal["tranches"] == tranches, "Event and snapshot allocations must agree.")
    items = {item.pk: item for item in loan.collateral_items.all()}
    frozen = {row["item_id"]: row for row in terms["collateral"]}
    ids = [row["collateral_item_id"] for row in tranches]
    _require(bool(items) and len(ids) == len(set(ids)) and set(ids) == set(items) == set(frozen)
             and len(frozen) == len(terms["collateral"]), "Collateral membership must match exactly.")
    principal_total = monthly_total = advance_total = Decimal("0")
    for row in tranches:
        item = items[row["collateral_item_id"]]
        principal, rate = _decimal(row["allocated_principal"]), _decimal(row["monthly_interest_rate"])
        _require(principal == item.allocated_principal and rate == item.monthly_interest_rate,
                 "Agreed item principal and rate must match their allocations.")
        _require(principal == principal.quantize(Decimal("0.01")), "Principal exceeds currency precision.")
        _, monthly = calculate_period_interest(calculation_base=principal, monthly_interest_rate=rate,
                                               period_fraction=1, currency_quantum=quantum)
        advance = monthly * snapshot.advance_interest_periods
        _require(_decimal(row["monthly_interest"]) == monthly and _decimal(row["advance_interest"]) == advance,
                 "Recorded interest must reconcile under the agreed rules.")
        original = frozen[item.pk]
        _require(_decimal(original["monthly_interest_rate"]) == rate,
                 "Original collateral terms must retain the agreed item rate.")
        for field in ("description", "metal", "quantity", "gross_weight", "net_weight", "purity_percentage"):
            value, expected = original[field], getattr(item, field)
            if isinstance(expected, Decimal):
                value = _decimal(value)
            _require(value == expected, f"Recorded collateral differs: {field}.")
        principal_total += principal
        monthly_total += monthly
        advance_total += advance
    _require((principal_total, monthly_total, advance_total) ==
             (snapshot.gross_principal, snapshot.monthly_interest, snapshot.advance_interest),
             "Payout allocations must reconcile to the saved totals.")
    values = event.payload["values"]
    for key, expected in (("principal", snapshot.gross_principal), ("advance_interest", snapshot.advance_interest),
                          ("fees", snapshot.deducted_fees), ("net_cash", snapshot.net_disbursed)):
        _require(_decimal(values[key]) == expected, f"Posted payout differs: {key}.")
