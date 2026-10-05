"""Bounded source-faithful recorded agreements, using ordinary financial writers."""
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid5

from django.core.exceptions import ValidationError
from django.db import connection
from django.utils import timezone

from apps.orgs.audit import AuditLog
from apps.tenant_apps.loans import models as m
from .history_contract import (
    PROFILE_V4, MANIFEST, HistoryError, canonical_document, validate, digest, decimal, money, encode,
)
from .portability_validation import HISTORICAL_INCONSISTENCY, OPERATIONAL_READINESS
from .history_setup import preview_history_setup
from .import_identity import find_source_origin, source_binding_id
from .recorded_collections import collection_balance, collection_state, recording_for


def inconsistent(message):
    raise HistoryError(message, category=HISTORICAL_INCONSISTENCY, code="CALCULATION_MISMATCH")


def unsupported(message):
    raise HistoryError(message + " Retain the source evidence and use a reviewed opening checkpoint or Loans recovery backup.",
        category=OPERATIONAL_READINESS, code="UNSUPPORTED_SOURCE_HISTORY")


def balances(loan, day):
    value = collection_balance(loan, day)
    return dict(principal=decimal(value.principal_outstanding),
        interest=decimal(value.interest_outstanding), fees=decimal(value.fees_outstanding))


def event_values(event, item_ids):
    """Actual immutable amounts and item balances, independent of allocation order."""
    values = event.payload["values"]
    if event.event_kind == "REPAYMENT":
        lines = event.repayment_allocation_lines.all()
        applied = "principal_applied"
    else:
        lines = event.principal_closing_lines.all()
        applied = "principal_settled"
    result = dict(principal=decimal(values["principal"]), interest=decimal(values["interest"]),
        fees=decimal(values.get("fees", "0")))
    result["allocations"] = sorted([dict(item=item_ids[line.collateral_item_id],
        before=decimal(line.balance_before), principal=decimal(getattr(line, applied)),
        after=decimal(line.balance_after)) for line in lines], key=lambda row: row["item"])
    return result


def check_event(source, event, item_ids):
    actual = event_values(event, item_ids)
    expected = {key: source[key] for key in ("principal", "interest", "fees")}
    expected["allocations"] = sorted(source["allocations"], key=lambda row: row["item"])
    if expected != actual or money(source["amount"]) != sum((money(actual[k]) for k in ("principal", "interest", "fees")), Decimal("0")):
        inconsistent("Source receipt amounts or item balances do not reconcile to the recorded agreement.")


def import_recorded_history(*, workspace, actor, document, mapping):
    """Internal: public history command owns owner authorization and Workspace lock."""
    from apps.tenant_apps.data_portability.children import parent_for
    from apps.tenant_apps.party.models import Party
    from .recorded_history import validate_input, _admit
    from .recorded_items import effective_rate
    source, manifest = document["loan"], document["manifest"]
    namespace = UUID(manifest["namespace"])
    binding = source_binding_id(namespace, source["id"], source["borrower"]["source_system"])
    checksum = digest(document)
    existing = find_source_origin(workspace_id=workspace.pk, namespace=namespace,
        source_id=source["id"], borrower_source_system=source["borrower"]["source_system"])
    if existing:
        if existing.source_sha256 != checksum or existing.references["mapping"] != mapping:
            raise HistoryError("This source loan already has different accepted history or mappings.",
                category=OPERATIONAL_READINESS, code="SOURCE_ALREADY_ACCEPTED")
        return existing, existing.references["summary"]
    start, cutoff = date.fromisoformat(source["disbursed_on"]), date.fromisoformat(manifest["as_of"])
    if not start <= cutoff <= timezone.localdate():
        inconsistent("Original date and cutover chronology disagree.")
    previous = start
    for row in source["events"]:
        day = date.fromisoformat(row["date"])
        if not previous <= day <= cutoff:
            inconsistent("Source transaction dates must be ordered between payout and cutover.")
        previous = day
        if money(row["amount"]) != sum((money(row[key]) for key in ("principal", "interest", "fees")), Decimal("0")):
            inconsistent("Source receipt total does not conserve principal, interest and fees.")
        if sum((money(line["principal"]) for line in row["allocations"]), Decimal("0")) != money(row["principal"]):
            inconsistent("Source item allocations do not conserve receipt principal.")
        if any(money(line["before"]) - money(line["principal"]) != money(line["after"]) for line in row["allocations"]):
            inconsistent("Source item balances do not conserve their principal reduction.")
    from .recorded_numbers import identity as number_identity
    alias = dict(scope=source["borrower"]["source_system"], licence=number_identity(source["licence_number"]),
        book=number_identity(source["book_reference"]), number=number_identity(source["number"]))
    if m.HistoricalLoanImport.objects.filter(workspace=workspace, source_namespace=namespace,
            references__source_alias=alias).exists():
        raise HistoryError("This source book and original number already have an accepted identity; reconcile the source ID.",
            category=OPERATIONAL_READINESS, code="SOURCE_ALREADY_ACCEPTED")
    for ref in m.PawnLoanEvent.objects.filter(workspace=workspace, event_kind="DISBURSAL",
            loan__policy_snapshot__basis="RECORDED_CONTRACT", payload__recording__source_claims__isnull=True).values_list("payload__recording__source_reference", flat=True):
        if isinstance(ref, str) and number_identity(ref) == number_identity(source["source_reference"]):
            raise HistoryError("This paper source reference is already recorded; reconcile its existing loan before import.",
                category=OPERATIONAL_READINESS, code="SOURCE_ALREADY_ACCEPTED")
    parent = parent_for(dict(party_source_system=source["borrower"]["source_system"],
        party_external_id=source["borrower"]["id"]), workspace.pk)
    if parent is None or parent.party_id != mapping["borrower_id"]:
        raise HistoryError("Borrower mapping must resolve the exact source Party identity.", code="BORROWER_MAPPING")
    borrower = Party.objects.select_for_update().get(workspace=workspace, pk=parent.party_id)
    item_positions = {row["id"]: str(index + 1) for index, row in enumerate(source["collateral"])}
    if len(item_positions) != len(source["collateral"]) or len({e["id"] for e in source["events"]}) != len(source["events"]):
        inconsistent("Source item and transaction identities must be unique.")
    close = source["events"][-1] if source["state"] == "CLOSED" and source["events"] else None
    if (bool(close) != (source["state"] == "CLOSED") or close and close["kind"] != "CLOSE"
            or any((e["closure"] is not None) != (e["kind"] == "CLOSE") for e in source["events"])):
        inconsistent("Closure evidence must match the final closed transaction.")
    setup = preview_history_setup(workspace_id=workspace.pk, actor=actor,
        revision_id=mapping["revision_id"], series_id=mapping["series_id"], product_version_id=mapping["product_version_id"],
        source_namespace=namespace, source_loan_id=binding, source_loan_number=source["number"],
        source_license_number=source["licence_number"], disbursed_on=date.fromisoformat(source["disbursed_on"]),
        tenure_months=source["tenure_months"], calculation_contract_version=source["calculation_contract"],
        operational_grace_days=source["grace_days"], legacy_license_evidence=source["legacy_license_evidence"],
        source_release_id=digest(binding + ":close") if close else "",
        source_release_number=close["closure"]["number"] if close and close["closure"] else "",
        historical_servicing=True)
    items = [dict(description=row["description"], metal=row["metal"], quantity=row["quantity"],
        gross_weight=row["gross_weight"], net_weight=row["net_weight"], purity=row["purity"],
        principal=row["principal"], rate=row["monthly_rate"]) for row in source["collateral"]]
    payout, monitor = source["payout"], source["monitoring"]
    from .recorded_items import monthly_interest
    principal = sum((money(i["principal"]) for i in items), Decimal("0"))
    advance = monthly_interest(items, money(source["currency_quantum"])) * payout["advance_months"]
    if money(payout["proceeds"]) != principal - advance - money(payout["document_charge"]):
        inconsistent("Source proceeds do not conserve principal less agreed advance interest and document charge.")
    # Book references may repeat; the durable source identity is namespace + scoped ID.
    reference = source["source_reference"]
    setup["source_claims"] = dict(namespace=str(namespace), id=source["id"], book_reference=source["book_reference"],
        number=source["number"], original_actor=source["original_actor"], profile=PROFILE_V4)
    data = dict(borrower_id=borrower.pk, series_id=setup["series"].pk, product_version_id=setup["product"].pk,
        number=setup["numbers"][0]["local_number"], date=source["disbursed_on"],
        principal=decimal(sum((money(i["principal"]) for i in items), Decimal("0"))),
        rate=decimal(effective_rate(items)), tenure=source["tenure_months"], advance_months=payout["advance_months"],
        cash_paid=payout["proceeds"], document_charge=payout["document_charge"], payout_basis=payout["basis"],
        source_reference=reference, description=items[0]["description"], metal=items[0]["metal"],
        quantity=sum(i["quantity"] for i in items), gross_weight=items[0]["gross_weight"], net_weight=items[0]["net_weight"],
        purity=items[0]["purity"], collateral=items, currency_quantum=source["currency_quantum"],
        monitoring_method=monitor["method"], monitoring_ltv=monitor["ltv"], monitoring_reason=monitor["reason"],
        complete_through=manifest["as_of"], final_state=source["state"], confirmed_history=True, confirmed_rule=True,
        entry_note="Source book and original claims retained in accepted loan-history/4 evidence.", events=[])
    for row in source["events"]:
        ids = [line["item"] for line in row["allocations"]]
        if len(set(ids)) != len(ids) or not set(ids) <= set(item_positions):
            inconsistent("Receipt allocation references duplicate or unknown source items.")
        value = dict(kind=row["kind"], date=row["date"], amount=row["amount"], reference=row["reference"],
            number="", rate=None, tenure=None, recipient="")
        if row["kind"] == "PAYMENT" and money(row["principal"]):
            value["item_principal_split"] = {item_positions[line["item"]]: line["principal"] for line in row["allocations"]}
        if row["closure"]:
            if row["closure"]["basis"] == "PAPER_SETTLEMENT" and (
                    row["closure"]["returned_at"] is not None or row["closure"]["collector"] is not None):
                inconsistent("An unconfirmed paper handover cannot also claim a return time or recipient.")
            stamp = row["closure"]["returned_at"]
            if stamp:
                when = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
                if timezone.localdate(when).isoformat() != row["date"] or when > timezone.now():
                    inconsistent("Source handover timestamp must match its transaction day and cannot be future dated.")
            value.update(number=setup["numbers"][1]["local_number"], recipient=row["closure"]["collector"],
                closure_basis=row["closure"]["basis"])
        data["events"].append(value)
    data = validate_input(data, historical_source=True)
    loan, _ = _admit(workspace, actor, data, uuid5(namespace, binding), historical_setup=setup)
    local_items = list(loan.collateral_items.order_by("pk"))
    item_map = {row["id"]: item.pk for row, item in zip(source["collateral"], local_items, strict=True)}
    reverse_items = {pk: key for key, pk in item_map.items()}
    events = list(loan.loan_events.filter(event_kind__in=("REPAYMENT", "RELEASE_RECEIPT")).order_by("effective_date", "pk"))
    event_map = {}
    for row, event in zip(source["events"], events, strict=True):
        check_event(row, event, reverse_items)
        event_map[row["id"]] = event.pk
    actual = balances(loan, date.fromisoformat(manifest["as_of"]))
    if actual != source["cutover"]:
        inconsistent("Source cutover balance does not reconcile to the recorded agreement.")
    connection.check_constraints()
    summary = dict(state=loan.state, loan_number=loan.loan_number, events=len(events), collateral=len(items),
        as_of=manifest["as_of"], balance=actual, borrower_name=borrower.display_name,
        source_number=source["number"], source_book=source["book_reference"], balance_basis="ELIGIBLE_COLLECTION")
    origin = m.HistoricalLoanImport.objects.create(workspace=workspace, loan=loan, source_namespace=namespace,
        source_id=binding, source_sha256=checksum, document=document,
        references=dict(mapping=mapping, items=item_map, events=event_map, summary=summary, source_alias=alias), imported_by=actor)
    AuditLog.log("DATA_IMPORT", company=workspace, user=actor, description="Imported reconciled recorded source agreement.",
        data=dict(history=str(origin.public_id), loan=loan.pk, sha256=checksum, profile=PROFILE_V4))
    return origin, summary


def _export_graph(loan):
    """Reject graphs outside this replay contract; never omit an operation."""
    items = list(loan.collateral_items.select_for_update().order_by("pk"))
    events = list(loan.loan_events.select_for_update().order_by("effective_date", "pk"))
    if not items or len(items) > 20 or not events or events[0].event_kind != "DISBURSAL":
        unsupported("Missing original recorded payout or unsupported item count.")
    if sum(e.event_kind == "DISBURSAL" for e in events) != 1 or any(e.event_kind not in
            ("DISBURSAL", "INTEREST_ACCRUAL", "REPAYMENT", "RELEASE_RECEIPT") for e in events):
        unsupported("Reversals, opening positions, renewals, auctions and corrections need wider portability.")
    if any(e.payload.get("history_correction") or money(e.payload.get("values", {}).get("interest_concession", "0")) for e in events):
        unsupported("Corrected or conceded settlements need wider portability.")
    closed = events[-1].event_kind == "RELEASE_RECEIPT"
    if closed != (loan.state == "CLOSED"):
        inconsistent("Loan state and the final settlement disagree.")
    closure_basis = events[-1].payload.get("release", {}).get("paper_closure", {}).get("closure_basis", "RETURNED")
    expected_custody = ("PAPER_CLOSED" if closure_basis == "PAPER_SETTLEMENT" else "WITH_CUSTOMER") if closed else "IN_VAULT"
    if any(i.custody_state != expected_custody for i in items):
        unsupported("Later or inconsistent collateral handover needs wider custody portability.")
    if any(i.renewed_from_id or i.current_storage_location_id or i.custody_state not in
            ("IN_VAULT", "WITH_CUSTOMER", "PAPER_CLOSED") or i.funding_pledge_items.exists() or i.storage_movements.exists() for i in items):
        unsupported("Connected custody, renewal or funding history needs wider portability.")
    recognized = Decimal("0")
    for index, event in enumerate(events):
        if event.event_kind == "INTEREST_ACCRUAL":
            if index + 1 == len(events) or events[index + 1].event_kind not in ("REPAYMENT", "RELEASE_RECEIPT") or events[index + 1].effective_date != event.effective_date:
                unsupported("Standalone interest recognition cannot be omitted from recorded source history.")
            frozen = event.payload.get("recorded_collection")
            if not frozen or frozen["profile"] != "recorded-anniversary/3":
                unsupported("The interest recognition is outside the shared monthly contract.")
            state = collection_state(loan, event.effective_date)
            if (frozen["months"] != state["months"] or money(frozen["calculated"]) != money(state["calculated"])
                    or money(frozen["advance"]) != money(state["advance"]) or money(frozen["already_recognized"]) != recognized):
                inconsistent("Frozen interest recognition disagrees with the source agreement.")
            recognized += money(event.payload["values"]["interest"])
            if recognized != max(Decimal("0"), money(state["calculated"]) - money(state["advance"])):
                inconsistent("Frozen interest recognition does not conserve calculated charges.")
    return items, events


def export_recorded_history(*, workspace_id, actor, loan):
    """Internal: ordinary export already holds owner authorization and aggregate locks."""
    from apps.tenant_apps.data_portability.models import WorkspaceNamespace, PartyIdentity
    from apps.tenant_apps.loans.selectors.transaction_completeness import transaction_completeness
    recording = recording_for(loan)
    if not recording or recording["collection_profile"] != "recorded-anniversary/3":
        unsupported("This recorded agreement requires a recorded-origination profile with reviewed shared-contract correction before export.")
    from .recorded_origination_evidence import validate_recorded_origination
    try:
        validate_recorded_origination(loan.disbursal_snapshot)
    except ValidationError as exc:
        inconsistent("Frozen recorded origination cannot be reconciled: " + str(exc))
    product = loan.product_version
    if (product.repayment_structure, product.amortisation_method, product.payment_frequency, product.extra_payment_rule) != (
            "FLEXIBLE_PARTIAL_PAYMENT", "NONE", "FLEXIBLE", "REDUCE_PRINCIPAL"):
        unsupported("This recorded source profile supports the flexible monthly payment contract.")
    items, events = _export_graph(loan)
    origin = m.HistoricalLoanImport.objects.filter(workspace_id=workspace_id, loan=loan).first()
    if origin and origin.document.get("manifest", {}).get("profile") != PROFILE_V4:
        unsupported("This recorded origin uses a different evidence contract.")
    namespace, _ = WorkspaceNamespace.objects.get_or_create(workspace_id=workspace_id)
    def identity(kind, pk):
        return str(uuid5(namespace.public_id, f"{kind}:{pk}"))
    if origin:
        document = deepcopy(origin.document)
        source = document["loan"]
        item_ids = {pk: key for key, pk in origin.references["items"].items()}
        source_events = {pk: row for row in source["events"] for pk in [origin.references["events"][row["id"]]]}
        accepted = origin.references["mapping"]
        if (accepted["borrower_id"] != loan.borrower_id or accepted["revision_id"] != loan.license_revision_id
                or accepted["series_id"] != loan.series_id or accepted["product_version_id"] != loan.product_version_id):
            inconsistent("The accepted source mapping no longer agrees with the loan.")
        cutoff = max(date.fromisoformat(document["manifest"]["as_of"]), events[-1].effective_date)
    else:
        if not loan.license_revision_id:
            unsupported("An explicit source licence revision mapping is required for portable history.")
        party, _ = PartyIdentity.objects.get_or_create(workspace_id=workspace_id, party=loan.borrower)
        item_ids = {i.pk: str(i.public_id) for i in items}
        source_events = {}
        cutoff = events[-1].effective_date
        funding = recording.get("funding", {})
        snapshot = loan.disbursal_snapshot
        source = dict(id=identity("loan", loan.pk), number=loan.loan_number,
            book_reference=loan.series.code, source_reference=recording["source_reference"], state=loan.state,
            borrower=dict(source_system="rokkad:" + str(namespace.public_id), id=str(party.public_id)),
            licence_number=loan.license_revision.license_number,
            legacy_license_evidence=("Recorded past payout; original validity unknown" if loan.license_revision.kind == "LEGACY_REFERENCE" else None),
            disbursed_on=loan.loan_date.isoformat(), tenure_months=loan.tenure_months,
            calculation_contract=loan.product_version.calculation_contract_version,
            grace_days=loan.product_version.operational_grace_days, contract=recording["collection_profile"],
            currency_quantum=decimal(loan.policy_snapshot.currency_quantum), original_actor=recording["original_actor"],
            collateral=[], payout=dict(advance_months=snapshot.advance_interest_periods,
                document_charge=decimal(snapshot.deducted_fees), proceeds=decimal(snapshot.net_disbursed), basis=funding.get("basis", "CASH")),
            monitoring=dict(method=recording["monitoring"]["valuation_method"], ltv=decimal(recording["monitoring"]["maximum_ltv_ratio"]),
                reason=recording["monitoring"]["reason"]), events=[], cutover={})
        document = dict(manifest=dict(profile=PROFILE_V4, namespace=str(namespace.public_id), as_of=cutoff.isoformat(),
            coverage="PARTIAL", exclusions=MANIFEST["properties"]["exclusions"]["const"]), loan=source)
        frozen = {r["item_id"]: r for r in recording["terms"]["collateral"]}
        tranches = {r["collateral_item_id"]: r for r in snapshot.evidence["tranches"]}
        for item in items:
            row, tranche = frozen[item.pk], tranches[item.pk]
            source["collateral"].append(dict(id=item_ids[item.pk], description=row["description"], metal=row["metal"], quantity=row["quantity"],
                gross_weight=decimal(row["gross_weight"]), net_weight=decimal(row["net_weight"]), purity=decimal(row["purity_percentage"]),
                principal=decimal(tranche["allocated_principal"]), monthly_rate=decimal(tranche["monthly_interest_rate"])))
    if set(item_ids) != {i.pk for i in items}:
        inconsistent("Source collateral membership changed.")
    coverage = transaction_completeness(loan, cutoff)
    if not coverage.complete:
        unsupported("Verify the complete source book through the export cutover before exporting full history.")
    # Retained claims must still agree with the immutable contract, not mutable appraisal values.
    frozen = {row["item_id"]: row for row in recording["terms"]["collateral"]}
    tranches = {row["collateral_item_id"]: row for row in loan.disbursal_snapshot.evidence["tranches"]}
    for row in source["collateral"]:
        pk = next(pk for pk, source_id in item_ids.items() if source_id == row["id"])
        actual = frozen[pk]
        for key, field in (("description", "description"), ("metal", "metal"), ("quantity", "quantity")):
            if row[key] != actual[field]: inconsistent("Frozen source item facts changed.")
        for key, field in (("gross_weight", "gross_weight"), ("net_weight", "net_weight"), ("purity", "purity_percentage")):
            if money(row[key]) != money(actual[field]): inconsistent("Frozen source item measurements changed.")
        if money(row["principal"]) != money(tranches[pk]["allocated_principal"]) or money(row["monthly_rate"]) != money(tranches[pk]["monthly_interest_rate"]):
            inconsistent("Frozen source item economics changed.")
    if (source["disbursed_on"] != loan.loan_date.isoformat() or source["tenure_months"] != loan.tenure_months
            or money(recording["terms"]["principal_amount"]) != loan.principal_amount):
        inconsistent("Frozen source loan terms changed.")
    source["events"] = []
    for event in events:
        if event.event_kind not in ("REPAYMENT", "RELEASE_RECEIPT"): continue
        if event.pk in source_events:
            row = deepcopy(source_events[event.pk])
            check_event(row, event, item_ids)
        else:
            detail = event.payload.get("repayment", {}) if event.event_kind == "REPAYMENT" else event.payload["release"]
            paper = detail.get("recording") or detail.get("paper_closure")
            row = dict(id=identity("event", event.pk), kind="PAYMENT" if event.event_kind == "REPAYMENT" else "CLOSE",
                date=event.effective_date.isoformat(), reference=(paper.get("receipt_reference") or paper.get("paper_reference")) if paper else "event:" + identity("event", event.pk),
                original_actor=paper.get("original_actor") if paper else identity("actor", event.created_by_id),
                capture_purpose="RECORD_COMPLETED" if paper else "PERFORM_NOW", closure=None, **event_values(event, item_ids))
            row["amount"] = decimal(sum((money(row[k]) for k in ("principal", "interest", "fees")), Decimal("0")))
            if event.event_kind == "RELEASE_RECEIPT":
                returned = list(event.release.items.values_list("returned_at", flat=True))
                if len(set(returned)) > 1:
                    unsupported("Distinct item handover times need wider custody portability.")
                row["closure"] = dict(number=detail["release_number"], collector=paper.get("collector_name") if paper else None,
                    returned_at=returned[0].isoformat() if returned and returned[0] else None,
                    basis=paper.get("closure_basis", "RETURNED") if paper else "RETURNED")
        source["events"].append(row)
    source["state"] = loan.state
    source["cutover"] = balances(loan, cutoff)
    document["manifest"]["as_of"] = cutoff.isoformat()
    validate(document)
    document = canonical_document(document)
    content = encode(document)
    AuditLog.log("DATA_EXPORT", company=loan.workspace, user=actor, description="Exported bounded recorded source history.",
        data=dict(loan=loan.pk, profile=PROFILE_V4, sha256=digest(document)))
    return content
