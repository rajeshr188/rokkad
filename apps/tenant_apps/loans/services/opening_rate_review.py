"""Pure rate-restatement proposal for an unserviced aggregate checkpoint.

No ORM access or write authority. Partial earlier payments require explicit
checkpoint review; a rate change cannot establish a different cash history.
"""

from copy import deepcopy
from datetime import date
from decimal import Decimal

from .legacy_interest import aggregate_collection_interest
from .opening_validation import COLLECTION_PROFILE, validate_opening


def prepare_unpaid_collection_rate_review(review, *, monthly_rate, reference):
    """Restate only when every recognized post-upfront charge remains unpaid.

    The caller separately establishes the original rate/first-month payment,
    exact loan selection, authorization and absence of connected activity.
    This helper does not certify those facts or authorize application.
    """
    if not isinstance(review, dict) or review.get("profile") != COLLECTION_PROFILE:
        raise ValueError(
            "Rate preparation requires its retained aggregate collection checkpoint."
        )
    checked = validate_opening(review)
    if not checked["document_reconciled"]:
        raise ValueError("The retained collection checkpoint does not reconcile.")
    if not isinstance(reference, str) or not reference.strip() or len(reference) > 255:
        raise ValueError("Supply a bounded supporting reference.")
    if not isinstance(monthly_rate, str):
        raise ValueError("Supply the corrected monthly rate as a decimal string.")
    corrected = deepcopy(review)
    carry = corrected["continuation"]
    if Decimal(carry["recognized_interest"]) != Decimal(
        carry["recognized_unpaid_interest"]
    ):
        raise ValueError(
            "Earlier paid or waived interest requires an explicit payment/checkpoint review."
        )
    # No attribution between due rows or unrecognized future charges is inferred.
    interest_rows = [
        row for row in corrected["obligations"] if Decimal(row["interest"]) > 0
    ]
    if len(interest_rows) > 1:
        raise ValueError(
            "Multiple interest obligations require an explicit checkpoint review."
        )
    if any(
        Decimal(row["interest"]) != Decimal(row["recognized_interest"])
        for row in corrected["obligations"]
    ):
        raise ValueError(
            "Future or differently allocated interest requires an explicit checkpoint review."
        )
    for row in corrected["collateral"]:
        row["monthly_rate"] = monthly_rate
    # Validate the new rate before arithmetic (including nonfinite/precision bounds).
    invalid_rate = [
        i
        for i in validate_opening(corrected)["issues"]
        if i["field"].endswith("monthly_rate")
    ]
    if invalid_rate:
        raise ValueError("The corrected monthly rate is outside supported bounds.")
    monthly = sum(
        Decimal(r["original_principal"]) * Decimal(monthly_rate) / 100
        for r in corrected["collateral"]
    )
    calculation = aggregate_collection_interest(
        date.fromisoformat(review["terms"]["original_date"]),
        date.fromisoformat(review["cutover"]["date"]),
        monthly,
    )
    interest = calculation["additional_interest"]
    carry.update(
        recognized_interest=interest,
        recognized_unpaid_interest=interest,
        evidence_reference=reference,
    )
    corrected["balances"].update(interest=interest, evidence_reference=reference)
    if interest_rows:
        # Keep the existing single aggregate-interest due date and identity;
        # separate principal-only rows retain their exact dates and amounts.
        if Decimal(interest) == 0 and Decimal(interest_rows[0]["principal"]) == 0:
            raise ValueError(
                "An empty corrected interest obligation needs an explicit checkpoint review."
            )
        interest_rows[0].update(interest=interest, recognized_interest=interest)
    elif Decimal(interest) != 0:
        raise ValueError(
            "New interest has no retained obligation; review its due date explicitly."
        )
    if not validate_opening(corrected)["document_reconciled"]:
        raise ValueError("The corrected collection checkpoint does not reconcile.")
    return corrected
