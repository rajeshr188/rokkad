"""Owner-authorized, per-loan commit of explicitly reviewed v2 opening evidence.

Source extraction/approval UI is a separate boundary. This command never infers
missing balances, dates, custody or mappings from a raw dump.
"""
from copy import deepcopy
from datetime import date, datetime, time
from decimal import Decimal, ROUND_HALF_EVEN
from zoneinfo import ZoneInfo

from dateutil.relativedelta import relativedelta
from django.db import connection, transaction

from apps.orgs.audit import AuditLog
from apps.orgs.models import Company
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.domain import DisbursalPolicySnapshot
from .event_recording import _persist_locked_event
from .history_contract import POLICY, digest, validate
from .history_import import balance_values
from .history_setup import preview_history_setup, require_history_setup_access
from .import_identity import find_source_origin, source_binding_id
from .opening_evidence import OpeningEvidenceError, opening_event_payload
from .opening_obligations import persist_opening_repayment_schedule
from .opening_validation import COLLECTION_PROFILE, validate_opening

PROFILE = "loan-opening-commit/1"


def _document(review, setup):
    result = validate_opening(review)
    if result["profile"] != COLLECTION_PROFILE or not result["document_reconciled"]:
        raise OpeningEvidenceError("A reconciled v2 review is required; unresolved loans remain held.")
    required_setup = {"tenure_months", "source_license_number", "policy"}
    if (type(setup) is not dict or not required_setup <= set(setup)
            or set(setup) - required_setup - {"legacy_license_evidence", "local_loan_number"}):
        raise OpeningEvidenceError("Supply reviewed original tenure, source licence number and servicing policy.")
    if "local_loan_number" in setup:
        from .history_setup import _text
        _text(setup["local_loan_number"], "Destination loan number", 64)
    if "legacy_license_evidence" in setup:
        from .history_setup import _text
        _text(setup["legacy_license_evidence"], "Legacy licence evidence", 255)
    validate(setup["policy"], schema=POLICY, path="setup.policy")
    policy = DisbursalPolicySnapshot.from_dict(setup["policy"])
    if policy.valuation_method.value != "LATEST_APPRAISAL":
        raise OpeningEvidenceError("Opening commit currently requires reviewed appraisals.")
    tenure = setup["tenure_months"]
    if type(tenure) is not int or not 1 <= tenure <= 1200:
        raise OpeningEvidenceError("Original tenure must be explicitly reviewed; unknown is not three months.")
    original = date.fromisoformat(review["terms"]["original_date"])
    if original + relativedelta(months=tenure) != date.fromisoformat(review["terms"]["maturity_date"]):
        raise OpeningEvidenceError("Original tenure and reviewed maturity must agree.")
    return deepcopy({"profile": PROFILE, "review": review, "setup": setup})


def _create(model, *, exclude=(), **values):
    obj = model(**values)
    obj.full_clean(exclude=exclude)
    obj.save()
    return obj


def _write(*, workspace_id, actor, document, restoration=None):
    # Workspace lock serializes both financial-origin writers, including replay.
    workspace = Company.all_objects.select_for_update().get(pk=workspace_id)
    require_history_setup_access(workspace_id, actor)
    review, supplied = document["review"], document["setup"]
    mapping, source, terms = review["mapping"], review["source"], review["terms"]
    if mapping["workspace_id"] != workspace_id:
        raise OpeningEvidenceError("Opening destination must match the authorized Workspace.")
    binding_id = source_binding_id(source["namespace"], source["loan_id"], mapping["borrower_source_system"])
    checksum = digest(document)
    existing = find_source_origin(workspace_id=workspace_id, namespace=source["namespace"],
        source_id=source["loan_id"], borrower_source_system=mapping["borrower_source_system"])
    if existing:
        if existing.source_sha256 != checksum or existing.document != document:
            raise OpeningEvidenceError("This source loan already has a different accepted financial origin.")
        if restoration is not None and existing.references.get("restore") != restoration:
            raise OpeningEvidenceError("This source loan already has a different accepted restoration or opening.")
        return existing, deepcopy(existing.references["summary"])
    setup = preview_history_setup(workspace_id=workspace_id, actor=actor,
        revision_id=mapping["licence_revision_id"], series_id=mapping["series_id"],
        product_version_id=mapping["product_version_id"], source_namespace=source["namespace"],
        source_loan_id=binding_id, source_loan_number=source["number"],
        source_license_number=supplied["source_license_number"], disbursed_on=date.fromisoformat(terms["original_date"]),
        tenure_months=supplied["tenure_months"], calculation_contract_version=terms["rule_id"],
        operational_grace_days=terms["grace_days"], legacy_license_evidence=supplied.get("legacy_license_evidence"),
        local_loan_number=supplied.get("local_loan_number"))
    from apps.tenant_apps.party.models import Party
    from apps.tenant_apps.data_portability.children import parent_for
    try:
        borrower = Party.objects.select_for_update().get(pk=mapping["borrower_id"], workspace_id=workspace_id)
    except Party.DoesNotExist as exc:
        raise OpeningEvidenceError("Borrower must belong to the destination Workspace.") from exc
    parent = parent_for({"party_source_system": mapping["borrower_source_system"],
                         "party_external_id": mapping["borrower_external_id"]}, workspace_id)
    if parent is None or parent.party_id != borrower.pk:
        raise OpeningEvidenceError("Borrower must resolve the exact source Party identity.")
    principal = Decimal(review["balances"]["principal"])
    monthly = sum(Decimal(row["original_principal"]) * Decimal(row["monthly_rate"]) / 100 for row in review["collateral"])
    loan = _create(m.PawnLoan, workspace=workspace, license=setup["revision"].license,
        license_revision=setup["revision"], series=setup["series"], product_version=setup["product"], borrower=borrower,
        loan_number=setup["numbers"][0]["local_number"], state="ACTIVE", loan_date=date.fromisoformat(terms["original_date"]),
        principal_amount=principal, monthly_interest_rate=(monthly / principal * 100).quantize(Decimal("0.000001"), rounding=ROUND_HALF_EVEN),
        tenure_months=supplied["tenure_months"], created_by=actor, updated_by=actor)
    items = {}
    zone = ZoneInfo(review["cutover"]["timezone"])
    for row in review["collateral"]:
        # Only v2 review validation authorizes excluding this unknown field.
        item = _create(m.PawnCollateralItem, exclude={"gross_weight"} if row["gross_weight"] is None else (),
            workspace=workspace, loan=loan, description=row["description"], metal=row["metal"],
            gross_weight=Decimal(row["gross_weight"]) if row["gross_weight"] is not None else None,
            net_weight=Decimal(row["net_weight"]), purity_percentage=Decimal(row["purity"]),
            allocated_principal=Decimal(row["remaining_principal"]), monthly_interest_rate=Decimal(row["monthly_rate"]),
            custody_state="IN_VAULT")
        items[row["id"]] = item.pk
        valuation = row["valuation"]
        if valuation.get("status") == "UNVERIFIED":
            continue  # Source claims stay in the opening; never create an approved appraisal.
        _create(m.CollateralAppraisal, workspace=workspace, collateral_item=item, version=1,
            effective_at=datetime.combine(date.fromisoformat(valuation["date"]), time.min, tzinfo=zone),
            appraised_value=Decimal(valuation["amount"]), method="MIGRATION_REVIEW",
            evidence_reference=valuation["evidence_reference"], created_by=actor)
    _create(m.LoanPolicySnapshot, workspace=workspace, loan=loan, **supplied["policy"])
    cutover = date.fromisoformat(review["cutover"]["date"])
    event, _ = _persist_locked_event(loan, kind="MIGRATION_OPENING", effective_date=cutover,
        payload=opening_event_payload(loan, review=review, item_mapping=items), actor=actor)
    schedule = persist_opening_repayment_schedule(loan.pk, actor=actor)
    balance = balance_values(loan, cutover)
    if any(Decimal(balance[key]) != Decimal(review["balances"][key]) for key in balance):
        raise OpeningEvidenceError("Stored opening balances do not reconcile.")
    summary = {"state": loan.state, "loan_number": loan.loan_number, "source_number": source["number"],
        "as_of": cutover.isoformat(), "balance": balance, "collateral": len(items),
        "events": 1, "borrower_name": borrower.display_name, "coverage": "OPENING_POSITION"}
    if restoration is not None:
        from .opening_restore import _restore_servicing
        _restore_servicing(loan, actor=actor, evidence=restoration["document"]["evidence"], item_mapping=items)
        loan.refresh_from_db()
        as_of = date.fromisoformat(restoration["document"]["manifest"]["as_of"])
        summary.update(state=loan.state, as_of=as_of.isoformat(), balance=balance_values(loan, as_of),
            events=loan.loan_events.count(), coverage="OPENING_AND_SUPPORTED_SERVICING")
    references = {"mapping": mapping, "items": items, "events": {"opening": event.pk},
                  "schedule_id": schedule.pk, "summary": summary}
    if restoration is not None:
        references["restore"] = restoration
    origin = _create(m.HistoricalLoanImport, workspace=workspace, loan=loan,
        source_namespace=source["namespace"], source_id=binding_id, source_sha256=checksum, document=document,
        references=references, imported_by=actor)
    AuditLog.log("DATA_IMPORT", company=workspace, user=actor,
        description="Imported reviewed loan opening without reconstructing unavailable history.",
        data={"history": str(origin.public_id), "loan": loan.pk, "sha256": checksum, "profile": PROFILE})
    connection.check_constraints()
    return origin, summary


def preview_opening_import(*, workspace_id, actor, review, setup):
    require_history_setup_access(workspace_id, actor)
    document = _document(review, setup)
    with transaction.atomic():
        _, summary = _write(workspace_id=workspace_id, actor=actor, document=document)
        transaction.set_rollback(True)
    return {"sha256": digest(document), "summary": summary}


@transaction.atomic
def commit_opening_import(*, workspace_id, actor, review, setup, expected_sha256, confirmed=False):
    require_history_setup_access(workspace_id, actor)
    document = _document(review, setup)
    if confirmed is not True or expected_sha256 != digest(document):
        raise OpeningEvidenceError("Confirm the exact reviewed opening and setup fingerprint before commit.")
    return _write(workspace_id=workspace_id, actor=actor, document=document)


@transaction.atomic
def adopt_opening_source_number(*, workspace_id, actor, loan_id):
    """Replace an unused generated opening number; retain all accepted evidence."""
    from .history_setup import _check_number, _number, _text
    import uuid

    workspace = Company.all_objects.select_for_update().get(pk=workspace_id)
    require_history_setup_access(workspace_id, actor)
    loan = m.PawnLoan.objects.select_for_update().get(pk=loan_id, workspace_id=workspace_id)
    origin = m.HistoricalLoanImport.objects.get(loan=loan, workspace_id=workspace_id)
    if origin.document.get("profile") != PROFILE:
        raise OpeningEvidenceError("Only a reviewed opening has an adoptable source number.")
    number = origin.document["review"]["source"]["number"]
    _text(number, "Source loan number", 64)
    if loan.loan_number == number:
        return loan
    expected = _number(uuid.UUID(str(origin.source_namespace)), origin.source_id, "PAWN_LOAN")
    if loan.loan_number != expected or loan.state != "ACTIVE":
        raise OpeningEvidenceError("Only an active opening with its generated number may be corrected.")
    if list(loan.loan_events.values_list("event_kind", flat=True)) != ["MIGRATION_OPENING"]:
        raise OpeningEvidenceError("A serviced opening cannot be renumbered by this command.")
    if (m.LoanDocumentIssue.objects.filter(workspace_id=workspace_id,
            source_type="PawnLoan", source_id=str(loan.pk)).exists()
            or m.PawnCollateralLabelIssue.objects.filter(workspace_id=workspace_id,
                collateral_item__loan=loan, action="PRINT").exists()):
        raise OpeningEvidenceError("Issued documents must be reconciled before changing a loan number.")
    _check_number(workspace_id, number, "PAWN_LOAN")
    previous = loan.loan_number
    loan.loan_number, loan.updated_by = number, actor
    loan.full_clean()
    loan.save(update_fields=["loan_number", "updated_by", "updated_at"])
    AuditLog.log("DATA_IMPORT", company=workspace, user=actor, content_object=loan,
        description="Adopted the original source loan number for an unserviced opening.",
        data={"operation": "ADOPT_OPENING_SOURCE_NUMBER", "loan": loan.pk,
              "before": previous, "after": number, "history": str(origin.public_id)})
    return loan
