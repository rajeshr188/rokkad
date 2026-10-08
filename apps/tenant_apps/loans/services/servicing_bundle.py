"""Bounded portable Loans evidence, distinct from owner-only native recovery.

The historical admission command validates a complete source-local operation graph,
allocates fresh destination identities, and reconciles canonical readers under RLS.
It never copies source actors, switches capture mode, disables guards or posts cash
again. Published earlier history/opening profiles remain separate.
"""
import base64
from copy import deepcopy
from datetime import date
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import PurePosixPath
from uuid import UUID, uuid4, uuid5
from zipfile import ZipFile, ZIP_DEFLATED

from django.apps import apps
from django.core.files.base import ContentFile
from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone

from apps.orgs.access import resolve_workspace_access
from apps.orgs.audit import AuditLog
from apps.orgs.models import Company
from apps.tenant_apps.loans import models as m
from .history_setup import require_history_setup_access, _number, _check_number
from .history_contract import digest, dump, HistoryError
from .servicing_bundle_contract import PROFILE, ROWS, MAX_ROWS, MAX_BYTES, MAX_LOANS, EXCLUSIONS, ISSUE_FIELDS, row, decode, require, sha, read_bundle

KINDS = {name: apps.get_model("loans", name) for name in ROWS}
ACTORS = "accounts.CustomUser"
EXTERNAL = {ACTORS, "orgs.Company", "party.Party", "loans.LoanLicense", "loans.LoanLicenseRevision", "loans.LoanSeries", "loans.LoanProductVersion", "loans.PawnMetalInterestRatePolicy"}
SUPPORTED_EVENTS = {"DISBURSAL", "MIGRATION_OPENING", "RENEWAL_OPENING", "REPAYMENT", "INTEREST_ACCRUAL", "RELEASE_RECEIPT", "RENEWAL_SETTLEMENT", "AUCTION_RECOVERY", "REVERSAL"}


def _access(workspace_id, actor, *, exporting=False):
    workspace = require_history_setup_access(workspace_id, actor, read_only=exporting)
    access = resolve_workspace_access(actor=actor, workspace=workspace)
    access.require("data.export")
    if not exporting:
        for action in ("data.create", "loan.repay", "loan.release", "loan.approve", "loan.disburse", "workspace.settings.manage"):
            access.require(action)
    return workspace


def _connected(workspace_id, loan_id):
    ids = {loan_id}
    for _ in range(MAX_LOANS):
        old = set(ids)
        for pair in m.PawnLoanRenewal.objects.filter(workspace_id=workspace_id).filter(Q(source_loan_id__in=ids) | Q(successor_loan_id__in=ids)).values_list("source_loan_id", "successor_loan_id"):
            ids.update(pair)
        batches = m.PawnReleaseBatchLine.objects.filter(workspace_id=workspace_id, release__loan_id__in=ids).values_list("batch_id", flat=True)
        ids.update(m.PawnReleaseBatchLine.objects.filter(workspace_id=workspace_id, batch_id__in=batches).values_list("release__loan_id", flat=True))
        require(len(ids) <= MAX_LOANS, "Connected renewal/release graph exceeds twenty loans; use exact Workspace recovery.")
        if ids == old:
            return ids
    raise HistoryError("Connected servicing graph exceeds its bound.")


def _collect(workspace_id, ids):
    selected = {kind: {} for kind in KINDS}
    selected["PawnLoan"] = {o.pk:o for o in m.PawnLoan.objects.select_for_update().filter(workspace_id=workspace_id, pk__in=ids)}
    require(set(selected["PawnLoan"]) == ids, "A connected loan is missing from this Workspace.")
    # Follow only the frozen inventory's typed relationships. Root closure is
    # explicit above; this never pulls an unrelated loan into an accepted graph.
    for _ in range(len(KINDS)):
        before = sum(map(len, selected.values()))
        for kind, model in KINDS.items():
            if kind == "PawnLoan":
                continue
            query = Q(pk__in=selected[kind])
            for key, spec in ROWS[kind].items():
                parent = spec.get("reference", "").removeprefix("loans.")
                if parent in selected and selected[parent]:
                    query |= Q(**{key+"__in": list(selected[parent])})
            selected[kind].update({o.pk:o for o in model.objects.select_for_update().filter(workspace_id=workspace_id).filter(query)[:MAX_ROWS+1]})
        # Include referenced ancestors such as retained archives and release batches.
        for kind, objects in tuple(selected.items()):
            for obj in tuple(objects.values()):
                for key, spec in ROWS[kind].items():
                    parent = spec.get("reference", "").removeprefix("loans.")
                    pk = getattr(obj, key) if parent in selected else None
                    if pk is None or pk in selected.get(parent, {}):
                        continue
                    require(parent != "PawnLoan" or pk in ids, "An operation references a loan outside the connected graph.")
                    value = KINDS[parent].objects.filter(workspace_id=workspace_id, pk=pk).first()
                    require(value is not None, "Missing or foreign servicing ancestor.")
                    selected[parent][pk] = value
        count = sum(map(len, selected.values()))
        for evidence in tuple(selected['HistoricalLoanEvidence'].values()):
            selected['HistoricalLoanEvidence'].update({r.pk:r for r in m.HistoricalLoanEvidence.objects.filter(workspace_id=workspace_id, source_namespace=evidence.source_namespace, source_system=evidence.source_system, source_id=evidence.source_id)})
        count = sum(map(len, selected.values()))
        require(count <= MAX_ROWS, "Servicing graph exceeds five thousand rows.")
        if before == count:
            return selected
    raise HistoryError("Servicing graph did not resolve within the fixed inventory.")


def _position(loan, day):
    require(not any(snapshot.evidence.get("recording", {}).get("origination_correction")
        for snapshot in loan.disbursal_snapshots.all()),
        "Origination correction retains native source IDs; use exact Workspace recovery until a remapping profile is supported.")
    from apps.tenant_apps.loans.selectors.servicing_contract import get_servicing_position
    from apps.tenant_apps.loans.selectors.exposure import get_pawn_loan_exposure
    from apps.tenant_apps.loans.selectors.transaction_completeness import transaction_completeness
    from apps.tenant_apps.loans.selectors.balances import get_pawn_loan_balance
    events = tuple(loan.loan_events.order_by("pk"))
    require(events and len(events) <= 1000 and all(e.event_kind in SUPPORTED_EVENTS and e.effective_date <= day for e in events), "Unsupported or future financial event graph.")
    from .servicing_bundle_validation import reconcile
    reconcile(loan, events)
    position = get_servicing_position(loan, as_of_date=day, operation="NOTICE")
    balance = get_pawn_loan_balance(loan, as_of_date=day)
    exposure = get_pawn_loan_exposure(loan.pk, as_of_date=day)
    require(not exposure.integrity_findings, "Servicing obligations do not reconcile: " + "; ".join(exposure.integrity_findings))
    require(loan.state in {"ACTIVE", "CLOSED", "CANCELLED"}, "Portable servicing requires an admitted or reversed loan.")
    if loan.state in {"CLOSED", "CANCELLED"}:
        require(balance.total_due == 0, "Closed/reversed source loan has remaining financial debt.")
    from .recorded_origination_evidence import validate_recorded_origination
    for snapshot in loan.disbursal_snapshots.all():
        if snapshot.basis == "RECORDED":
            # Historical superseded terms remain source claims; validate the active
            # contract against the active origin, without applying later corrections
            # to a superseded original snapshot.
            if snapshot.pk == loan.disbursal_snapshot_id:
                validate_recorded_origination(snapshot)
    return dict(state=loan.state, contract=position.contract.profile,
        financial_history_from=position.contract.financial_history_from.isoformat(),
        recorded={key:str(getattr(balance, key+"_outstanding")) for key in ("principal", "interest", "fees")},
        collection={key:str(getattr(position.balance, key+"_outstanding")) for key in ("principal", "interest", "fees")},
        exposure=str(exposure.total_economic_exposure), interest_conceded=str(balance.interest_conceded),
        custody=[dict(id=i.pk, state=i.custody_state, predecessor=i.renewed_from_id) for i in loan.collateral_items.order_by("pk")],
        coverage=transaction_completeness(loan, day).evidence())


def _add_file(files, claims, value, *, expected=None):
    with value.open("rb") as stream:
        content = stream.read(MAX_BYTES+1)
    checksum = sha(content)
    require(len(content) <= MAX_BYTES and (not expected or checksum == expected), "Retained source file is missing or corrupt.")
    require(sum(map(len, files.values())) + (0 if checksum in files else len(content)) <= MAX_BYTES, "Servicing file evidence exceeds 32 MiB.")
    files[checksum] = content
    claim = claims.setdefault(checksum, dict(sha256=checksum, size=len(content), source_names=[]))
    if value.name not in claim["source_names"]:
        claim["source_names"].append(value.name)
    return checksum


@transaction.atomic
def export_servicing_bundle(*, workspace_id, actor, loan_id):
    workspace = _access(workspace_id, actor, exporting=True)
    Company.all_objects.select_for_update().get(pk=workspace_id)
    _access(workspace_id, actor, exporting=True)
    m.PawnLoan.objects.get(pk=loan_id, workspace_id=workspace_id)
    selected = _collect(workspace_id, _connected(workspace_id, loan_id))
    require(not any(snapshot.evidence.get("recording", {}).get("origination_correction")
        for snapshot in selected['PawnLoanDisbursalSnapshot'].values()),
        "Origination correction retains native source IDs; use exact Workspace recovery until a remapping profile is supported.")
    require(not any(item.funding_pledge_items.exists() or item.storage_movements.exists() for item in selected['PawnCollateralItem'].values()), 'Funding or storage history requires exact Workspace recovery; this servicing profile cannot omit it.')
    from apps.tenant_apps.data_portability.models import WorkspaceNamespace, PartyIdentity
    namespace, _ = WorkspaceNamespace.objects.get_or_create(workspace_id=workspace_id)
    tables = {kind:[row(kind, obj) for obj in sorted(objects.values(), key=lambda o:o.pk)] for kind, objects in selected.items()}
    for kind, objects in selected.items():
        for obj in objects.values():
            for key, spec in ROWS[kind].items():
                target = spec.get("reference")
                if target and target not in EXTERNAL and target.removeprefix("loans.") not in selected:
                    require(getattr(obj, key) is None, "Funding, storage or standing item-policy references require a wider servicing profile.")
    files, claims, documents = {}, {}, []
    for kind, objects in selected.items():
        for obj in objects.values():
            for key, spec in ROWS[kind].items():
                if spec["type"] == "FileField" and getattr(obj, key).name:
                    expected = getattr(obj, "artifact_sha256", None) if key == "artifact" else getattr(obj, "attachment_sha256", None) if key == "attachment" else getattr(obj, "sha256", None)
                    _add_file(files, claims, getattr(obj, key), expected=expected)
    targets = {kind:set(objects) for kind, objects in selected.items()}
    targets["PawnLoanAuctionNotice"] = targets["PawnLoanAuction"]
    query = Q(pk__in=[])
    for kind, pks in targets.items():
        query |= Q(source_type=kind, source_id__in=[str(pk) for pk in pks])
    for issue in m.LoanDocumentIssue.objects.filter(workspace_id=workspace_id).filter(query).order_by("pk"):
        checksum = _add_file(files, claims, issue.artifact, expected=issue.pdf_hash)
        original_issue = {key:getattr(issue,key) for key in ISSUE_FIELDS}
        original_issue.update(artifact=issue.artifact.name,issued_at=issue.issued_at.isoformat())
        documents.append(dict(id=issue.pk, source_type=issue.source_type, source_id=issue.source_id, document_type=issue.document_type,source_issue=original_issue,
            issued_at=issue.issued_at.isoformat(), issued_by=issue.issued_by_id, source_fingerprint=issue.source_fingerprint,
            payload_hash=issue.payload_hash, layout_hash=issue.layout_hash, pdf_sha256=checksum,
            source_snapshot=issue.source_snapshot, filename=PurePosixPath(issue.artifact.name).name))
    setup, positions = {}, {}
    for loan in selected["PawnLoan"].values():
        party, _ = PartyIdentity.objects.get_or_create(workspace_id=workspace_id, party=loan.borrower)
        product = loan.product_version
        setup[str(loan.pk)] = dict(borrower=dict(source_system="rokkad:"+str(namespace.public_id), id=str(party.public_id)),
            licence_number=loan.license_revision.license_number if loan.license_revision_id else loan.license.license_number,
            licence_evidence='REVISION' if loan.license_revision_id else 'SOURCE_REFERENCE',
            product={key:getattr(product,key) for key in ("repayment_structure", "amortisation_method", "payment_frequency", "extra_payment_rule", "calculation_contract_version", "operational_grace_days")})
        positions[str(loan.pk)] = _position(loan, timezone.localdate())
    document = dict(profile=PROFILE, namespace=str(namespace.public_id), workspace_id=workspace_id, root_loan_id=loan_id,
        as_of=timezone.localdate().isoformat(), coverage="SOURCE_FINANCIAL_AND_CUSTODY_GRAPH", exclusions=EXCLUSIONS,
        tables=tables, setup=setup, positions=positions, files=claims, documents=documents)
    _source_graph(document)
    document["sha256"] = sha(dump(document).encode())
    raw = dump(document).encode()
    require(len(raw)+sum(map(len, files.values())) <= MAX_BYTES, "Expanded servicing bundle exceeds 32 MiB.")
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", raw)
        for key, content in files.items():
            archive.writestr("files/"+key, content)
    result = buffer.getvalue()
    read_bundle(result)
    AuditLog.log("DATA_EXPORT", company=workspace, user=actor, description="Exported bounded connected Loans servicing evidence and original file bytes.", data=dict(root_loan=loan_id, loans=len(positions), profile=PROFILE, sha256=sha(result)))
    return result


def _source_graph(document):
    try:
        return _validate_source_graph(document)
    except (KeyError, TypeError, ValueError, InvalidOperation, AttributeError, RecursionError) as exc:
        if isinstance(exc, HistoryError):
            raise
        raise HistoryError('Invalid servicing evidence: ' + str(exc)) from exc


def _validate_source_graph(document):
    """Resolve every reference and source hash before destination writes."""
    tables = document["tables"]
    source_files = {name:claim for claim in document['files'].values() for name in claim['source_names']}
    for kind, rows in tables.items():
        for source in rows:
            if kind=='PawnCollateralPhoto':
                require(source['mime_type'] in {'image/jpeg','image/png','image/webp'}, 'Unsupported portable collateral photograph type.')
            if kind=='HistoricalLoanAttachment':
                require(source['mime_type'] in {'image/jpeg','image/png','image/webp','application/pdf','application/octet-stream'}, 'Unsupported portable historical attachment type.')
            for key, spec in ROWS[kind].items():
                if spec['type']=='FileField' and source[key]:
                    claim = source_files.get(source[key])
                    expected = source.get('artifact_sha256') if key=='artifact' else source.get('attachment_sha256') if key=='attachment' else source.get('sha256')
                    require(claim is not None and expected==claim['sha256'] and (source.get('byte_size') is None or source['byte_size']==claim['size']), 'Source file metadata differs from its retained bytes.')
    from .servicing_bundle_coverage import validate_source_coverage
    validate_source_coverage(document)
    ids = {kind:{r["id"] for r in rows} for kind, rows in tables.items()}
    require(len(document['documents']) <= 200, 'Portable document inventory exceeds two hundred copies.')
    document_fields = {'id','source_type','source_id','document_type','issued_at','issued_by','source_fingerprint','payload_hash','layout_hash','pdf_sha256','source_snapshot','filename','source_issue'}
    for claim in document['documents']:
        require(type(claim) is dict and set(claim) == document_fields, 'Unsupported source document claim.')
        kind = 'PawnLoanAuction' if claim['source_type'] == 'PawnLoanAuctionNotice' else claim['source_type']
        require(kind in ids and type(claim['source_id']) is str and claim['source_id'].isdigit() and int(claim['source_id']) in ids[kind], 'Source document references a missing operation.')
        require(claim['pdf_sha256'] in document['files'] and type(claim['source_snapshot']) is dict, 'Source document is missing its original bytes/snapshot.')
        original_issue = claim['source_issue']
        require(type(original_issue) is dict and set(original_issue)==set(ISSUE_FIELDS)
            and original_issue['workspace_id']==document['workspace_id']
            and all(original_issue[key]==claim[key] for key in ('id','source_type','source_id','document_type','issued_at','source_fingerprint','payload_hash','layout_hash','source_snapshot'))
            and original_issue['pdf_hash']==claim['pdf_sha256'] and original_issue['issued_by_id']==claim['issued_by'], 'Source issue evidence differs from its file claim.')
    require(set(document["setup"]) == set(document["positions"]) == {str(pk) for pk in ids["PawnLoan"]}, "Portable setup/position coverage differs from its loans.")
    product_fields = {'repayment_structure', 'amortisation_method', 'payment_frequency', 'extra_payment_rule', 'calculation_contract_version', 'operational_grace_days'}
    for setup in document['setup'].values():
        require(type(setup) is dict and set(setup)=={'borrower','licence_number','licence_evidence','product'}, 'Unsupported portable setup fields.')
        require(type(setup['borrower']) is dict and set(setup['borrower'])=={'source_system','id'}
            and all(type(v) is str and v for v in setup['borrower'].values()), 'Invalid source Party identity.')
        require(type(setup['licence_number']) is str and setup['licence_number'] and setup['licence_evidence'] in {'REVISION','SOURCE_REFERENCE'}, 'Invalid source licence evidence.')
        require(type(setup['product']) is dict and set(setup['product'])==product_fields, 'Unsupported portable product fields.')
    # The next admission adds one source packet. Reject excessive ancestry here,
    # before it could create a loan whose original documents cannot be displayed.
    for origin in tables['HistoricalLoanImport']:
        packet = origin['references'].get('portable')
        for _ in range(7):
            if not packet:
                break
            ancestor = next((r for r in packet['document']['tables']['HistoricalLoanImport'] if r['loan_id']==packet['source_loan_id']), None)
            packet = ancestor['references'].get('portable') if ancestor else None
        require(not packet, 'Source document ancestry exceeds eight transfers; use exact Workspace recovery.')
    from .event_recording import _fingerprint
    for kind, rows in tables.items():
        for source in rows:
            for key, spec in ROWS[kind].items():
                target = spec.get("reference", "").removeprefix("loans.")
                if target in ids and source[key] is not None:
                    require(source[key] in ids[target], "Unresolved portable reference: " + kind + "." + key)
                elif spec.get("reference") and spec["reference"] not in EXTERNAL:
                    require(source[key] is None, "Unsupported external financial/custody reference.")
            if kind == "PawnLoanEvent":
                require(source["event_kind"] in SUPPORTED_EVENTS and source["effective_date"] <= document["as_of"], "Unsupported portable event/date.")
                require(source["payload_fingerprint"] == _fingerprint(source["payload"]) and source["idempotency_key"] == f"loans:{source['loan_id']}:{source['event_kind']}:{source['payload_fingerprint']}", "Source financial event hash differs.")
                payload = source["payload"]
                require(payload.get("event_kind") == source["event_kind"] and payload.get("effective_date") == source["effective_date"] and payload.get("source_identity", {}).get("loan_id") == source["loan_id"], "Financial event envelope differs from its parent.")
                require(payload.get("currency") == "INR" and type(payload.get("values")) is dict and payload["values"], "Unsupported economic event envelope.")
                require(all(Decimal(str(v)).is_finite() and Decimal(str(v)) >= 0 for v in payload["values"].values()), "Invalid portable economic amount.")
            if kind == "PawnLoanApprovalSnapshot":
                require(source["fingerprint"] == digest(source["payload"]), "Source approval hash differs.")
            if kind in {'HistoricalLoanImport', 'HistoricalLoanEvidence'}:
                require(source['source_sha256']==digest(source['document']), 'Source accepted-document hash differs.')
            if kind == 'StatutoryAuctionNotice':
                require(source['snapshot_sha256']==digest(source['snapshot']), 'Source statutory snapshot hash differs.')
    loans = {r["id"]:r for r in tables["PawnLoan"]}
    items = {r["id"]:r for r in tables["PawnCollateralItem"]}
    events = {r["id"]:r for r in tables["PawnLoanEvent"]}
    for event in events.values():
        target = event["reversal_of_id"]
        if target:
            require(events[target]["loan_id"] == event["loan_id"] and events[target]["id"] < event["id"] and event["event_kind"] == "REVERSAL", "Invalid portable reversal lineage.")
            require(event["payload"]["values"] == events[target]["payload"]["values"], "Portable reversal changes its original economic values.")
    for kind, rows in tables.items():
        for source in rows:
            loan_ids = {source[k] for k in ("loan_id", "source_loan_id", "successor_loan_id") if k in source and source[k] is not None}
            if source.get("collateral_item_id"):
                loan_ids.add(items[source["collateral_item_id"]]["loan_id"])
            if source.get("loan_event_id"):
                loan_ids.add(events[source["loan_event_id"]]["loan_id"])
            require(kind in {"PawnLoanRenewal", "PawnLoanPrincipalOpeningLine"} or len(loan_ids) <= 1, "Portable child crosses loan ownership.")
    # Original aliases and proof remain unchanged; only explicit destination keys
    # will be adapted. Never trust a recomputed ZIP digest as financial validation.
    return loans


def _mapping(document, workspace_id, mapping):
    loans = _source_graph(document)
    require(type(mapping) is dict and set(mapping) == {str(pk) for pk in loans}, "Select destination mappings for every connected loan.")
    from apps.tenant_apps.party.models import Party
    from apps.tenant_apps.data_portability.children import parent_for
    result = {}
    for source_id, values in mapping.items():
        require(type(values) is dict and set(values) == {"borrower_id", "revision_id", "series_id", "product_version_id"} and all(type(v) is int and v > 0 for v in values.values()), "Select borrower, licence revision, series and product for each loan.")
        revision = m.LoanLicenseRevision.objects.select_related("license").get(workspace_id=workspace_id, pk=values["revision_id"])
        series = m.LoanSeries.objects.get(workspace_id=workspace_id, pk=values["series_id"], license_id=revision.license_id)
        product = m.LoanProductVersion.objects.get(workspace_id=workspace_id, pk=values["product_version_id"])
        require(product.status in {'ACTIVE', 'RETIRED'}, 'Select an active or retired compatible servicing product.')
        borrower = Party.objects.get(workspace_id=workspace_id, pk=values["borrower_id"])
        source = document["setup"][source_id]
        require(revision.license_number == source["licence_number"], "Destination original licence identity differs.")
        require(all(getattr(product, k) == v for k,v in source["product"].items()), "Destination product cannot continue the frozen source agreement.")
        original = date.fromisoformat(loans[int(source_id)]["loan_date"])
        require(product.minimum_tenor_months <= loans[int(source_id)]["tenure_months"] <= product.maximum_tenor_months, "Destination tenure bounds differ.")
        parent = parent_for({"party_source_system":source["borrower"]["source_system"], "party_external_id":source["borrower"]["id"]}, workspace_id)
        require(parent is not None and parent.party_id == borrower.pk, "Import the exact source Party identity before restoring servicing.")
        if document["positions"][source_id]["contract"].startswith("native-"):
            require(source['licence_evidence'] == 'REVISION' and loans[int(source_id)]['license_revision_id'] is not None, 'Native approval requires an evidenced original licence revision.')
            require(revision.kind != "LEGACY_REFERENCE" and revision.issued_on and revision.issued_on <= original <= revision.expires_on, "A native approved source needs a matching evidenced original licence revision.")
        result[source_id] = dict(values, license_id=revision.license_id)
    return result


# Named JSON keys are owned by the supported evidence profiles. Unrecognised
# numeric source claims are retained as claims, never assigned as foreign keys.
JSON_REFS = {
    "loan_id":"PawnLoan", "source_loan_id":"PawnLoan", "successor_loan_id":"PawnLoan",
    "collateral_item_id":"PawnCollateralItem", "item_id":"PawnCollateralItem", "predecessor_collateral_item_id":"PawnCollateralItem",
    "opening_event_id":"PawnLoanEvent", "original_event_id":"PawnLoanEvent", "source_event_id":"PawnLoanEvent", "loan_event_id":"PawnLoanEvent", "loan_event":"PawnLoanEvent",
    "recognition_event_id":"PawnLoanEvent", "reversal_event_id":"PawnLoanEvent", "settlement_event_id":"PawnLoanEvent",
    "root_event_id":"PawnLoanEvent", "target_event_id":"PawnLoanEvent", "paired_event_id":"PawnLoanEvent",
    "policy_snapshot_id":"LoanPolicySnapshot", "approval_snapshot_id":"PawnLoanApprovalSnapshot", "disbursal_snapshot_id":"PawnLoanDisbursalSnapshot",
    "successor_approval_snapshot_id":"PawnLoanApprovalSnapshot",
    "release_id":"PawnLoanRelease", "release_reversal_id":"PawnLoanReleaseReversal", "auction_id":"PawnLoanAuction", "auction_reversal_id":"PawnLoanAuctionReversal",
    "renewal_id":"PawnLoanRenewal", "renewal_reversal_id":"PawnLoanRenewalReversal", "batch_id":"PawnReleaseBatch",
    "accrual_id":"PawnLoanInterestAccrual", "catch_up_accrual_id":"PawnLoanInterestAccrual", "schedule_version_id":"RepaymentScheduleVersion", "schedule_id":"RepaymentScheduleVersion",
    "obligation_id":"RepaymentObligation", "review_id":"LoanTransactionReview",
}


def _adapt(value, *, refs, external, numbers, event_keys, opaque=False):
    if isinstance(value, list):
        return [_adapt(v, refs=refs, external=external, numbers=numbers, event_keys=event_keys, opaque=opaque) for v in value]
    if not isinstance(value, dict) or opaque:
        return deepcopy(value)
    result = {}
    for key, val in value.items():
        if key in {"source", "historical_approval", "source_evidence", "restore", "portable"}:
            result[key] = deepcopy(val)
        elif key == "valuation_context" or key == "origination_rates":
            result[key] = deepcopy(val)
            if isinstance(val, dict):
                result[key].setdefault("source_workspace_id", external["source_workspace_id"])
        elif key in {'archive', 'archive_admission'} and isinstance(val, dict) and type(val.get('id')) is int:
            result[key] = deepcopy(val)
            result[key]['id'] = refs['HistoricalLoanEvidence'][val['id']]
            if 'snapshot_ids' in val:
                result[key]['snapshot_ids'] = [refs['HistoricalLoanEvidence'][pk] for pk in val['snapshot_ids']]
            if 'snapshots' in val:
                result[key]['snapshots'] = [[refs['HistoricalLoanEvidence'][pk], fingerprint] for pk, fingerprint in val['snapshots']]
        elif key == 'custody_restatement' and isinstance(val, dict):
            result[key] = deepcopy(val)
            for field in ('superseded', 'replacements'):
                if field in val:
                    result[key][field] = [refs['PawnCollateralCustodyEvent'][pk] for pk in val[field]]
        elif key == 'batch_correction' and isinstance(val, dict):
            result[key] = deepcopy(val)
            result[key]['id'] = refs['PawnReleaseBatch'][val['id']]
        elif key in JSON_REFS and type(val) is int:
            require(val in refs[JSON_REFS[key]], "Unresolved named financial reference: " + key)
            result[key] = refs[JSON_REFS[key]][val]
        elif key in external and type(val) is int:
            result[key] = external[key]
        elif key in {'loan_number','source_loan_number','successor_loan_number','release_number','auction_number','renewal_number'} and type(val) is str:
            scope = 'loan_number' if key in {'source_loan_number','successor_loan_number'} else key
            result[key] = numbers.get((scope,val),val)
        elif key in {"item_mapping", "item_principal_split"}:
            if key == "item_principal_split":
                result[key] = {str(refs["PawnCollateralItem"][int(pk)]):amount for pk, amount in val.items()}
                continue
            result[key] = {name:refs["PawnCollateralItem"][pk] for name, pk in val.items()}
        elif key == "original_idempotency_key":
            require(val in event_keys, "Unresolved original financial event key.")
            result[key] = event_keys[val]
        else:
            result[key] = _adapt(val, refs=refs, external=external, numbers=numbers, event_keys=event_keys)
    if result.get("profile") in {"loan-terminal-admission/1", "archive-terminal-admission/1", "loan-terminal-review/1"}:
        data = result["data"]
        data["number"] = numbers.get(("loan_number", value["data"]["number"]), data["number"])
        if result["profile"] == "loan-terminal-review/1":
            from .terminal_admission import PROFILE as TERMINAL_PROFILE, ARCHIVE_PROFILE
            result["admission_sha256"] = digest(dict(profile=ARCHIVE_PROFILE if result["archive"] else TERMINAL_PROFILE,
                data=data, archive=result["archive"]))
    return result


def _allocate(tables):
    refs = {kind:{} for kind in KINDS}
    # Ordinary PostgreSQL sequence allocation; no source PK, business counter,
    # trigger disabling or owner credential is used. Preview may leave PK gaps.
    with connection.cursor() as cursor:
        for kind, rows in tables.items():
            for source in rows:
                cursor.execute("SELECT nextval(pg_get_serial_sequence(%s, 'id'))", [KINDS[kind]._meta.db_table])
                refs[kind][source["id"]] = cursor.fetchone()[0]
    return refs


ORDER = ("PawnLoan", "PawnCollateralItem", "LoanPolicySnapshot", "PawnLoanApprovalSnapshot", "PawnLoanAuction",
    "PawnLoanEvent", "PawnLoanDisbursalSnapshot", "RepaymentScheduleVersion", "RepaymentObligation",
    "PawnLoanInterestAccrual", "PawnLoanInterestAccrualLine", "PawnLoanRepaymentAllocationLine",
    "PawnLoanPrincipalClosingLine", "PawnLoanPrincipalOpeningLine", "PawnLoanRelease", "PawnLoanReleaseItem",
    "PawnLoanReleaseReversal", "PawnLoanAuctionItem", "PawnLoanAuctionReversal", "PawnLoanRenewal", "PawnLoanRenewalReversal",
    "ObligationAllocation", "RepaymentScheduleChange", "CollateralAppraisal", "PawnReleaseBatch", "PawnReleaseBatchLine",
    "HistoricalLoanEvidence", "HistoricalLoanAttachment", "StatutoryAuctionNotice", "StatutoryNoticeEvidence",
    "PawnCollateralCustodyEvent", "PawnCollateralPhoto", "LoanChangeLog", "LoanTransactionReview")
LOCAL_TIMES = {"created_at", "updated_at", "approved_at", "imported_at", "accepted_at", "reviewed_at", "finalized_at"}


def _loan_for(kind, source, tables):
    if kind == "PawnLoan":
        return source["id"]
    if source.get("loan_id"):
        return source["loan_id"]
    if source.get("source_loan_id"):
        return source["source_loan_id"]
    for key, parent in (("collateral_item_id", "PawnCollateralItem"), ("loan_event_id", "PawnLoanEvent"),
            ("accrual_id", "PawnLoanInterestAccrual"), ("release_id", "PawnLoanRelease"), ("auction_id", "PawnLoanAuction"),
            ("renewal_id", "PawnLoanRenewal"), ("schedule_version_id", "RepaymentScheduleVersion"), ("obligation_id", "RepaymentObligation"),
            ("notice_id", "StatutoryAuctionNotice"), ("evidence_id", "HistoricalLoanEvidence")):
        if source.get(key):
            row_source = next(r for r in tables[parent] if r["id"] == source[key])
            return _loan_for(parent, row_source, tables)
    return None


def _new_row(kind, values):
    """Validated new-row insertion; database guards and forced RLS stay enabled.

    Identity allocation precedes insertion for the supported cyclic graph. Model
    clean validates domain bindings; bulk_create is used only for these fresh
    immutable rows, whose save overrides prohibit any already-assigned primary key.
    No update/delete of posted evidence is performed.
    """
    obj = KINDS[kind](**values)
    # SQL-nullable legacy measurements may intentionally be unknown even where
    # the current origination form requires a value (blank=False).
    unknown = [key for key, spec in ROWS[kind].items() if spec["nullable"] and values.get(key) is None]
    if kind == "PawnReleaseBatchLine" and not values.get("collector_name"):
        # The original field predates unspecified-handover closures. Permit its
        # blank value only with the same exact evidence binding as the SQL guard.
        release, batch = obj.release, obj.batch
        paper = release.loan_event.payload.get("release", {}).get("paper_closure", {})
        require(batch.mode == "PAPER" and batch.workspace_id == release.workspace_id == obj.workspace_id
            and paper.get("profile") == "recorded-history-closure/1"
            and paper.get("closure_basis") == "PAPER_SETTLEMENT"
            and paper.get("batch_id") == batch.pk,
            "A blank collector requires exactly bound unspecified completed-closure evidence.")
        unknown.append("collector_name")
    obj.full_clean(exclude=unknown, validate_unique=False, validate_constraints=False)
    KINDS[kind].objects.bulk_create([obj])
    return obj


def _restore_graph(workspace, actor, document, files, mapping, saved_files):
    tables = document["tables"]
    refs = _allocate(tables)
    source_loans = {r["id"]:r for r in tables["PawnLoan"]}
    namespace = UUID(document["namespace"])
    numbers = {}
    loan_numbers = {}
    for pk, source in source_loans.items():
        number = _number(namespace, str(uuid5(namespace, f"loan:{pk}")), "PAWN_LOAN")
        _check_number(workspace.pk, number, "PAWN_LOAN")
        loan_numbers[pk] = number
        numbers[('loan_number',source['loan_number'])] = number
    for kind, field in (("PawnLoanRelease", "release_number"), ("PawnLoanAuction", "auction_number"), ("PawnLoanRenewal", "renewal_number")):
        for source in tables[kind]:
            numbers[(field,source[field])] = _number(namespace, kind+":"+str(source["id"]), kind)
    event_keys, deferred_loans, deferred_auctions = {}, {}, {}
    objects = {kind:{} for kind in KINDS}
    source_origins = {r["loan_id"]:r for r in tables["HistoricalLoanImport"]}
    terminal_loans = {r["loan_id"] for r in tables["PawnLoanEvent"] if r["payload"].get("opening", {}).get("profile") == "loan-terminal-evidence/1"}
    source_file_keys = {name:key for key, claim in document["files"].items() for name in claim["source_names"]}
    for kind in ORDER:
        for source in tables[kind]:
            owner = _loan_for(kind, source, tables)
            selected_mapping = mapping[str(owner)] if owner is not None else next(iter(mapping.values()))
            external = dict(selected_mapping, workspace_id=workspace.pk, licence_revision_id=selected_mapping["revision_id"],
                license_revision_id=selected_mapping["revision_id"], party_id=selected_mapping["borrower_id"],
                source_workspace_id=document["workspace_id"])
            current_numbers = dict(numbers)
            values = decode(kind, source)
            values["id"] = refs[kind][source["id"]]
            values["workspace_id"] = workspace.pk
            for key, spec in ROWS[kind].items():
                if key in LOCAL_TIMES:
                    values.pop(key, None)
                elif spec.get("reference") == ACTORS:
                    values[key] = actor.pk
                elif spec.get("reference", "").removeprefix("loans.") in refs and source[key] is not None:
                    values[key] = refs[spec["reference"].removeprefix("loans.")][source[key]]
                elif spec["type"] == "JSONField":
                    values[key] = _adapt(source[key], refs=refs, external=external, numbers=current_numbers, event_keys=event_keys)
                elif key in {"loan_number", "release_number", "auction_number", "renewal_number"}:
                    values[key] = loan_numbers[source["id"]] if kind == "PawnLoan" else numbers[(key,source[key])]
                elif key in {'public_id', 'creation_submission_id'} and spec["type"] == "UUIDField":
                    values[key] = uuid4()
            if kind == "PawnLoan":
                values.update({key:selected_mapping[key] for key in ("borrower_id", "license_id", "series_id", "product_version_id")})
                values["license_revision_id"] = selected_mapping["revision_id"]
                deferred_loans[source["id"]] = {k:values[k] for k in ("policy_snapshot_id", "disbursal_snapshot_id", "state")}
                values.update(policy_snapshot_id=None, disbursal_snapshot_id=None, state="ACTIVE", creation_submission_id=uuid4())
            if kind == "PawnCollateralItem":
                values["custody_state"] = source["custody_state"] if source["loan_id"] in terminal_loans else "IN_VAULT"
                # The frozen per-item agreement travels; the source's standing
                # setup row is retained as a claim, not a destination FK.
                values['interest_rate_policy_id'] = None
            if kind == "PawnLoanApprovalSnapshot":
                values["payload"].setdefault("historical_approval", dict(at=source["approved_at"], actor=str(source["approved_by_id"]) if source["approved_by_id"] else None,
                    reference="servicing-source:"+source["fingerprint"]))
                values["fingerprint"] = digest(values["payload"])
            if kind == "PawnLoanAuction":
                deferred_auctions[source["id"]] = {k:values[k] for k in ("state", "loan_event_id", "catch_up_accrual_id", "recovery_amount", "principal_amount", "interest_amount", "fee_amount", "completed_at", "started_at", "cancelled_at", "cancellation_reason")}
                values.update(state="INITIATED", loan_event_id=None, catch_up_accrual_id=None,
                    recovery_amount=0, principal_amount=0, interest_amount=0, fee_amount=0, completed_at=None, started_at=None, cancelled_at=None, cancellation_reason="")
            if kind == "PawnLoanEvent":
                if source["loan_id"] in terminal_loans:
                    terminal = objects["PawnLoan"][source["loan_id"]]
                    terminal.state = "CLOSED"
                    terminal.save(update_fields=["state"])
                from .event_recording import _fingerprint
                values["payload_fingerprint"] = _fingerprint(values["payload"])
                values["idempotency_key"] = f"loans:{values['loan_id']}:{values['event_kind']}:{values['payload_fingerprint']}"
                event_keys[source["idempotency_key"]] = values["idempotency_key"]
            if kind == "CollateralAppraisal":
                values["valuation_context"].setdefault("source_workspace_id", document["workspace_id"])
            if kind == "PawnCollateralPhoto":
                values["source_evidence"] = dict(portable_source=dict(captured_at=source["captured_at"], captured_by=source["captured_by_id"], workflow_source=source["workflow_source"], evidence=source["source_evidence"]))
            if kind == 'HistoricalLoanEvidence':
                values['document'], values['review'] = deepcopy(source['document']), deepcopy(source['review'])
            if kind == "StatutoryAuctionNotice":
                # The original statutory PDF remains the original source copy.
                # Its snapshot is a source claim, not a newly sent local notice.
                values["snapshot"] = deepcopy(source["snapshot"])
                values["snapshot_sha256"] = digest(values["snapshot"])
            if kind == "LoanTransactionReview":
                from apps.tenant_apps.loans.selectors.transaction_completeness import transaction_fingerprint
                loan = objects["PawnLoan"][source["loan_id"]]
                values.update(future_capture="PAPER_MIXED", capture_state="", capture_event_id=None, capture_contract_fingerprint="",
                    confirmed_complete=False, source_fingerprint=transaction_fingerprint(loan),
                    source_reference=("Source review retained in the imported bundle; local completeness is checked separately. " + source["source_reference"])[:500],
                    request_key="portable-source-review:"+str(namespace)+":"+str(source["id"]))
            for key, spec in ROWS[kind].items():
                if spec["type"] == "FileField" and source[key]:
                    require(source[key] in source_file_keys, "Missing retained source file.")
                    checksum = source_file_keys[source[key]]
                    field = KINDS[kind]._meta.get_field(key)
                    holder = KINDS[kind](**values)
                    name = field.generate_filename(holder, PurePosixPath(source[key]).name)
                    if kind == 'HistoricalLoanAttachment':
                        name = f'loans/portable/workspace-{workspace.pk}/attachments/{uuid4().hex}/{PurePosixPath(source[key]).name}'
                    new_name = field.storage.save(name, ContentFile(files[checksum]))
                    saved_files.append((field.storage, new_name))
                    values[key] = new_name
            provisional = []
            if kind == 'PawnLoanDisbursalSnapshot' and source['basis']=='RECORDED' and source['id']!=source_loans[owner]['disbursal_snapshot_id']:
                reversal = next((e for e in tables['PawnLoanEvent'] if e['reversal_of_id']==source['loan_event_id']), None)
                require(reversal and reversal['payload'].get('history_correction',{}).get('operation')=='CONTRACT', 'Superseded payout requires an explicit compensated contract correction.')
                # During admission only, replay the earlier mutable agreement
                # projection while inserting its immutable snapshot. Ordinary
                # Python and SQL checks both remain enabled. Restore the current
                # projection before accepting any destination position.
                loan = objects['PawnLoan'][owner]
                recording = values['evidence']['recording']
                fields = dict(loan_date=date.fromisoformat(recording['occurred_on']), principal_amount=values['gross_principal'],
                    monthly_interest_rate=Decimal(recording['terms']['monthly_interest_rate']),tenure_months=recording['terms']['tenure_months'])
                provisional.append((loan,{key:getattr(loan,key) for key in fields}))
                for key,value in fields.items():
                    setattr(loan,key,value)
                loan.save(update_fields=list(fields))
                facts = {r['item_id']:r for r in recording['terms']['collateral']}
                for tranche in values['evidence']['tranches']:
                    item = m.PawnCollateralItem.objects.get(pk=tranche['collateral_item_id'],loan=loan,workspace=workspace)
                    item_fields = {key:facts[item.pk][key] for key in ('description','metal','quantity','gross_weight','net_weight','purity_percentage')}
                    item_fields.update(allocated_principal=Decimal(tranche['allocated_principal']),monthly_interest_rate=Decimal(tranche['monthly_interest_rate']))
                    provisional.append((item,{key:getattr(item,key) for key in item_fields}))
                    for key,value in item_fields.items():
                        setattr(item,key,value)
                    item.save(update_fields=list(item_fields))
            obj = _new_row(kind, values)
            for projection,fields in provisional:
                for key,value in fields.items():
                    setattr(projection,key,value)
                projection.save(update_fields=list(fields))
            objects[kind][source["id"]] = obj
            if kind == "LoanPolicySnapshot" and source["id"] == source_loans[source["loan_id"]]["policy_snapshot_id"]:
                loan = objects["PawnLoan"][source["loan_id"]]
                loan.policy_snapshot_id = obj.pk
                loan.save(update_fields=["policy_snapshot_id"])
            if kind == "PawnLoanDisbursalSnapshot" and source["id"] == source_loans[source["loan_id"]]["disbursal_snapshot_id"]:
                loan = objects["PawnLoan"][source["loan_id"]]
                loan.disbursal_snapshot_id = obj.pk
                loan.save(update_fields=["disbursal_snapshot_id"])
            if kind == "PawnCollateralCustodyEvent":
                item = objects["PawnCollateralItem"][source["collateral_item_id"]]
                item.custody_state = obj.to_state
                item.save(update_fields=["custody_state"])
    for pk, fields in deferred_auctions.items():
        m.PawnLoanAuction.objects.filter(pk=refs["PawnLoanAuction"][pk], workspace=workspace).update(**fields)
    for pk, fields in deferred_loans.items():
        loan = objects["PawnLoan"][pk]
        for key, value in fields.items():
            setattr(loan, key, value)
        loan.save(update_fields=list(fields))
    for source in tables["PawnCollateralItem"]:
        item = objects["PawnCollateralItem"][source["id"]]
        require(item.custody_state == source["custody_state"], "Rebuilt collateral custody differs from its source graph.")
    # Retain every original row, original actor/time/review choice, issued PDF and
    # source claim independently from local imported operational records.
    retained_files = {key:base64.b64encode(value).decode() for key,value in files.items()}
    origins = []
    summary = dict(profile=PROFILE, source_sha256=document["sha256"], loans=[])
    for source_id, loan in objects["PawnLoan"].items():
        original = source_origins.get(source_id)
        source_identity = str(uuid5(namespace, f"loan:{source_id}"))
        source_namespace = namespace
        accepted = dict(profile="loan-servicing-admission/1", source_loan=source_loans[source_id], source_setup=document["setup"][str(source_id)])
        if original:
            accepted = _adapt(original["document"], refs=refs, external=dict(mapping[str(source_id)], workspace_id=workspace.pk,
                licence_revision_id=mapping[str(source_id)]["revision_id"], license_revision_id=mapping[str(source_id)]["revision_id"],
                source_workspace_id=document["workspace_id"]), numbers=numbers, event_keys=event_keys)
            source_namespace, source_identity = UUID(original["source_namespace"]), original["source_id"]
        references = dict(mapping={k:v for k,v in mapping[str(source_id)].items() if k != "license_id"},
            items={str(pk):local for pk,local in refs["PawnCollateralItem"].items() if next(i for i in tables["PawnCollateralItem"] if i["id"]==pk)["loan_id"]==source_id},
            events={str(pk):local for pk,local in refs["PawnLoanEvent"].items() if next(e for e in tables["PawnLoanEvent"] if e["id"]==pk)["loan_id"]==source_id},
            portable=dict(document=document, files=retained_files, mapping=mapping, source_loan_id=source_id, refs=refs))
        if original:
            old = original["references"]
            if 'items' in old:
                references["items"] = {key:refs["PawnCollateralItem"][pk] for key,pk in old["items"].items()}
            if 'events' in old:
                references["events"] = {key:refs["PawnLoanEvent"][pk] for key,pk in old["events"].items()}
            if old.get("schedule_id"):
                references["schedule_id"] = refs["RepaymentScheduleVersion"][old["schedule_id"]]
            if accepted.get("profile") == "loan-opening-commit/1":
                references["mapping"] = accepted["review"]["mapping"]
        origin = m.HistoricalLoanImport.objects.create(workspace=workspace, loan=loan,
            archive_evidence_id=refs["HistoricalLoanEvidence"][original["archive_evidence_id"]] if original and original["archive_evidence_id"] else None,
            source_namespace=source_namespace, source_id=source_identity, source_sha256=digest(accepted),
            document=accepted, references=references, imported_by=actor)
        origins.append(origin)
        loan.refresh_from_db()
        actual = _position(loan, date.fromisoformat(document["as_of"]))
        expected = document["positions"][str(source_id)]
        for key in ("state", "contract", "financial_history_from", "recorded", "collection", "exposure", "interest_conceded"):
            require(actual[key] == expected[key], "Restored financial position differs: " + key)
        expected_custody = [dict(id=refs["PawnCollateralItem"][r["id"]], state=r["state"], predecessor=refs["PawnCollateralItem"].get(r["predecessor"])) for r in expected["custody"]]
        require(actual["custody"] == expected_custody, "Restored collateral lineage differs.")
        from .transaction_reviews import _store
        if loan.state in {'ACTIVE','CLOSED'}:
            _store(loan, actor, through_date=date.fromisoformat(document["as_of"]), confirmed_complete=expected["coverage"]["complete"],
                source_reference="Imported and reconciled source servicing graph; source completeness claim retained, future recording remains paper/mixed.",
                request_key="portable-position:"+str(namespace)+":"+str(source_id))
        summary["loans"].append(dict(source_id=source_id, source_number=source_loans[source_id]["loan_number"], local_number=loan.loan_number,
            state=loan.state, position=expected["recorded"], collection=expected["collection"], source_coverage=expected["coverage"], future_capture="PAPER_MIXED"))
    return origins, summary


def restore_servicing_bundle(*, workspace_id, actor, content, mapping, expected_sha256=None, confirmed=False):
    workspace = _access(workspace_id, actor)
    document, files = read_bundle(content)
    request_sha = digest(dict(source=sha(content), workspace_id=workspace_id, actor_id=actor.pk, mapping=mapping))
    require((expected_sha256 is None and confirmed is False) or (confirmed is True and expected_sha256 == request_sha), "Confirm the exact servicing restore preview checksum.")
    saved_files = []
    committed = False
    try:
        with transaction.atomic():
            Company.all_objects.select_for_update().get(pk=workspace_id)
            _access(workspace_id, actor)
            selected_mapping = _mapping(document, workspace_id, mapping)
            existing = list(m.HistoricalLoanImport.objects.filter(workspace_id=workspace_id,
                references__portable__document__sha256=document["sha256"]).select_related("loan"))
            if existing:
                require(len(existing) == len(document["tables"]["PawnLoan"]) and all(o.references["portable"]["mapping"] == selected_mapping for o in existing), "Existing servicing source has different destination mappings.")
                return dict(sha256=request_sha, already_restored=True, loans=[o.loan_id for o in existing])
            original_sources = document["tables"]["HistoricalLoanImport"]
            original_loans = {r['loan_id'] for r in original_sources}
            for loan in document['tables']['PawnLoan']:
                if loan['id'] not in original_loans:
                    require(not m.HistoricalLoanImport.objects.filter(workspace_id=workspace_id, source_namespace=document['namespace'], source_id=str(uuid5(UUID(document['namespace']), f"loan:{loan['id']}"))).exists(), "This source loan already has accepted financial history; changed bundles cannot overwrite it.")
            for original in original_sources:
                require(not m.HistoricalLoanImport.objects.filter(workspace_id=workspace_id, source_namespace=original["source_namespace"], source_id=original["source_id"]).exists(), "This source loan already has accepted financial history; servicing restore cannot overwrite or augment it.")
            origins, summary = _restore_graph(workspace, actor, document, files, selected_mapping, saved_files)
            # Force deferred graph/ownership guards before reporting a successful
            # preview, including preview transactions that will be rolled back.
            with connection.cursor() as cursor:
                cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
                cursor.execute("SET CONSTRAINTS ALL DEFERRED")
            result = dict(sha256=request_sha, summary=summary, committed=confirmed,
                loans=[origin.loan_id for origin in origins] if confirmed else [])
            if confirmed:
                AuditLog.log("DATA_IMPORT", company=workspace, user=actor, description="Imported and reconciled bounded source servicing graph; original actors, review choices and documents retained separately.", data=dict(profile=PROFILE, loans=result["loans"], sha256=request_sha))
            else:
                transaction.set_rollback(True)
        committed = confirmed
        return result
    finally:
        if not committed:
            for storage, name in saved_files:
                storage.delete(name)
