"""Reviewed agreement changes; approval alone never changes the live contract."""
from decimal import Decimal

from django.db.models import Max
from django.utils import timezone

from apps.tenant_apps.loans.domain.khata import amount, revise_limit
from apps.tenant_apps.loans.models import KhataOperation
from apps.tenant_apps.loans.selectors.khata import account_position, effective_agreement
from .action_access import require_workspace_action
from .khata_accounts import KhataDraftError, _hash, _key
from .khata_opening import _locked, _operation, _retry
from .khata_servicing import _active


def _review(account, day, repayment, outgoing=(), workspace=None, actor=None):
    _active(account, day)
    current = effective_agreement(account)
    proposal = account.agreement_revisions.order_by("-number").first()
    if proposal.pk == current.pk or proposal.number <= current.number:
        raise KhataDraftError("Save a new agreement proposal before approval.")
    if proposal.intended_on != day:
        raise KhataDraftError("Save today's proposal; stale approvals cannot be backdated.")
    if any(getattr(proposal, field) != getattr(current, field)
           for field in ("ltv", "frequency", "lender_name", "lender_address", "contract_version")):
        raise KhataDraftError("Active changes preserve LTV, payment frequency and lender identity.")
    if (proposal.agreed_limit, proposal.monthly_rate) == (current.agreed_limit, current.monthly_rate):
        raise KhataDraftError("The proposed limit and rate are already active.")
    if account.interest_periods.filter(end_on__gt=day).exists():
        raise KhataDraftError("A change cannot reinterpret finalized interest; use a reviewed correction.")
    position = account_position(account)
    updated = revise_limit(position, new_limit=proposal.agreed_limit, principal_repayment=repayment)
    license = account.series.license
    if proposal.agreed_limit > current.agreed_limit:
        if not account.series.is_active or account.borrower.status != "ACTIVE":
            raise KhataDraftError("An active series and borrower are required to increase the limit.")
        if license and (not license.is_active or license.is_legacy_reference or license.issued_on > day or license.is_expired(day)):
            raise KhataDraftError("The associated licence is unavailable for a limit increase.")
    snapshot = dict(schema="khata-revision/1", account_id=account.pk, date=day.isoformat(),
        last_sequence=account.operations.aggregate(last=Max("sequence"))["last"],
        current_agreement_id=current.pk, proposal_id=proposal.pk,
        old_limit=str(current.agreed_limit), new_limit=str(proposal.agreed_limit),
        old_monthly_rate=str(current.monthly_rate), new_monthly_rate=str(proposal.monthly_rate),
        principal=str(position.principal), unused=str(position.unused),
        principal_repayment=str(repayment), new_principal=str(updated.principal), new_unused=str(updated.unused),
        frequency=current.frequency, ltv=str(current.ltv), opened_on=account.opened_on.isoformat(),
        series_active=account.series.is_active, borrower_status=account.borrower.status,
        license={"id": license.pk, "active": license.is_active, "legacy": license.is_legacy_reference,
            "issued_on": str(license.issued_on), "expires_on": str(license.expires_on),
            "revision_id": license.revisions.order_by("-revision_number").values_list("pk", flat=True).first()} if license else None)
    if outgoing:
        from .khata_collateral import reduction_snapshot
        if proposal.agreed_limit >= current.agreed_limit:
            raise KhataDraftError("Collateral returns require a formal limit reduction.")
        snapshot.update(reduction_snapshot(account, workspace, actor, day, outgoing, updated.principal, current.ltv))
    return proposal, snapshot


def preview_revision(*, workspace, actor, account_id, principal_repayment="0", outgoing_ids=()):
    from .khata_collateral import _ids
    repayment = amount(principal_repayment).quantize(Decimal("0.01"))
    with _locked(workspace, actor, account_id, "data.view") as account:
        _, snapshot = _review(account, timezone.localdate(), repayment, _ids(outgoing_ids), workspace, actor)
        return {"snapshot": snapshot, "review_hash": _hash(snapshot)}


def approve_revision(*, workspace, actor, account_id, request_key, business_date,
                     review_hash, agreement_reference, principal_repayment="0", outgoing_ids=()):
    from .khata_collateral import _ids
    outgoing = _ids(outgoing_ids)
    repayment = amount(principal_repayment).quantize(Decimal("0.01"))
    if not agreement_reference.strip():
        raise KhataDraftError("Record the borrower's agreement/consent reference.")
    key = _key(request_key)
    fingerprint = _hash(dict(kind="TERMS_OK", actor=actor.pk, date=business_date,
        review=review_hash, repayment=str(repayment), outgoing=outgoing, agreement_reference=agreement_reference.strip()))
    with _locked(workspace, actor, account_id, "loan.approve") as account:
        if op := _retry(account, key, fingerprint):
            return op
        proposal, snapshot = _review(account, business_date, repayment, outgoing, workspace, actor)
        if _hash(snapshot) != review_hash:
            raise KhataDraftError("Khata changed after review; refresh before approving terms.")
        return _operation(account, actor, key, fingerprint, "TERMS_OK", business_date,
            {"schema": "khata-revision/1", "review": snapshot,
             "agreement_reference": agreement_reference.strip()}, agreement=proposal)


def _approval(account, approval_id):
    return KhataOperation.objects.get(workspace_id=account.workspace_id, account=account, pk=approval_id, kind="TERMS_OK")


def _activation_review(account, approval, day, workspace, actor):
    repayment = amount(approval.evidence["review"]["principal_repayment"]).quantize(Decimal("0.01"))
    proposal, snapshot = _review(account, day, repayment, approval.evidence["review"].get("outgoing_ids", []), workspace, actor)
    original = approval.evidence["review"]
    if (approval.agreement_id != proposal.pk or approval.business_date != day
        or snapshot["last_sequence"] != approval.sequence
        or any(snapshot[k] != original[k] for k in snapshot if k != "last_sequence")):
        raise KhataDraftError("Agreement approval is stale; review and approve the current account again.")
    snapshot["approval_id"] = approval.pk
    return proposal, repayment, snapshot


def preview_activation(*, workspace, actor, account_id, approval_id):
    with _locked(workspace, actor, account_id, "data.view") as account:
        _, _, snapshot = _activation_review(account, _approval(account, approval_id), timezone.localdate(), workspace, actor)
        return {"snapshot": snapshot, "review_hash": _hash(snapshot)}


def activate_revision(*, workspace, actor, account_id, approval_id, request_key, business_date,
                      review_hash, payment_reference=""):
    key = _key(request_key)
    fingerprint = _hash(dict(kind="REVISE", actor=actor.pk, date=business_date, approval_id=approval_id,
        review=review_hash, payment_reference=payment_reference.strip()))
    with _locked(workspace, actor, account_id, "data.view") as account:
        approval = _approval(account, approval_id)
        repayment = amount(approval.evidence["review"]["principal_repayment"])
        # Approval never confers permission to collect cash. A cashier may execute
        # an approved repayment; non-cash activation remains an approver action.
        require_workspace_action(workspace, actor, "loan.repay" if repayment else "loan.approve")
        if approval.evidence["review"].get("outgoing_ids"):
            require_workspace_action(workspace, actor, "loan.release")
        if op := _retry(account, key, fingerprint):
            return op
        proposal, repayment, snapshot = _activation_review(account, approval, business_date, workspace, actor)
        if _hash(snapshot) != review_hash:
            raise KhataDraftError("Khata changed after review; refresh before activating terms.")
        if repayment and not payment_reference.strip():
            raise KhataDraftError("Record the actual principal repayment reference.")
        snapshot["payment_reference"] = payment_reference.strip()
        op = _operation(account, actor, key, fingerprint, "REVISE", business_date, snapshot,
            agreement=proposal, approval=approval, amount=repayment)
        if snapshot.get("outgoing_ids"):
            from .khata_collateral import _reserve
            from .khata_opening import _save_valuations
            _save_valuations(op, snapshot)
            _reserve(op, snapshot["outgoing_ids"])
        return op
