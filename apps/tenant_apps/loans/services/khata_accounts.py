"""Authorized khata setup, numbered drafts and immutable agreement proposals."""
import hashlib
import json
import uuid

from django.utils import timezone

from apps.orgs.models import Company
from apps.tenancy.context import workspace_context
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.loans.domain.khata import amount, decimal_rate
from apps.tenant_apps.loans.models import (
    KhataSeries, KhataAccount, KhataAgreementRevision, LoanLicense, LoanNumberSequence, PawnLoan,
)
from .action_access import require_setup_administration, require_workspace_action


class KhataDraftError(ValueError):
    pass


def _hash(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def _key(value):
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise KhataDraftError("A valid request UUID is required.") from exc


def _today(value):
    if value != timezone.localdate():
        raise KhataDraftError("Khata entries must use today's business date.")


def _terms(*, agreed_limit, monthly_rate, ltv, frequency, intended_on, lender_name, lender_address, reason):
    values = dict(agreed_limit=amount(agreed_limit, positive=True).quantize(amount("0.01")),
                  monthly_rate=decimal_rate(monthly_rate).normalize(), ltv=decimal_rate(ltv, ltv=True).normalize(),
                  frequency=frequency, intended_on=intended_on,
                  lender_name=lender_name.strip(), lender_address=lender_address.strip(), reason=reason.strip())
    if frequency not in KhataAgreementRevision.Frequency.values:
        raise KhataDraftError("Choose monthly or annual collection.")
    if not all(values[key] for key in ("lender_name", "lender_address", "reason")):
        raise KhataDraftError("Lender name, address and a reason are required.")
    return values


def _series_ready(series, day):
    if not series.is_active or series.next_number > series.maximum_number:
        raise KhataDraftError("Khata series is inactive or its number range is exhausted.")
    if series.license_id:
        license = series.license
        if (not license.is_active or license.is_legacy_reference or license.is_expired(day)
                or license.issued_on > day):
            raise KhataDraftError("The associated licence is not available for a new khata.")


def _next_number(series):
    return f"{series.prefix}{series.next_number:0{series.width}d}"


def create_series(*, workspace, actor, code, name, prefix="KH", width=5, maximum_number=99999, license_id=None):
    with workspace_context(workspace.pk):
        require_setup_administration(workspace.pk, actor)
        Company.objects.select_for_update().get(pk=workspace.pk)
        if license_id is not None and not LoanLicense.objects.filter(workspace=workspace, pk=license_id).exists():
            raise KhataDraftError("Select a licence in this workspace.")
        prefix = prefix.strip().upper()
        if LoanNumberSequence.objects.filter(workspace=workspace, prefix=prefix).exists():
            raise KhataDraftError("Choose a prefix different from ordinary-loan sequences.")
        if type(width) is not int or not 1 <= width <= 12 or type(maximum_number) is not int or not 1 <= maximum_number < 10 ** width:
            raise KhataDraftError("The number ceiling must fit the selected width (1-12 digits).")
        series = KhataSeries(workspace=workspace, created_by=actor, license_id=license_id,
            code=code.strip().upper(), name=name.strip(), prefix=prefix, width=width, maximum_number=maximum_number)
        series.full_clean()
        series.save()
        return series


def preview_number(*, workspace, actor, series_id):
    with workspace_context(workspace.pk):
        require_workspace_action(workspace, actor, "data.view")
        series = KhataSeries.objects.select_related("license").get(workspace=workspace, pk=series_id)
        _series_ready(series, timezone.localdate())
        return _next_number(series)


def create_draft(*, workspace, actor, series_id, borrower_id, request_key, intended_on,
                 agreed_limit, monthly_rate, ltv, frequency, lender_name, lender_address):
    key = _key(request_key)
    values = _terms(agreed_limit=agreed_limit, monthly_rate=monthly_rate, ltv=ltv, frequency=frequency,
                   intended_on=intended_on, lender_name=lender_name, lender_address=lender_address, reason="Initial agreement proposal")
    fingerprint = _hash(dict(values, actor=actor.pk, series=series_id, borrower=borrower_id))
    with workspace_context(workspace.pk):
        require_workspace_action(workspace, actor, "data.create")
        Company.objects.select_for_update().get(pk=workspace.pk)
        existing = KhataAccount.objects.filter(workspace=workspace, request_key=key).first()
        if existing:
            if existing.request_sha256 != fingerprint:
                raise KhataDraftError("Request UUID was already used with different instructions.")
            return existing
        _today(intended_on)
        series = KhataSeries.objects.select_for_update().get(workspace=workspace, pk=series_id)
        _series_ready(series, intended_on)
        if not Party.objects.filter(workspace=workspace, pk=borrower_id, status="ACTIVE").exists():
            raise KhataDraftError("Select an active borrower in this workspace.")
        number = _next_number(series)
        if PawnLoan.objects.filter(workspace=workspace, loan_number=number).exists():
            raise KhataDraftError("This number conflicts with an ordinary loan; use a different series.")
        account = KhataAccount(workspace=workspace, series=series, borrower_id=borrower_id,
            account_number=number, created_by=actor, request_key=key, request_sha256=fingerprint)
        account.full_clean()
        account.save()  # Database trigger atomically advances and freezes the series.
        revision = KhataAgreementRevision(workspace=workspace, account=account, number=1,
            created_by=actor, request_key=key, request_sha256=fingerprint, **values)
        revision.full_clean()
        revision.save()
        return account


def propose_revision(*, workspace, actor, account_id, expected_revision, request_key, intended_on,
                     agreed_limit, monthly_rate, ltv, frequency, lender_name, lender_address, reason):
    key = _key(request_key)
    values = _terms(agreed_limit=agreed_limit, monthly_rate=monthly_rate, ltv=ltv, frequency=frequency,
        intended_on=intended_on, lender_name=lender_name, lender_address=lender_address, reason=reason)
    fingerprint = _hash(dict(values, actor=actor.pk, account=account_id, expected_revision=expected_revision))
    with workspace_context(workspace.pk):
        require_workspace_action(workspace, actor, "data.edit")
        Company.objects.select_for_update().get(pk=workspace.pk)
        account = KhataAccount.objects.select_for_update().get(workspace=workspace, pk=account_id)
        existing = KhataAgreementRevision.objects.filter(workspace=workspace, request_key=key).first()
        if existing:
            if existing.account_id != account.pk or existing.request_sha256 != fingerprint:
                raise KhataDraftError("Request UUID was already used with different instructions.")
            return existing
        _today(intended_on)
        latest = account.agreement_revisions.order_by("-number").first()
        if account.state not in (KhataAccount.State.DRAFT, KhataAccount.State.APPROVED, KhataAccount.State.ACTIVE) or latest is None or latest.number != expected_revision:
            raise KhataDraftError("The account changed; refresh the agreement before saving.")
        if account.opened_on:
            from apps.tenant_apps.loans.selectors.khata import effective_agreement
            active = effective_agreement(account)
            if any(values[field] != getattr(active, field) for field in ("ltv", "frequency", "lender_name", "lender_address")):
                raise KhataDraftError("Active changes preserve LTV, payment frequency and lender identity.")
            if values["agreed_limit"] == active.agreed_limit and values["monthly_rate"] == active.monthly_rate:
                raise KhataDraftError("Change the agreed limit or monthly rate; the current terms are already active.")
        revision = KhataAgreementRevision(workspace=workspace, account=account, number=latest.number + 1,
            created_by=actor, request_key=key, request_sha256=fingerprint, **values)
        revision.full_clean()
        revision.save()
        return revision


def cancel_draft(*, workspace, actor, account_id, reason):
    reason = reason.strip()
    if not reason:
        raise KhataDraftError("A cancellation reason is required.")
    with workspace_context(workspace.pk):
        require_workspace_action(workspace, actor, "data.edit")
        account = KhataAccount.objects.select_for_update().get(workspace=workspace, pk=account_id)
        if account.state == KhataAccount.State.CANCELLED:
            if account.cancellation_reason != reason or account.cancelled_by_id != actor.pk:
                raise KhataDraftError("The draft was already cancelled with different instructions.")
            return account
        from apps.tenant_apps.loans.selectors.khata import held_items
        if account.opened_on is not None or held_items(account).exists():
            raise KhataDraftError("Return unopened collateral before cancellation; active khatas require settlement.")
        account.state = KhataAccount.State.CANCELLED
        account.cancelled_by = actor
        account.cancelled_at = timezone.now()
        account.cancellation_reason = reason
        account.full_clean()
        account.save(update_fields=("state", "cancelled_by", "cancelled_at", "cancellation_reason"))
        return account
