"""One known, already-completed paper renewal from an existing ordinary loan."""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from django.core import signing
from django.db import transaction
from django.utils import timezone

from .action_access import require_loan_action
from .pawn_release import _locked_loan
from .recorded_collections import recording_for
from .recorded_history import _amount, _digest, _text
from .recorded_renewals import record_admission_renewal
from apps.tenant_apps.loans.selectors.transaction_completeness import transaction_fingerprint

SALT = "loans.existing-paper-renewal.v1"


def _facts(data):
    fields = {"date", "number", "rate", "tenure", "new_principal", "advance_months", "document_charge",
        "amount", "cash_paid", "reference", "request_key"}
    if not isinstance(data, dict) or not fields <= set(data) or set(data) - fields - {"product_version_id", "currency_quantum"}:
        raise ValueError("Enter the known renewal's actual terms, deductions and net cash.")
    facts = dict(data)
    quantum = facts.get("currency_quantum", "0.01")
    if quantum not in ("0.01", "1"):
        raise ValueError("Enter the new agreement's supported interest rounding quantum.")
    if "product_version_id" in facts and (type(facts["product_version_id"]) is not int or facts["product_version_id"] <= 0):
        raise ValueError("Select the contract version matching the new paper agreement.")
    facts["request_key"] = str(UUID(facts["request_key"]))
    day = date.fromisoformat(facts["date"])
    if day > timezone.localdate():
        raise ValueError("An already-completed renewal cannot be in the future.")
    for name in ("number", "reference"):
        facts[name] = _text(facts[name], name, 64 if name == "number" else 160)
    for name in ("new_principal", "document_charge", "amount", "cash_paid"):
        facts[name] = _amount(facts[name], name, positive=name == "new_principal")
    facts["rate"] = _amount(facts["rate"], "monthly rate", places=6)
    if (type(facts["tenure"]) is not int or not 1 <= facts["tenure"] <= 600 or Decimal(facts["rate"]) > 999
            or type(facts["advance_months"]) is not int or facts["advance_months"] not in (0, 1)):
        raise ValueError("Use a supported rate, tenure and zero or one advance month.")
    advance = (Decimal(facts["new_principal"])*Decimal(facts["rate"])/100).quantize(Decimal(quantum), rounding=ROUND_HALF_UP)*facts["advance_months"]
    if advance + Decimal(facts["document_charge"]) >= Decimal(facts["new_principal"]):
        raise ValueError("Deductions must leave positive new loan proceeds.")
    return facts


def _source(loan_id, actor):
    loan = _locked_loan(loan_id)
    require_loan_action(loan, actor, "data.create", "loan.release", "loan.disburse")
    if not recording_for(loan) and not loan.loan_events.filter(event_kind="MIGRATION_OPENING").exists():
        raise ValueError("This paper-renewal profile requires an entered paper contract.")
    return loan


def _write(source, actor, facts):
    day = date.fromisoformat(facts["date"])
    from .servicing_eligibility import servicing_eligibility
    servicing_eligibility(source, operation="RENEWAL", purpose="PAPER", effective_date=day).require()
    if source.state != "ACTIVE" or hasattr(source, "renewal_as_source"):
        raise ValueError("Only an outstanding loan without a successor can be renewed.")
    if day < source.loan_date or source.loan_events.filter(effective_date__gt=day).exists():
        raise ValueError("Review later financial activity before recording this earlier renewal.")
    if source.auctions.filter(state__in=("INITIATED", "IN_PROGRESS")).exists():
        raise ValueError("Cancel the active auction before renewal.")
    items = list(source.collateral_items.select_for_update().all())
    if len(items) != 1 or items[0].custody_state != "IN_VAULT":
        raise ValueError("This recorded renewal supports one collateral group still held by the business.")
    if items[0].custody_history.filter(effective_date__gt=day).exists():
        raise ValueError("Review later collateral movements before this renewal.")
    from .physical_verification import assert_physical_verification_clear
    from .pawn_disbursal import assert_pawn_loan_financial_actions_allowed
    assert_physical_verification_clear((items[0].pk,), operation="Recorded paper renewal")
    origin = source.loan_events.filter(event_kind="MIGRATION_OPENING").first()
    if origin:
        from .opening_servicing import opening_release_context
        opening_release_context(source, as_of_date=day)
    else:
        assert_pawn_loan_financial_actions_allowed(source.pk)
    item, policy = items[0], source.policy_snapshot
    if origin:
        from .opening_evidence import read_opening_evidence
        opening = read_opening_evidence(source, origin)
        original = [dict(row, item_id=opening["item_mapping"][row["id"]], purity_percentage=row["purity"])
                    for row in opening["review"]["collateral"]]
    else:
        original = recording_for(source)["terms"]["collateral"]
    if len(original) != 1 or original[0]["item_id"] != item.pk:
        raise ValueError("Collateral contract facts changed. Reconcile them before recording the known renewal.")
    for field in (("metal", "gross_weight", "net_weight", "purity_percentage") if origin else
                  ("description", "metal", "quantity", "gross_weight", "net_weight", "purity_percentage")):
        actual, expected = getattr(item, field), original[0][field]
        if isinstance(actual, Decimal):
            expected = Decimal(str(expected))
        if actual != expected:
            raise ValueError("Collateral contract facts changed. Reconcile them before recording the known renewal.")
    data = dict(series_id=source.series_id, borrower_id=source.borrower_id,
        product_version_id=facts.get("product_version_id", source.product_version_id),
        source_reference=facts["reference"], quantity=item.quantity, description=item.description,
        metal=item.metal, gross_weight=str(item.gross_weight), net_weight=str(item.net_weight), purity=str(item.purity_percentage),
        monitoring_method=policy.valuation_method, monitoring_ltv=str(policy.maximum_ltv_ratio),
        monitoring_reason="Continue the existing current monitoring selection", complete_through=facts["date"],
        confirmed_history=True)
    data["currency_quantum"] = facts.get("currency_quantum", "0.01")
    row = dict(facts, renewal_method="NET_SETTLEMENT", custody="HELD", recipient="", request_sha256=_digest(facts))
    successor, review = record_admission_renewal(source.workspace, actor, data, UUID(facts["request_key"]), source,
        row, f"paper-renewal:{facts['request_key']}")
    return successor, review


@transaction.atomic
def preview_existing_paper_renewal(*, loan_id, actor, data):
    facts, source = _facts(data), _source(loan_id, actor)
    fingerprint = transaction_fingerprint(source)
    with transaction.atomic():
        _, review = _write(source, actor, facts)
        transaction.set_rollback(True)
    token = signing.dumps(dict(loan=source.pk, workspace=source.workspace_id, actor=actor.pk,
        facts=_digest(facts), fingerprint=fingerprint, review=review), salt=SALT)
    return review, token


@transaction.atomic
def record_existing_paper_renewal(*, loan_id, actor, data, review_token, confirmed=False):
    facts, source = _facts(data), _source(loan_id, actor)
    if hasattr(source, "renewal_as_source"):
        existing = source.renewal_as_source
        saved = existing.opening_event.payload.get("recording", {})
        if existing.request_key == f"paper-renewal:{facts['request_key']}" and saved.get("renewal_request_sha256") == _digest(facts):
            return existing.successor_loan, False
        raise ValueError("This loan already has a renewal successor. Open its history.")
    if confirmed is not True:
        raise ValueError("Review and confirm the actual renewal before recording it.")
    try:
        expected = signing.loads(review_token or "", salt=SALT, max_age=3600)
    except signing.BadSignature as exc:
        raise ValueError("Review the paper renewal again.") from exc
    values = dict(loan=source.pk, workspace=source.workspace_id, actor=actor.pk,
        facts=_digest(facts), fingerprint=transaction_fingerprint(source))
    if any(expected.get(key) != value for key, value in values.items()):
        raise ValueError("Source activity or renewal facts changed. Review again.")
    successor, review = _write(source, actor, facts)
    if expected["review"] != review:
        raise ValueError("The settlement calculation changed. Review again.")
    from .transaction_reviews import _store
    source.refresh_from_db()
    for loan in (source, successor):
        _store(loan, actor, through_date=date.fromisoformat(facts["date"]), confirmed_complete=True,
            source_reference=facts["reference"], request_key=f"paper-renewal:{facts['request_key']}")
    return successor, True
