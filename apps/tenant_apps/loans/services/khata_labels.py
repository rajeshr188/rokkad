"""Immutable held-collateral snapshots and idempotent private label issuance."""
import hashlib
from urllib.parse import urlsplit

from django.core.files.base import ContentFile
from django.urls import reverse
from django.utils import timezone

from apps.tenant_apps.loans.documents.khata_labels import render_labels, VERSION
from apps.tenant_apps.loans.models import KhataDocumentIssue
from apps.tenant_apps.loans.selectors.khata import held_items
from .action_access import require_workspace_action
from .khata_accounts import _hash, _key, KhataDraftError
from .khata_opening import _locked


def _selection(mode, item_ids):
    ids = list(item_ids or ())
    if mode != "SELECTED" and ids:
        raise KhataDraftError("Item selections require the selected-item layout.")
    if mode == "SELECTED":
        if not 1 <= len(ids) <= 100 or any(type(i) is not int or i <= 0 for i in ids) or len(set(ids)) != len(ids):
            raise KhataDraftError("Select between 1 and 100 distinct held items for this batch.")
    return sorted(ids)


def label_payload(account, *, origin, mode, item_id=None, item_ids=None):
    selected = _selection(mode, item_ids)
    if mode not in ("ONE", "ALL", "EACH", "SELECTED") or (mode == "ONE") != (item_id is not None):
        raise KhataDraftError("Choose one held item, all held collateral, or one page per held item.")
    parsed = urlsplit(origin)
    if parsed.scheme not in ("https", "http") or not parsed.netloc or parsed.username or parsed.password or parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise KhataDraftError("A valid application origin is required for authenticated scan routes.")
    origin = origin.rstrip("/")
    scan_path = reverse("workspace_loans:khata_account_scan", kwargs=dict(workspace_slug=account.workspace.slug, public_id=account.public_id))
    if len(origin + scan_path) > 256:
        raise KhataDraftError("The authenticated scan URL is too long for a readable label QR.")
    items = held_items(account).filter(pk=item_id) if mode == "ONE" else held_items(account)
    if mode == "SELECTED":
        items = items.filter(pk__in=selected)
    items = list(items.order_by("pk")[:101])
    if mode == "SELECTED" and [i.pk for i in items] != selected:
        raise KhataDraftError("Every selected item must belong to this account and still be physically held. Refresh the item list.")
    if not items:
        raise KhataDraftError("There is no matching held collateral to label; returned items cannot receive a new custody label.")
    if len(items) > 100:
        raise KhataDraftError("At most 100 held items can be labelled in one issue. Use selected-item batches for larger accounts.")
    reserved = set(account.operations.filter(corrected_by__isnull=True, collateral_selections__role="OUT")
        .values_list("collateral_selections__item_id", flat=True))
    rows = []
    for item in items:
        path = reverse("workspace_loans:khata_item_scan", kwargs=dict(workspace_slug=account.workspace.slug, public_id=item.public_id))
        if len(origin + path) > 256:
            raise KhataDraftError("The authenticated scan URL is too long for a readable label QR.")
        rows.append(dict(id=item.pk, public_id=str(item.public_id), received_operation_id=item.received_operation_id,
            description=item.description, metal=item.metal, quantity=item.quantity, gross_weight=str(item.gross_weight),
            net_weight=str(item.net_weight), purity=str(item.purity), storage_reference=item.storage_reference,
            custody="Return pending" if item.pk in reserved else "Held", scan_path=path))
    return dict(schema="khata-label/1", kind="LABEL", workspace_id=account.workspace_id, account_id=account.pk,
        account_number=account.account_number, public_id=str(account.public_id),
        borrower=dict(id=account.borrower_id, name=account.borrower.display_name, code=account.borrower.party_code),
        title="Combined held-collateral label" if mode == "ALL" else "Selected collateral label batch" if mode == "SELECTED" else "Individual held-collateral labels" if mode == "EACH" else "Collateral item label",
        mode=mode, origin=origin, scan_path=scan_path, items=rows, as_of=timezone.localdate().isoformat(),
        issued_at=timezone.now().isoformat(), source_sequence=account.operations.order_by("-sequence").values_list("sequence", flat=True).first() or 0)


def issue_labels(*, workspace, actor, account_id, request_key, origin, mode, item_id=None, item_ids=None):
    key = _key(request_key)
    selected = _selection(mode, item_ids)
    instructions = dict(kind="KHATA_LABEL", account=account_id, actor=actor.pk, mode=mode, item=item_id, origin=origin)
    if mode == "SELECTED":
        instructions["items"] = selected
    fingerprint = _hash(instructions)
    artifact = None
    try:
        with _locked(workspace, actor, account_id, "data.edit") as account:
            require_workspace_action(workspace, actor, "data.export")
            existing = KhataDocumentIssue.objects.filter(workspace=workspace, request_key=key).first()
            if existing:
                if existing.account_id != account_id or existing.request_sha256 != fingerprint:
                    raise KhataDraftError("Label request UUID was already used with different instructions.")
                return existing
            payload = label_payload(account, origin=origin, mode=mode, item_id=item_id, item_ids=selected)
            content = render_labels(payload)
            issue = KhataDocumentIssue(workspace=workspace, account=account, kind="LABEL", as_of=payload["as_of"],
                source_sequence=payload["source_sequence"], request_key=key, request_sha256=fingerprint,
                payload=payload, payload_sha256=_hash(payload), renderer_version=VERSION,
                artifact_sha256=hashlib.sha256(content).hexdigest(), byte_size=len(content), created_by=actor)
            issue.artifact.save("label.pdf", ContentFile(content), save=False)
            artifact = issue.artifact
            issue.full_clean()
            issue.save()
            return issue
    except Exception:
        if artifact:
            artifact.storage.delete(artifact.name)
        raise
