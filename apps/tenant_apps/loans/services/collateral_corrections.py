"""Reviewed transcription corrections; agreement economics and custody stay frozen."""
from copy import deepcopy
from decimal import Decimal, InvalidOperation

from django.core import signing
from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone

from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.access import LOANS_ADMIN_ACTION
from apps.tenant_apps.loans.domain import CollateralMetal
from apps.tenant_apps.loans.selectors.exposure import get_pawn_loan_exposure, require_consistent_exposure
from apps.tenant_apps.loans.selectors.transaction_completeness import transaction_fingerprint
from .action_access import require_loan_action
from .recorded_history import _digest, _text

PROFILE = "collateral-fact-correction/1"
SALT = "loans.collateral-fact-correction.v1"
FIELDS = ("description", "quantity", "metal", "gross_weight", "net_weight", "purity_percentage")
MEASUREMENTS = frozenset(FIELDS) - {"description"}


def normalize_details(values):
    if not isinstance(values, dict) or set(values) != set(FIELDS):
        raise ValueError("Correct only the recorded description, quantity, metal, weights and purity.")
    result = dict(values)
    result["description"] = _text(values["description"], "the collateral description", 255)
    if values["metal"] not in {value.value for value in CollateralMetal}:
        raise ValueError("Select a supported collateral metal.")
    if values["quantity"] is not None and (type(values["quantity"]) is not int or not 1 <= values["quantity"] <= 10000):
        raise ValueError("Quantity must be a whole number from 1 to 10,000, or remain unrecorded.")
    for key in ("gross_weight", "net_weight", "purity_percentage"):
        if key == "gross_weight" and values[key] is None:
            continue
        try:
            value = Decimal(str(values[key]))
            if (not value.is_finite() or value <= 0 or value >= Decimal("10000000000")
                    or (key == "purity_percentage" and value > 100)
                    or value != value.quantize(Decimal(".0001"))):
                raise ValueError()
        except (ValueError, InvalidOperation):
            raise ValueError("Enter positive weights and purity with at most four decimal places; purity cannot exceed 100%.") from None
        result[key] = format(value, ".4f")
    if result["gross_weight"] is not None and Decimal(result["gross_weight"]) < Decimal(result["net_weight"]):
        raise ValueError("Gross weight cannot be less than net weight.")
    return result


def item_details(item):
    return normalize_details({key: getattr(item, key) for key in FIELDS})


def correction_facts(data):
    if not isinstance(data, dict) or set(data) != {"item_id", "after", "reference", "reason", "request_key"}:
        raise ValueError("Select an existing collateral item and provide its correction and supporting reference.")
    if type(data["item_id"]) is not int or data["item_id"] <= 0:
        raise ValueError("Select a collateral item on this loan.")
    return dict(item_id=data["item_id"], after=normalize_details(data["after"]),
        reference=_text(data["reference"], "the supporting reference", 160),
        reason=_text(data["reason"], "the correction reason", 500),
        request_key=_text(data["request_key"], "the correction request reference", 80))


def collateral_correction_blockers(loan):
    blockers = []
    if loan.state not in {"ACTIVE", "CLOSED"}:
        blockers.append("Edit a preparation draft directly; return an approved loan to draft before changing it.")
    if loan.is_imported_closed_position:
        blockers.append("This verified closed position requires a source-position reconciliation.")
    if m.PawnLoanRenewal.objects.filter(Q(source_loan=loan) | Q(successor_loan=loan)).exists():
        blockers.append("Linked renewals require a review of both loans before correcting collateral details.")
    if (loan.auctions.exists() or m.FundingPledgeItem.objects.filter(collateral_item__loan=loan).exists()
            or m.FundingLoanDraftCollateral.objects.filter(collateral_item__loan=loan).exists()):
        blockers.append("Auction or funding records require a connected collateral reconciliation.")
    return blockers


def _locked_loan(loan_id, actor):
    workspace_id = m.current_tenant_workspace_id()
    if workspace_id is None:
        raise ValueError("Collateral correction requires an active Workspace.")
    try:
        loan = m.PawnLoan.objects.select_for_update(of=("self",)).get(pk=loan_id, workspace_id=workspace_id)
    except m.PawnLoan.DoesNotExist:
        raise ValueError("Loan was not found in the active Workspace.") from None
    require_loan_action(loan, actor, LOANS_ADMIN_ACTION, "data.edit")
    return loan


def _review(loan, facts):
    blockers = collateral_correction_blockers(loan)
    if blockers:
        raise ValueError(" ".join(blockers))
    require_consistent_exposure(get_pawn_loan_exposure(loan.pk, as_of_date=timezone.localdate()))
    try:
        item = loan.collateral_items.select_for_update().get(pk=facts["item_id"], workspace_id=loan.workspace_id)
    except m.PawnCollateralItem.DoesNotExist:
        raise ValueError("Select an existing collateral item on this loan.") from None
    before, after = item_details(item), facts["after"]
    if before == after:
        raise ValueError("No collateral details changed.")
    for key in ("quantity", "gross_weight"):
        if before[key] is not None and after[key] is None:
            raise ValueError("A recorded quantity or gross weight cannot be cleared by this correction.")
    validate_correction_chain(loan)
    source_rows = corrected_collateral_source(loan, _source_rows(loan))
    source_item = next((row for row in source_rows if row["item_id"] == item.pk), None)
    if source_item is None or any(before[key] != value for key, value in _row_details(source_item).items()):
        raise ValueError("Current collateral does not match its retained source. Reconcile that evidence before correcting it.")
    version = item.appraisals.aggregate(value=Max("version"))["value"] or 0
    review = dict(item_id=item.pk, before=before, after=after,
        valuation_changed=any(before[key] != after[key] for key in MEASUREMENTS),
        appraisal_version=version, reference=facts["reference"], reason=facts["reason"])
    source = _digest(dict(review=review, transactions=transaction_fingerprint(loan),
        loan_updated=loan.updated_at.isoformat(), items=[{key: str(value) for key, value in row.items()}
            for row in loan.collateral_items.order_by("pk").values()],
        corrections=list(loan.change_log.filter(event_kind="COLLATERAL_CORRECTED").values_list("pk", "metadata"))))
    return item, review, source


def _source_rows(loan):
    """Use the existing frozen agreement, including honest import boundaries."""
    from .recorded_collections import recording_for
    recording = recording_for(loan)
    if recording:
        return recording["terms"]["collateral"]
    approval = loan.approval_snapshots.order_by("-version").first()
    if approval and approval.payload.get("collateral"):
        return approval.payload["collateral"]
    origin = getattr(loan, "historical_import", None)
    if origin:
        event = loan.loan_events.filter(event_kind="MIGRATION_OPENING").first()
        if event:
            from .opening_evidence import read_opening_evidence
            opening = read_opening_evidence(loan, event)
            rows, mapping = opening["review"]["collateral"], opening["item_mapping"]
        else:
            rows, mapping = origin.document.get("loan", {}).get("collateral", []), origin.references["items"]
        return [dict(item_id=mapping[row["id"]], description=row["description"], metal=row["metal"],
            quantity=row.get("quantity"), gross_weight=row.get("gross_weight"), net_weight=row["net_weight"],
            purity_percentage=row["purity"]) for row in rows]
    raise ValueError("Review the original collateral evidence before correcting this loan.")


def _row_details(row):
    result = {key: row[key] for key in FIELDS if key in row}
    for key in ("gross_weight", "net_weight", "purity_percentage"):
        if key in result and result[key] is not None:
            result[key] = format(Decimal(str(result[key])), ".4f")
    return result


@transaction.atomic
def preview_collateral_correction(loan_id, *, actor, data):
    facts = correction_facts(data)
    loan = _locked_loan(loan_id, actor)
    _, review, source = _review(loan, facts)
    return review, signing.dumps(dict(loan=loan.pk, workspace=loan.workspace_id, actor=actor.pk,
        facts=_digest(facts), source=source), salt=SALT, compress=True)


@transaction.atomic
def record_collateral_correction(loan_id, *, actor, data, review_token, confirmed=False):
    facts = correction_facts(data)
    loan = _locked_loan(loan_id, actor)
    if confirmed is not True:
        raise ValueError("Confirm the reviewed collateral correction.")
    existing = loan.change_log.filter(event_kind="COLLATERAL_CORRECTED",
        metadata__collateral_correction__request_key=facts["request_key"]).first()
    if existing:
        if existing.actor_id != actor.pk or existing.metadata["collateral_correction"]["request_sha256"] != _digest(facts):
            raise ValueError("This request already records different collateral facts.")
        return existing, False
    item, review, source = _review(loan, facts)
    try:
        signed = signing.loads(review_token or "", salt=SALT, max_age=3600)
    except signing.BadSignature:
        raise ValueError("Review this collateral correction again.") from None
    if signed != dict(loan=loan.pk, workspace=loan.workspace_id, actor=actor.pk, facts=_digest(facts), source=source):
        raise ValueError("Loan, collateral or appraisal facts changed. Review this correction again.")
    correction = m.LoanChangeLog.objects.create(workspace_id=loan.workspace_id, loan=loan,
        event_kind="COLLATERAL_CORRECTED", from_state=loan.state, to_state=loan.state, actor=actor,
        reason=facts["reason"], metadata=dict(collateral_correction=dict(schema=PROFILE,
            request_key=facts["request_key"], request_sha256=_digest(facts), source_fingerprint=source, **review)))
    # Validation above covers the permitted fields. Retain the original metal-rate
    # policy reference: it describes agreed economics, not a corrected measurement.
    m.PawnCollateralItem.objects.filter(pk=item.pk, loan=loan, workspace_id=loan.workspace_id).update(
        **{key: facts["after"][key] for key in FIELDS}, updated_at=timezone.now())
    loan.updated_by = actor
    loan.save(update_fields=["updated_by", "updated_at"])
    if review["valuation_changed"]:
        m.LoanRiskSnapshot.objects.filter(workspace_id=loan.workspace_id, loan=loan).exclude(status="ERROR").update(
            status="STALE", error_message="Collateral details corrected; reassessment required.")
    return correction, True


def validate_correction_rows(logs, items):
    """Shared source-local validator for live reads and portable version 6."""
    chains = {}
    keys = set()
    for log in logs:
        evidence = log.metadata.get("collateral_correction")
        if not evidence or evidence.get("schema") != PROFILE:
            raise ValueError("Unsupported collateral correction evidence.")
        facts = correction_facts({key: evidence.get(key) for key in ("item_id", "after", "reference", "reason", "request_key")})
        before = normalize_details(evidence.get("before"))
        fingerprint = evidence.get("source_fingerprint")
        item = items.get(facts["item_id"])
        if (item is None or item.loan_id != log.loan_id or item.workspace_id != log.workspace_id
                or log.actor_id is None or log.from_state != log.to_state or log.from_state not in {"ACTIVE", "CLOSED"}
                or log.reason != facts["reason"] or evidence.get("request_sha256") != _digest(facts)
                or type(evidence.get("appraisal_version")) is not int or evidence["appraisal_version"] < 0
                or type(evidence.get("valuation_changed")) is not bool
                or evidence["valuation_changed"] != any(before[key] != facts["after"][key] for key in MEASUREMENTS)
                or evidence.get("before") != before or evidence.get("after") != facts["after"]
                or not isinstance(fingerprint, str) or len(fingerprint) != 64 or any(c not in "0123456789abcdef" for c in fingerprint)
                or any(before[key] is not None and facts["after"][key] is None for key in ("quantity", "gross_weight"))
                or before == facts["after"]):
            raise ValueError("Invalid collateral correction chain.")
        if facts["request_key"] in keys:
            raise ValueError("Duplicate collateral correction request.")
        keys.add(facts["request_key"])
        chain = chains.setdefault(item.pk, [])
        if chain and chain[-1]["after"] != before:
            raise ValueError("Collateral correction history needs reconciliation.")
        chain.append(evidence)
    for pk, chain in chains.items():
        if item_details(items[pk]) != chain[-1]["after"]:
            raise ValueError("Current collateral differs from its reviewed correction.")
    return chains


def validate_correction_chain(loan):
    logs = list(loan.change_log.filter(event_kind="COLLATERAL_CORRECTED").order_by("pk"))
    if not logs:
        return {}
    return validate_correction_rows(logs, {item.pk: item for item in loan.collateral_items.order_by("pk")})


def corrected_collateral_source(loan, rows):
    """Project reviewed facts on a copy, leaving original source evidence intact."""
    chains = validate_correction_chain(loan)
    result = deepcopy(rows)
    for row in result:
        chain = chains.get(int(row["item_id"]))
        if chain:
            # Frozen snapshots may precede or follow an earlier correction.
            # Accept only a genuine reviewed version, never an unrelated source.
            known = _row_details(row)
            versions = [chain[0]["before"], *(evidence["after"] for evidence in chain)]
            if not any(all(version[key] == value for key, value in known.items()) for version in versions):
                raise ValueError("Collateral correction does not match its original source evidence.")
            row.update(chain[-1]["after"])
            # A prior appraisal is not a valuation of the corrected item facts.
            if any(evidence["valuation_changed"] for evidence in chain) and "latest_appraised_value" in row:
                row["latest_appraised_value"] = None
    return result


def collateral_document_fingerprint(loan, source):
    latest = loan.change_log.filter(event_kind="COLLATERAL_CORRECTED").order_by("pk").last()
    if latest is None:
        return source
    return _digest(dict(source=source, collateral_correction=latest.pk,
        request_sha256=latest.metadata["collateral_correction"]["request_sha256"]))


def invalidated_appraisal_versions(loan):
    result = {}
    for log in loan.change_log.filter(event_kind="COLLATERAL_CORRECTED").order_by("pk"):
        evidence = log.metadata["collateral_correction"]
        if evidence["valuation_changed"]:
            result[evidence["item_id"]] = max(result.get(evidence["item_id"], 0), evidence["appraisal_version"])
    return result


def appraisals_for_corrected_facts(queryset):
    """Exclude appraisal versions predating the latest measurement review."""
    from django.db.models import BigIntegerField, F, IntegerField, OuterRef, Subquery, Value
    from django.db.models.functions import Cast, Coalesce
    corrections = m.LoanChangeLog.objects.filter(
        workspace_id=OuterRef("workspace_id"), loan_id=OuterRef("collateral_item__loan_id"),
        event_kind="COLLATERAL_CORRECTED", metadata__collateral_correction__valuation_changed=True,
    ).annotate(corrected_item=Cast("metadata__collateral_correction__item_id", BigIntegerField()),
        cutoff=Cast("metadata__collateral_correction__appraisal_version", IntegerField()),
    ).filter(corrected_item=OuterRef("collateral_item_id")).order_by("-pk")
    return queryset.alias(correction_cutoff=Coalesce(Subquery(corrections.values("cutoff")[:1]), Value(-1))).filter(version__gt=F("correction_cutoff"))
