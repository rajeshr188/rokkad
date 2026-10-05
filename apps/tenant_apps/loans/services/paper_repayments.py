"""Reviewed recording of an already received payment on a supported loan."""

from dataclasses import asdict, dataclass
from datetime import date
import json

from django.core import signing
from django.db import transaction
from django.utils import timezone

from .action_access import require_loan_action
from .pawn_repayment import (
    PawnRepaymentError, PawnRepaymentPreview, _decimal_string, _existing_result,
    _locked_loan, _money_amount, _record_pawn_loan_repayment_at,
    _repayment_preview, _request_key, allocate_repayment,
)


PROFILE = "paper-repayment/1"
SALT = "loans.paper-repayment.review.v1"
MAX_AGE = 3600


@dataclass(frozen=True)
class PaperRepaymentReview:
    preview: PawnRepaymentPreview
    review_token: str


def normalize_item_split(value):
    from decimal import Decimal, InvalidOperation
    if not isinstance(value, dict) or len(value) > 100:
        raise PawnRepaymentError("Enter the principal amount applied to each collateral item.")
    result = {}
    try:
        for key, raw in value.items():
            if not isinstance(key, str) or not key.isdecimal() or int(key) < 1 or str(int(key)) != key:
                raise ValueError
            amount = Decimal(str(raw))
            if not amount.is_finite() or amount < 0 or amount != amount.quantize(Decimal("0.01")):
                raise ValueError
            result[key] = str(amount.quantize(Decimal("0.01")))
    except (ValueError, InvalidOperation, TypeError) as exc:
        raise PawnRepaymentError("Item principal splits need valid item IDs and non-negative two-decimal amounts.") from exc
    return result


def _evidence(*, received_on, receipt_reference, amount, item_principal_split=None):
    if type(received_on) is not date or received_on > timezone.localdate():
        raise PawnRepaymentError("Enter the actual receipt date, no later than today.")
    if not isinstance(receipt_reference, str):
        raise PawnRepaymentError("Enter the paper receipt or book/page reference.")
    reference = receipt_reference.strip()
    if not reference or len(reference) > 255 or any(ord(c) < 32 or ord(c) == 127 for c in reference):
        raise PawnRepaymentError("Enter a paper reference of 1–255 characters without control characters.")
    evidence = {
        "profile": PROFILE,
        "received_on": received_on.isoformat(),
        "date_precision": "DAY",
        "receipt_reference": reference,
        "reference_key": " ".join(reference.split()).casefold(),
        "amount_received": _decimal_string(amount),
        "allocation_basis": "DERIVED_FROM_AGREED_TERMS",
        "original_receiver": None,
        "confirmed_received": True,
    }
    if item_principal_split is not None:
        evidence["item_principal_split"] = normalize_item_split(item_principal_split)
    return evidence


def validate_paper_repayment_evidence(evidence, *, effective_date, amount):
    """Validate preserved source metadata, including during portable restoration."""
    if not isinstance(evidence, dict):
        raise PawnRepaymentError("Invalid paper receipt evidence.")
    expected = _evidence(received_on=effective_date,
                         receipt_reference=evidence.get("receipt_reference"), amount=amount,
                         item_principal_split=evidence.get("item_principal_split"))
    if evidence != expected or type(evidence.get("confirmed_received")) is not bool:
        raise PawnRepaymentError("Paper receipt evidence does not match its date and amount.")


def _preview(loan, *, amount, received_on, evidence):
    from .servicing_eligibility import servicing_eligibility, paper_repayment_allocation_allowed
    from apps.tenant_apps.loans.selectors.servicing_contract import get_servicing_position
    servicing_eligibility(loan, operation="REPAYMENT", purpose="PAPER", effective_date=received_on).require()
    if loan.loan_events.filter(
        event_kind="REPAYMENT",
        payload__repayment__recording__reference_key=evidence["reference_key"],
    ).exists():
        raise PawnRepaymentError(
            "This paper reference is already recorded for this loan. Review the original receipt or its correction."
        )
    try:
        balance = get_servicing_position(loan, as_of_date=received_on).balance
        allocation = allocate_repayment(balance, amount)
        paper_repayment_allocation_allowed(loan, balance, allocation)
        preview = _repayment_preview(loan, balance, allocation, item_principal_split=evidence.get("item_principal_split"), paper=True)
    except ValueError as exc:
        raise PawnRepaymentError(str(exc)) from exc
    return preview


def _review_values(loan, actor, request_key, evidence, preview):
    return {
        "workspace": loan.workspace_id, "loan": loan.pk, "actor": actor.pk,
        "request_key": request_key, "evidence": evidence,
        "latest_event": loan.loan_events.order_by("-pk").values_list("pk", flat=True).first(),
        "preview": json.loads(json.dumps(asdict(preview), default=str)),
    }


@transaction.atomic
def preview_paper_repayment(loan_id, *, amount, received_on, receipt_reference, request_key, actor, item_principal_split=None):
    loan = _locked_loan(loan_id)
    require_loan_action(loan, actor, "loan.repay")
    amount, request_key = _money_amount(amount, loan), _request_key(request_key)
    evidence = _evidence(received_on=received_on, receipt_reference=receipt_reference, amount=amount, item_principal_split=item_principal_split)
    preview = _preview(loan, amount=amount, received_on=received_on, evidence=evidence)
    token = signing.dumps(_review_values(loan, actor, request_key, evidence, preview), salt=SALT, compress=True)
    return PaperRepaymentReview(preview, token)


@transaction.atomic
def record_paper_repayment(loan_id, *, amount, received_on, receipt_reference,
                           request_key, actor, review_token, confirmed_received=False, item_principal_split=None):
    loan = _locked_loan(loan_id)
    require_loan_action(loan, actor, "loan.repay")
    amount, request_key = _money_amount(amount, loan), _request_key(request_key)
    evidence = _evidence(received_on=received_on, receipt_reference=receipt_reference, amount=amount, item_principal_split=item_principal_split)
    if confirmed_received is not True:
        raise PawnRepaymentError("Confirm that this amount was already received on the stated date.")
    # Authorize and compare original facts before returning an idempotent result.
    existing = _existing_result(loan, request_key, amount)
    if existing:
        if (existing.loan_event.effective_date != received_on or
                existing.loan_event.payload["repayment"].get("recording") != evidence):
            raise PawnRepaymentError("This request key already records different receipt facts.")
        return existing
    preview = _preview(loan, amount=amount, received_on=received_on, evidence=evidence)
    try:
        approved = signing.loads(review_token or "", salt=SALT, max_age=MAX_AGE)
    except (signing.BadSignature, TypeError, ValueError) as exc:
        raise PawnRepaymentError("Preview this receipt again before recording it; the review is missing or expired.") from exc
    if approved != _review_values(loan, actor, request_key, evidence, preview):
        raise PawnRepaymentError("The receipt or loan changed since review. Preview the allocation again.")
    return _record_pawn_loan_repayment_at(
        loan_id, amount=amount, request_key=request_key, actor=actor,
        effective_date=received_on, recording_evidence=evidence,
    )
