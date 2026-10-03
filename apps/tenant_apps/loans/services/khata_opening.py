"""Khata custody, opening approval and withdrawals. Not exposed by HTTP yet."""
import hashlib
import logging
import uuid
from contextlib import contextmanager
from decimal import Decimal, ROUND_DOWN
from io import BytesIO

from django.core.files.base import ContentFile
from django.db.models import Max
from django.utils import timezone
from PIL import Image

from apps.orgs.models import Company
from apps.tenancy.context import workspace_context
from apps.tenant_apps.loans.access import LOANS_OWNER_ACTION
from apps.tenant_apps.loans.domain.khata import DrawPosition, amount, available_draw
from apps.tenant_apps.loans.models import (
    KhataAccount, KhataOperation, KhataPolicyRevision, KhataCollateralItem,
    KhataCollateralPhoto, KhataCollateralValuation,
)
from apps.tenant_apps.loans.selectors.khata import held_items, eligible_items, account_position, account_balances, effective_agreement, activated_agreements
from apps.tenant_apps.loans.selectors.origination_rates import get_origination_quote_rows, require_fresh_quotes
from .action_access import require_workspace_action
from .collateral_media import validate_collateral_photo, MAX_PHOTO_BYTES
from .khata_accounts import KhataDraftError, _hash, _key, _today
from .origination_settings import collateral_photos_required

logger = logging.getLogger(__name__)


def _photo_content(upload):
    mime = validate_collateral_photo(upload)
    upload.seek(0)
    content = upload.read(MAX_PHOTO_BYTES + 1)
    upload.seek(0)
    if not content or len(content) > MAX_PHOTO_BYTES:
        raise KhataDraftError("Collateral photo exceeds the supported size.")
    try:
        with Image.open(BytesIO(content)) as image:
            image.verify()
    except (OSError, ValueError) as exc:
        raise KhataDraftError("Select a readable JPEG or PNG photograph.") from exc
    return mime, content, hashlib.sha256(content).hexdigest()


def _discard_failed_photo(photo):
    if photo is not None and photo.file.name:
        try:
            photo.file.storage.delete(photo.file.name)
        except Exception:
            logger.exception("Could not clean up an uncommitted Khata photograph.")


@contextmanager
def _locked(workspace, actor, account_id, action):
    with workspace_context(workspace.pk):
        require_workspace_action(workspace, actor, action)
        # Same order as Rates writes, photo-policy writes and draft allocation.
        Company.objects.select_for_update().get(pk=workspace.pk)
        account = KhataAccount.objects.select_for_update().get(workspace=workspace, pk=account_id)
        yield account


def _retry(account, key, fingerprint):
    op = KhataOperation.objects.filter(workspace_id=account.workspace_id, request_key=key).first()
    if op and (op.account_id != account.pk or op.request_sha256 != fingerprint):
        raise KhataDraftError("Request UUID was already used with different instructions.")
    return op


def _operation(account, actor, key, fingerprint, kind, day, evidence, **fields):
    op = KhataOperation(workspace_id=account.workspace_id, account=account, created_by=actor,
        request_key=key, request_sha256=fingerprint, kind=kind, business_date=day,
        sequence=(account.operations.aggregate(last=Max("sequence"))["last"] or 0) + 1,
        evidence=evidence, **fields)
    op.full_clean()
    op.save()
    return op


def _live(account, day):
    _today(day)
    if account.state not in ("DRAFT", "APPROVED", "ACTIVE"):
        raise KhataDraftError("This khata is cancelled or financially settled.")


def record_deposit(*, workspace, actor, account_id, request_key, business_date, description,
                   metal, quantity, gross_weight, net_weight, purity, storage_reference, received_from, upload=None):
    values = dict(description=description.strip(), metal=metal, quantity=quantity,
        gross_weight=Decimal(str(gross_weight)), net_weight=Decimal(str(net_weight)), purity=Decimal(str(purity)),
        storage_reference=storage_reference.strip())
    if any(not values[f].is_finite() for f in ("gross_weight", "net_weight", "purity")):
        raise KhataDraftError("Collateral weights and purity must be finite decimals.")
    if not received_from.strip():
        raise KhataDraftError("Record who handed over the collateral.")
    key = _key(request_key)
    instructions = dict(values, actor=actor.pk, date=business_date, received_from=received_from.strip(), kind="DEPOSIT")
    if upload is not None:
        instructions["photo_sha256"] = _photo_content(upload)[2]
    fingerprint = _hash(instructions)
    photo = None
    try:
        with _locked(workspace, actor, account_id, "data.edit") as account:
            if op := _retry(account, key, fingerprint):
                return op.received_item
            _live(account, business_date)
            op = _operation(account, actor, key, fingerprint, "DEPOSIT", business_date,
                {"schema": "khata-opening/1", "received_from": received_from.strip()})
            item = KhataCollateralItem(workspace=workspace, account=account, received_operation=op, **values)
            item.full_clean()
            item.save()
            if upload is not None:
                photo = attach_photo(workspace=workspace, actor=actor, account_id=account_id,
                    item_id=item.pk, business_date=business_date, upload=upload,
                    request_key=uuid.uuid5(key, "receipt-photo"))
        return item
    except Exception:
        _discard_failed_photo(photo)
        raise


def return_unopened_item(*, workspace, actor, account_id, item_id, request_key, business_date, recipient, reason):
    key = _key(request_key)
    fingerprint = _hash(dict(actor=actor.pk, item=item_id, date=business_date, recipient=recipient.strip(), reason=reason.strip(), kind="RETURN"))
    with _locked(workspace, actor, account_id, "loan.release") as account:
        if op := _retry(account, key, fingerprint):
            return op
        _live(account, business_date)
        if account.opened_on or not recipient.strip() or not reason.strip():
            raise KhataDraftError("Record recipient/reason; active returns require exchange, reduction or settlement.")
        item = held_items(account).get(pk=item_id)
        return _operation(account, actor, key, fingerprint, "RETURN", business_date,
            {"schema": "khata-opening/1", "recipient": recipient.strip(), "reason": reason.strip()}, item=item)


def attach_photo(*, workspace, actor, account_id, item_id, request_key, business_date, upload):
    mime, content, digest = _photo_content(upload)
    key = _key(request_key)
    fingerprint = _hash(dict(actor=actor.pk, item=item_id, date=business_date, sha256=digest, kind="PHOTO"))
    photo = None
    try:
        with _locked(workspace, actor, account_id, "data.edit") as account:
            if op := _retry(account, key, fingerprint):
                return op.photo
            _live(account, business_date)
            item = held_items(account).get(pk=item_id)
            op = _operation(account, actor, key, fingerprint, "PHOTO", business_date, {"schema": "khata-opening/1", "sha256": digest}, item=item)
            photo = KhataCollateralPhoto(workspace=workspace, item=item, operation=op,
                sha256=digest, byte_size=len(content), mime_type=mime)
            # Know our unique private path before writing, including a partial-write failure.
            photo.file.name = photo.file.field.generate_filename(photo, "photo")
            photo.file.name = photo.file.storage.save(photo.file.name, ContentFile(content))
            photo.file._committed = True
            photo.full_clean()
            photo.save()
        return photo
    except Exception:
        _discard_failed_photo(photo)
        raise


def set_policies(*, workspace, actor, exchange, overdue, reason, request_key):
    key = _key(request_key)
    values = dict(exchange=exchange, overdue=overdue, reason=reason.strip())
    fingerprint = _hash(dict(values, actor=actor.pk))
    with workspace_context(workspace.pk):
        require_workspace_action(workspace, actor, LOANS_OWNER_ACTION)
        Company.objects.select_for_update().get(pk=workspace.pk)
        existing = KhataPolicyRevision.objects.filter(workspace=workspace, request_key=key).first()
        if existing:
            if existing.request_sha256 != fingerprint:
                raise KhataDraftError("Request UUID was already used with different instructions.")
            return existing
        row = KhataPolicyRevision(workspace=workspace, created_by=actor, request_key=key, request_sha256=fingerprint,
            number=(KhataPolicyRevision.objects.filter(workspace=workspace).aggregate(last=Max("number"))["last"] or 0) + 1, **values)
        row.full_clean()
        row.save()
        return row


def _photo_evidence(item, required):
    photo = item.photos.order_by("-pk").first()
    if not photo:
        if required:
            raise KhataDraftError("Every held collateral item requires a photograph under the workspace policy.")
        return None
    try:
        with photo.file.open("rb") as stream:
            content = stream.read(MAX_PHOTO_BYTES + 1)
        if len(content) != photo.byte_size or hashlib.sha256(content).hexdigest() != photo.sha256:
            raise KhataDraftError("Collateral photo bytes do not match recorded evidence.")
    except OSError as exc:
        raise KhataDraftError("A recorded collateral photograph is unavailable.") from exc
    return {"id": photo.pk, "sha256": photo.sha256, "file": photo.file.name}


def _review(account, *, workspace, actor, day):
    _live(account, day)
    terms = effective_agreement(account)
    if terms is None:
        raise KhataDraftError("Save agreement terms first.")
    if account.opened_on is None and terms.intended_on != day:
        raise KhataDraftError("Opening terms are dated earlier; save and approve today's proposal.")
    if account.borrower.status != "ACTIVE":
        raise KhataDraftError("Borrower must be active for approval or withdrawal.")
    license = account.series.license
    if not account.series.is_active:
        raise KhataDraftError("Khata series is inactive.")
    if license and (not license.is_active or license.is_legacy_reference or license.is_expired(day) or license.issued_on > day):
        raise KhataDraftError("The associated licence is unavailable for new lending.")
    items = list(eligible_items(account))
    if not items:
        raise KhataDraftError("Receive collateral before approval or withdrawal.")
    rows = get_origination_quote_rows(workspace_id=workspace.pk, loan_date=day, metals=[i.metal for i in items])
    require_fresh_quotes(rows)
    prices = {r["metal"]: r for r in rows}
    required = collateral_photos_required(workspace.pk)
    valuations = []
    for item in items:
        row = prices[item.metal]
        value = (row["rate"].buying_rate * item.net_weight * item.purity / 100).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
        valuations.append(dict(item_id=item.pk, value=str(value), rate_id=row["rate"].pk,
            rate_evidence=row["evidence"], photo=_photo_evidence(item, required)))
    policy = KhataPolicyRevision.objects.filter(workspace=workspace).order_by("-number").first()
    position = account_position(account) or DrawPosition(terms.agreed_limit, 0, terms.agreed_limit)
    balances = account_balances(workspace=workspace, actor=actor, account_id=account.pk)
    snapshot = dict(schema="khata-opening/1", account_id=account.pk, date=day.isoformat(), agreement_id=terms.pk,
        last_sequence=account.operations.aggregate(last=Max("sequence"))["last"] or 0,
        valuations=valuations, photos_required=required, policy_id=policy.pk if policy else None,
        overdue_policy=policy.overdue if policy else "WARN", exchange_policy=policy.exchange if policy else "WARN",
        principal=str(position.principal), unused=str(position.unused), overdue_interest=str(balances["overdue_interest"]),
        drawable=str(available_draw(position, collateral_value=sum((Decimal(v["value"]) for v in valuations), Decimal(0)), ltv=terms.ltv)),
        license={"id": license.pk, "number": license.license_number, "expires_on": str(license.expires_on),
                 "revision_id": license.revisions.order_by("-revision_number").values_list("pk", flat=True).first()} if license else None)
    return terms, snapshot


def preview_opening(*, workspace, actor, account_id):
    with _locked(workspace, actor, account_id, "data.view") as account:
        if account.opened_on is not None:
            raise KhataDraftError("Opening approval is already complete.")
        _, snapshot = _review(account, workspace=workspace, actor=actor, day=timezone.localdate())
        return {"snapshot": snapshot, "review_hash": _hash(snapshot)}


def _save_valuations(op, snapshot):
    for row in snapshot["valuations"]:
        KhataCollateralValuation.objects.create(workspace_id=op.workspace_id, operation=op,
            item_id=row["item_id"], rate_id=row["rate_id"], value=row["value"], rate_evidence=row["rate_evidence"])


def approve_opening(*, workspace, actor, account_id, request_key, business_date, review_hash):
    key = _key(request_key)
    fingerprint = _hash(dict(actor=actor.pk, date=business_date, review=review_hash, kind="APPROVE"))
    with _locked(workspace, actor, account_id, "loan.approve") as account:
        if op := _retry(account, key, fingerprint):
            return op
        if account.opened_on is not None:
            raise KhataDraftError("An active khata requires an agreement-change workflow.")
        terms, snapshot = _review(account, workspace=workspace, actor=actor, day=business_date)
        if _hash(snapshot) != review_hash:
            raise KhataDraftError("Khata changed after review; refresh before approval.")
        op = _operation(account, actor, key, fingerprint, "APPROVE", business_date, snapshot,
            agreement=terms, policy_id=snapshot["policy_id"])
        _save_valuations(op, snapshot)
        return op


def _withdrawal_review(account, workspace, actor, day, value):
    terms, snapshot = _review(account, workspace=workspace, actor=actor, day=day)
    changes = activated_agreements(account)
    approval = changes[-1].approval if changes else account.operations.filter(kind="APPROVE").order_by("-sequence").first()
    if approval is None or approval.agreement_id != terms.pk:
        raise KhataDraftError("Approve the current agreement before withdrawing.")
    if account.opened_on is None:
        if approval.business_date != day or any(approval.evidence[k] != snapshot[k] for k in (
            "valuations", "photos_required", "license")):
            raise KhataDraftError("Opening approval is stale; review and approve current evidence.")
    if value > Decimal(snapshot["drawable"]):
        raise KhataDraftError("Withdrawal exceeds unused entitlement or current collateral backing.")
    overdue = Decimal(snapshot["overdue_interest"]) > 0
    if overdue and snapshot["overdue_policy"] == "BLOCK":
        raise KhataDraftError("Workspace policy blocks withdrawals while interest is overdue.")
    snapshot.update(approval_id=approval.pk, amount=str(value), warnings=["Interest is overdue."] if overdue else [])
    return terms, approval, snapshot


def preview_withdrawal(*, workspace, actor, account_id, value):
    value = amount(value, positive=True).quantize(Decimal("0.01"))
    with _locked(workspace, actor, account_id, "data.view") as account:
        _, _, snapshot = _withdrawal_review(account, workspace, actor, timezone.localdate(), value)
        return {"snapshot": snapshot, "review_hash": _hash(snapshot)}


def record_withdrawal(*, workspace, actor, account_id, request_key, business_date, value, review_hash, payment_reference):
    value = amount(value, positive=True).quantize(Decimal("0.01"))
    if not payment_reference.strip():
        raise KhataDraftError("Record the actual cash handover or payment reference.")
    key = _key(request_key)
    fingerprint = _hash(dict(actor=actor.pk, date=business_date, amount=str(value), review=review_hash,
        payment_reference=payment_reference.strip(), kind="WITHDRAW"))
    with _locked(workspace, actor, account_id, "loan.disburse") as account:
        if op := _retry(account, key, fingerprint):
            return op
        terms, approval, snapshot = _withdrawal_review(account, workspace, actor, business_date, value)
        if _hash(snapshot) != review_hash:
            raise KhataDraftError("Khata changed after review; refresh before withdrawing.")
        snapshot["payment_reference"] = payment_reference.strip()
        op = _operation(account, actor, key, fingerprint, "WITHDRAW", business_date, snapshot,
            agreement=terms, approval=approval, amount=value, policy_id=snapshot["policy_id"])
        _save_valuations(op, snapshot)
        return op
