"""Typed khata snapshots, idempotent issuance, and verified exact private reprints."""
import hashlib
from copy import copy
from decimal import Decimal

from django.core.files.base import ContentFile
from django.utils import timezone

from apps.tenancy.context import workspace_context
from apps.tenant_apps.loans.models import KhataDocumentIssue
from apps.tenant_apps.loans.selectors.khata import account_position
from apps.tenant_apps.loans.selectors.khata_summary import summary_accounts, account_summary, collateral_cover
from apps.tenant_apps.loans.documents.khata import render_document, VERSION
from .action_access import require_workspace_action
from .khata_accounts import _hash, _key, KhataDraftError
from .khata_opening import _locked

TITLES = {"APPROVE": "Approved opening agreement", "WITHDRAW": "Withdrawal voucher",
    "INTEREST": "Interest receipt", "TERMS_OK": "Approved agreement amendment",
    "REVISE": "Activated agreement amendment", "EXCHANGE": "Collateral exchange",
    "HANDOVER": "Collateral handover", "RETURN": "Unopened collateral return",
    "SETTLE": "Settlement receipt", "CORRECT": "Correction acknowledgement", "DEPOSIT": "Collateral receipt"}


def _terms(revision):
    return dict(id=revision.pk, number=revision.number, agreed_limit=str(revision.agreed_limit),
        monthly_rate=str(revision.monthly_rate), ltv=str(revision.ltv), frequency=revision.frequency,
        lender_name=revision.lender_name, lender_address=revision.lender_address,
        contract_version=revision.contract_version)


def _source(op):
    return dict(id=op.pk, sequence=op.sequence, kind=op.kind, date=op.business_date.isoformat(),
        amount=str(op.amount), interest_amount=str(op.interest_amount), evidence=op.evidence,
        parent_id=op.parent_id, correction_of_id=op.correction_of_id,
        actor=op.created_by.get_full_name() or op.created_by.get_username())


def document_payload(account, *, source_operation_id=None):
    """Historical vouchers use the source prefix, never later agreement/custody facts."""
    ops = list(account.summary_operations)
    source = next((op for op in ops if op.pk == source_operation_id), None) if source_operation_id is not None else None
    if source_operation_id is not None and (source is None or source.kind not in TITLES):
        raise KhataDraftError("Choose a supported source operation from this khata.")
    prefix = [op for op in ops if op.sequence <= source.sequence] if source else ops
    summary = account_summary(account) if source is None else None
    agreement = source.agreement if source and source.agreement_id else next(
        (op.agreement for op in reversed(prefix) if op.kind in ("WITHDRAW", "REVISE", "APPROVE") and op.agreement_id), None)
    if summary:
        agreement = summary["agreement"]
    if agreement is None:
        if source:
            raise KhataDraftError("Issue collateral receipts after opening approval records the lender identity.")
        agreement = next(iter(account.summary_agreements), None)
    if agreement is None:
        raise KhataDraftError("No khata agreement evidence exists.")
    source_account = copy(account)
    source_account.summary_operations = prefix
    position = account_position(source_account)
    license_snapshot = None
    for op in prefix:
        if "license" in op.evidence:
            value = op.evidence["license"]
            license_snapshot = dict(license_snapshot or {}, **value) if value else None
    # Draft statements clearly use today's setup association; approved documents
    # retain the actual review revision, including explicit independent status.
    if not any("license" in op.evidence for op in prefix) and account.series.license_id:
        license = account.series.license
        license_snapshot = dict(id=license.pk, number=license.license_number,
            revision_id=license.revisions.order_by("-revision_number").values_list("pk", flat=True).first())
    addresses = account.borrower.addresses.order_by("-is_default", "pk")
    address = addresses.first()
    address_text = "\n".join(str(getattr(address, key)) for key in
        ("line1", "line2", "area", "city", "state", "postal_code", "country") if address and getattr(address, key))
    corrected = {op.correction_of_id for op in prefix if op.kind == "CORRECT"}
    returned = {op.item_id for op in prefix if op.kind in ("HANDOVER", "RETURN")}
    reserved = {s.item_id for op in prefix if op.pk not in corrected for s in op.summary_selections}
    items = [dict(id=item.pk, description=item.description, metal=item.metal, quantity=item.quantity,
        gross_weight=str(item.gross_weight), net_weight=str(item.net_weight), purity=str(item.purity),
        storage_reference=item.storage_reference,
        custody="Returned" if item.pk in returned else "Return pending" if item.pk in reserved else "Held")
        for item in account.collateral.all() if item.received_operation.sequence <= (source.sequence if source else 2**63)]
    payload = dict(schema="khata-document/1", workspace_id=account.workspace_id, account_id=account.pk,
        account_number=account.account_number, series=account.series.name,
        as_of=(source.business_date if source else timezone.localdate()).isoformat(),
        source_sequence=source.sequence if source else max((op.sequence for op in ops), default=0),
        title=TITLES[source.kind] if source else "Dated khata statement",
        kind="OPERATION" if source else "STATEMENT", issued_at=timezone.now().isoformat(),
        borrower=dict(id=account.borrower_id, name=account.borrower.display_name,
            code=account.borrower.party_code, address=address_text, phone=str(account.borrower.primary_phone)),
        agreement=_terms(agreement), license=license_snapshot, source=_source(source) if source else None,
        principal=str(position.principal if position else Decimal(0)),
        unused=str(position.unused if position else Decimal(0)), collateral=items,
        opened_on=next((op.business_date.isoformat() for op in prefix if op.kind == "WITHDRAW"), None),
        correction_notice=next((op.pk for op in ops if source and op.correction_of_id == source.pk), None),
        history=[_source(op) for op in ops if op.kind != "PHOTO"] if source is None else [])
    if source:
        payload["selected_items"] = [dict(item_id=s.item_id, role=s.role)
            for s in source.collateral_selections.all()]
        payload["allocations"] = [dict(start_on=str(a.period.start_on), end_on=str(a.period.end_on),
            due_on=str(a.period.due_on), amount=str(a.amount))
            for a in source.interest_allocations.select_related("period")]
    if summary:
        payload["state"] = account.get_state_display()
        payload["balances"] = {k: str(summary[k]) for k in ("principal", "interest", "due_interest", "overdue_interest", "limit", "unused", "outstanding")}
        payload["interest_schedule"] = [{k: str(v) for k, v in row.items()} for row in summary["schedule"]]
        payload["cover"] = {k: str(v) if isinstance(v, Decimal) else v for k, v in collateral_cover(account, summary).items()}
    # Canonical JSON primitives ensure reproducible payload hashes.
    return payload


def issue_document(*, workspace, actor, account_id, request_key, source_operation_id=None):
    key = _key(request_key)
    fingerprint = _hash(dict(account=account_id, source=source_operation_id, actor=actor.pk, kind="KHATA_DOCUMENT"))
    artifact = None
    try:
        with _locked(workspace, actor, account_id, "data.edit"):
            require_workspace_action(workspace, actor, "data.export")
            existing = KhataDocumentIssue.objects.filter(workspace=workspace, request_key=key).first()
            if existing:
                if existing.account_id != account_id or existing.request_sha256 != fingerprint:
                    raise KhataDraftError("Document request UUID was already used for different instructions.")
                return existing
            account = summary_accounts(workspace=workspace).get(pk=account_id)
            payload = document_payload(account, source_operation_id=source_operation_id)
            pdf = render_document(payload, issue_reference=str(key))
            issue = KhataDocumentIssue(workspace=workspace, account=account, source_operation_id=source_operation_id,
                kind=payload["kind"], as_of=payload["as_of"], source_sequence=payload["source_sequence"],
                request_key=key, request_sha256=fingerprint, payload=payload, payload_sha256=_hash(payload),
                renderer_version=VERSION, artifact_sha256=hashlib.sha256(pdf).hexdigest(), byte_size=len(pdf), created_by=actor)
            issue.artifact.save("khata.pdf", ContentFile(pdf), save=False)
            artifact = issue.artifact
            issue.full_clean()
            issue.save()
            return issue
    except Exception:
        if artifact:
            artifact.storage.delete(artifact.name)
        raise


def document_bytes(*, workspace, actor, issue_id, account_id):
    with workspace_context(workspace.pk):
        require_workspace_action(workspace, actor, "data.export")
        issue = KhataDocumentIssue.objects.get(workspace=workspace, account_id=account_id, pk=issue_id)
        if _hash(issue.payload) != issue.payload_sha256:
            raise KhataDraftError("Issued document snapshot integrity check failed.")
        with issue.artifact.open("rb") as stream:
            content = stream.read(issue.byte_size + 1)
        if len(content) != issue.byte_size or hashlib.sha256(content).hexdigest() != issue.artifact_sha256:
            raise KhataDraftError("Issued PDF integrity check failed; restore the preserved artifact.")
        return issue, content
