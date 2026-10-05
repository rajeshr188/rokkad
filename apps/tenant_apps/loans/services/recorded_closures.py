"""Record one existing paper loan's closure, without reconstructing other loans."""
from datetime import date
from decimal import Decimal

from django.core import signing
from django.db import transaction
from django.utils import timezone

from .action_access import require_loan_action
from .pawn_release import _locked_loan, _release_pawn_loan_in_full_at
from .recorded_collections import recording_for
from .recorded_history import _amount, _digest, _text
from apps.tenant_apps.loans.selectors.transaction_completeness import transaction_fingerprint

SALT = "loans.independent-paper-closure.v1"


def _facts(data):
    if not isinstance(data, dict) or set(data) != {"date", "amount", "number", "reference", "basis", "recipient", "request_key"}:
        raise ValueError("Enter the actual closing date, settlement and paper reference.")
    facts = dict(data)
    day = date.fromisoformat(facts["date"])
    if day > timezone.localdate():
        raise ValueError("Paper closure cannot be in the future.")
    facts["amount"] = _amount(facts["amount"], "settlement")
    facts["number"] = _text(facts["number"], "number", 64) if facts["number"] else ""
    for name in ("reference", "request_key"):
        facts[name] = _text(facts[name], name, 64 if name == "number" else 120 if name == "request_key" else 160)
    if facts["basis"] not in ("RETURNED", "PAPER_SETTLEMENT"):
        raise ValueError("Choose a confirmed return or paper-only settlement.")
    facts["recipient"] = _text(facts["recipient"], "return recipient", 255) if facts["basis"] == "RETURNED" else ""
    return facts


def _source(loan_id, actor):
    loan = _locked_loan(loan_id)
    require_loan_action(loan, actor, "loan.release")
    if not recording_for(loan):
        raise ValueError("Use the ordinary release workflow for this loan.")
    return loan


def _write(loan, facts, actor):
    day = date.fromisoformat(facts["date"])
    if day < loan.loan_date or loan.loan_events.filter(effective_date__gt=day).exists():
        raise ValueError("Review later financial activity before recording this earlier closure.")
    if loan.collateral_items.filter(custody_history__effective_date__gt=day).exists():
        raise ValueError("Review later collateral activity before this closure.")
    evidence = dict(profile="recorded-history-closure/1", date_precision="DAY",
        paper_reference=facts["reference"], collector_name=facts["recipient"], original_actor=None,
        closure_basis=facts["basis"], request_sha256=_digest(facts),
        original_release_number=facts["number"] or None,
        number_basis="ORIGINAL_PAPER" if facts["number"] else "SYSTEM_ASSIGNED")
    return _release_pawn_loan_in_full_at(loan.pk, settlement_amount=Decimal(facts["amount"]),
        request_key=facts["request_key"], actor=actor, effective_date=day,
        interest_concession=Decimal("0"), concession_reason="", recorded_number=facts["number"] or None, paper_evidence=evidence)


def _review(result, facts):
    return dict(date=facts["date"], number=result.loan.loan_number,
        closing_number=result.release.release_number,
        number_basis="ORIGINAL_PAPER" if facts["number"] else "SYSTEM_ASSIGNED",
        settlement=str(result.release.settlement_amount), principal=str(result.release.principal_amount),
        interest=str(result.release.interest_amount), basis=facts["basis"], reference=facts["reference"])


@transaction.atomic
def preview_recorded_closure(*, loan_id, actor, data):
    facts, loan = _facts(data), _source(loan_id, actor)
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
    facts, loan = _facts(data), _source(loan_id, actor)
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
    covered = transaction_completeness(loan, date.fromisoformat(facts["date"])).complete
    result = _write(loan, facts, actor)
    if expected["review"] != _review(result, facts):
        raise ValueError("The closure calculation changed. Review again.")
    from .transaction_reviews import _store
    if covered:
        _store(result.loan, actor, through_date=date.fromisoformat(facts["date"]), confirmed_complete=True,
            source_reference=facts["reference"], request_key=f"closure:{facts['request_key']}")
    return result.release, True
