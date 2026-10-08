"""Review a completed closure on one supported ordinary loan."""
from datetime import date
from decimal import Decimal

from django.core import signing
from django.db import transaction
from django.utils import timezone

from .action_access import require_loan_action
from .pawn_release import _locked_loan, _tenant_loan, _release_pawn_loan_in_full_at
from .recorded_history import _amount, _digest, _text
from apps.tenant_apps.loans.selectors.transaction_completeness import transaction_fingerprint

SALT = "loans.independent-paper-closure.v1"


def _facts(data):
    required = {"date", "amount", "number", "reference", "basis", "recipient", "request_key"}
    optional = {"interest_concession", "concession_reason", "exception_reason", "paid_by",
                "collector_is_borrower", "relationship", "authorization_note"}
    if not isinstance(data, dict) or not required <= set(data) or set(data) - required - optional:
        raise ValueError("Enter the actual closing date, settlement and paper reference.")
    facts = dict(data)
    day = date.fromisoformat(facts["date"])
    if day > timezone.localdate():
        raise ValueError("Paper closure cannot be in the future.")
    facts["amount"] = _amount(facts["amount"], "settlement")
    facts["number"] = _text(facts["number"], "number", 64) if facts["number"] else ""
    for name in ("reference", "request_key"):
        facts[name] = (_text(facts[name], name, 120 if name == "request_key" else 160)
                       if facts[name] or name == "request_key" or not (set(data) & optional) else "")
    if facts["basis"] not in ("RETURNED", "PAPER_SETTLEMENT"):
        raise ValueError("Choose a confirmed return or paper-only settlement.")
    facts["recipient"] = _text(facts["recipient"], "return recipient", 255) if facts["basis"] == "RETURNED" else ""
    if set(data) & optional:
        # Retain the exact seven-fact digest on already issued old requests.
        facts["interest_concession"] = _amount(data.get("interest_concession") or "0", "interest concession")
        for name, limit in (("concession_reason", 255), ("exception_reason", 255), ("paid_by", 255),
                            ("relationship", 100), ("authorization_note", 500)):
            value = data.get(name) or ""
            facts[name] = _text(value, name, limit) if value else ""
        if Decimal(facts["interest_concession"]) and not facts["concession_reason"]:
            raise ValueError("Explain the agreed interest concession.")
        borrower = data.get("collector_is_borrower", True)
        if type(borrower) is not bool:
            raise ValueError("Choose borrower or another recipient.")
        facts["collector_is_borrower"] = borrower
        if facts["basis"] == "PAPER_SETTLEMENT":
            for name in ("paid_by", "relationship", "authorization_note"):
                facts[name] = ""
        elif not facts["paid_by"]:
            raise ValueError("Enter the payer for confirmed cash collection and return.")
        elif not borrower and not (facts["relationship"] and facts["authorization_note"]):
            raise ValueError("Another recipient needs relationship and authority-to-collect evidence.")
    return facts


def _source(loan_id, actor, facts, *, commit=False):
    from .paper_closures import require_completed_closure_access
    candidate = _tenant_loan(loan_id)
    require_loan_action(candidate, actor, "loan.release")
    require_completed_closure_access(candidate.workspace, actor, date.fromisoformat(facts["date"]),
        facts.get("exception_reason", ""), lock=commit)
    loan = _locked_loan(loan_id)
    require_loan_action(loan, actor, "loan.release")
    return loan


def _write(loan, facts, actor, *, batch_id=None):
    day = date.fromisoformat(facts["date"])
    from .servicing_eligibility import servicing_eligibility
    servicing_eligibility(loan, operation="FULL_RELEASE", purpose="PAPER", effective_date=day).require()
    evidence = dict(profile="recorded-history-closure/1", date_precision="DAY",
        paper_reference=facts["reference"], collector_name=facts["recipient"], original_actor=None,
        closure_basis=facts["basis"], request_sha256=_digest(facts),
        original_release_number=facts["number"] or None,
        number_basis="ORIGINAL_PAPER" if facts["number"] else "SYSTEM_ASSIGNED")
    if "interest_concession" in facts:
        evidence.update(exception_reason=facts["exception_reason"], paid_by=facts["paid_by"],
            collector_is_borrower=facts["collector_is_borrower"], relationship=facts["relationship"],
            authorization_note=facts["authorization_note"])
        if (facts["basis"] == "RETURNED" and facts["collector_is_borrower"]
                and facts["recipient"] != loan.borrower.display_name):
            raise ValueError("Select another recipient when someone other than the borrower received the items.")
    if batch_id is not None:
        evidence["batch_id"] = batch_id
    return _release_pawn_loan_in_full_at(loan.pk, settlement_amount=Decimal(facts["amount"]),
        request_key=facts["request_key"], actor=actor, effective_date=day,
        interest_concession=Decimal(facts.get("interest_concession", "0")),
        concession_reason=facts.get("concession_reason", ""), recorded_number=facts["number"] or None, paper_evidence=evidence)


def _review(result, facts):
    review = dict(date=facts["date"], number=result.loan.loan_number,
        closing_number=result.release.release_number,
        number_basis="ORIGINAL_PAPER" if facts["number"] else "SYSTEM_ASSIGNED",
        settlement=str(result.release.settlement_amount), principal=str(result.release.principal_amount),
        interest=str(result.release.interest_amount), basis=facts["basis"], reference=facts["reference"])
    if "interest_concession" in facts:
        review.update(interest_concession=facts["interest_concession"], concession_reason=facts["concession_reason"])
    return review


@transaction.atomic
def preview_recorded_closure(*, loan_id, actor, data):
    facts = _facts(data)
    loan = _source(loan_id, actor, facts)
    fingerprint = transaction_fingerprint(loan)
    with transaction.atomic():
        result = _write(loan, facts, actor)
        review = _review(result, facts)
        transaction.set_rollback(True)
    token = signing.dumps(dict(loan=loan.pk, workspace=loan.workspace_id, actor=actor.pk,
        facts=_digest(facts), fingerprint=fingerprint, review=review), salt=SALT)
    return review, token


@transaction.atomic
def record_paper_closure(*, loan_id, actor, data, review_token, confirmed=False):
    facts = _facts(data)
    loan = _source(loan_id, actor, facts, commit=True)
    existing = loan.releases.filter(request_key=facts["request_key"]).first()
    if existing:
        evidence = existing.loan_event.payload.get("release", {}).get("paper_closure", {})
        if evidence.get("request_sha256") != _digest(facts):
            raise ValueError("This submission already recorded different closure facts.")
        return existing, False
    if confirmed is not True:
        raise ValueError("Review and confirm this paper closure.")
    try:
        expected = signing.loads(review_token or "", salt=SALT, max_age=3600)
    except signing.BadSignature as exc:
        raise ValueError("Review this paper closure again.") from exc
    values = dict(loan=loan.pk, workspace=loan.workspace_id, actor=actor.pk,
        facts=_digest(facts), fingerprint=transaction_fingerprint(loan))
    if any(expected.get(key) != value for key, value in values.items()):
        raise ValueError("Loan activity or closure facts changed. Review again.")
    from apps.tenant_apps.loans.selectors.transaction_completeness import transaction_completeness
    coverage = transaction_completeness(loan, date.fromisoformat(facts["date"]))
    covered = coverage.required and coverage.complete
    result = _write(loan, facts, actor)
    if expected["review"] != _review(result, facts):
        raise ValueError("The closure calculation changed. Review again.")
    from .transaction_reviews import _store
    if covered:
        _store(result.loan, actor, through_date=date.fromisoformat(facts["date"]), confirmed_complete=True,
            source_reference=facts["reference"], request_key=f"closure:{facts['request_key']}")
    return result.release, True
