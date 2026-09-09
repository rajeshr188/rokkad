from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from .action_access import require_setup_administration
from apps.orgs.audit import AuditLog
from apps.tenant_apps.loans.domain import LoanDocumentKind
from apps.tenant_apps.loans.models import (
    LoanLicense,
    LoanLicenseRevision,
    LoanNumberSequence,
    LoanSeries,
    current_tenant_workspace_id,
)


class LicenseSeriesError(ValueError):
    """Raised when a license, series, or sequence operation is not allowed."""


MAX_LICENSE_DOCUMENT_BYTES = 10 * 1024 * 1024


@transaction.atomic
def create_license(
    *,
    workspace,
    name: str,
    license_number: str,
    issued_on: date,
    expires_on: date,
    actor=None,
    issuing_authority: str = "",
    notes: str = "",
    supporting_document=None,
    request=None,
) -> LoanLicense:
    _require_active_workspace(workspace.pk)
    require_setup_administration(workspace.pk, actor)
    license = LoanLicense(
        workspace=workspace,
        name=name,
        license_number=license_number,
        issuing_authority=issuing_authority,
        issued_on=issued_on,
        expires_on=expires_on,
        notes=notes,
        created_by=actor,
        updated_by=actor,
    )
    license.full_clean()
    license.save()
    revision = _record_license_revision(
        license,
        kind=LoanLicenseRevision.Kind.INITIAL,
        actor=actor,
        supporting_document=supporting_document,
    )
    _audit_license_revision(revision, actor=actor, request=request)
    return license


@transaction.atomic
def update_license(
    license: LoanLicense,
    *,
    actor=None,
    supporting_document=None,
    request=None,
    **changes,
) -> LoanLicense:
    allowed = {"name", "license_number", "issuing_authority", "issued_on", "expires_on", "notes"}
    unexpected = set(changes) - allowed
    if unexpected:
        raise LicenseSeriesError(
            f"Unsupported license fields: {', '.join(sorted(unexpected))}."
        )
    _require_active_workspace(license.workspace_id)
    require_setup_administration(license.workspace_id, actor)
    license = LoanLicense.objects.select_for_update().get(pk=license.pk)
    for field, value in changes.items():
        setattr(license, field, value)
    license.updated_by = actor
    license.full_clean()
    license.save(update_fields=[*changes, "updated_by", "updated_at"])
    revision = _record_license_revision(
        license,
        kind=LoanLicenseRevision.Kind.AMENDMENT,
        actor=actor,
        supporting_document=supporting_document,
    )
    _audit_license_revision(revision, actor=actor, request=request)
    return license


@transaction.atomic
def renew_license(
    license: LoanLicense,
    *,
    issued_on: date,
    expires_on: date,
    supporting_document=None,
    actor=None,
    issuing_authority: str | None = None,
    license_number: str | None = None,
    notes: str = "",
    request=None,
) -> LoanLicense:
    """Append renewal evidence and update the current license projection."""
    _require_active_workspace(license.workspace_id)
    require_setup_administration(license.workspace_id, actor)
    if supporting_document is None:
        raise LicenseSeriesError("A supporting license document is required for renewal.")
    if expires_on < timezone.localdate():
        raise LicenseSeriesError("A renewal cannot already be expired.")
    license = LoanLicense.objects.select_for_update().get(pk=license.pk)
    license.issued_on = issued_on
    license.expires_on = expires_on
    if issuing_authority is not None:
        license.issuing_authority = issuing_authority
    if license_number is not None:
        license.license_number = license_number
    license.notes = notes
    license.is_active = True
    license.updated_by = actor
    license.full_clean()
    license.save(
        update_fields=[
            "issued_on",
            "expires_on",
            "issuing_authority",
            "license_number",
            "notes",
            "is_active",
            "updated_by",
            "updated_at",
        ]
    )
    revision = _record_license_revision(
        license,
        kind=LoanLicenseRevision.Kind.RENEWAL,
        actor=actor,
        supporting_document=supporting_document,
    )
    _audit_license_revision(revision, actor=actor, request=request)
    return license


def activate_license(
    license: LoanLicense, *, actor=None, as_of_date: date | None = None
) -> LoanLicense:
    _require_active_workspace(license.workspace_id)
    require_setup_administration(license.workspace_id, actor)
    if license.is_expired(as_of_date):
        raise LicenseSeriesError("An expired license cannot be activated.")
    if not license.is_active:
        license.is_active = True
        license.updated_by = actor
        license.save(update_fields=["is_active", "updated_by", "updated_at"])
    return license


def expire_license(license: LoanLicense, *, actor=None) -> LoanLicense:
    _require_active_workspace(license.workspace_id)
    require_setup_administration(license.workspace_id, actor)
    if license.is_active:
        license.is_active = False
        license.updated_by = actor
        license.save(update_fields=["is_active", "updated_by", "updated_at"])
    return license


def create_series(
    *, license: LoanLicense, name: str, code: str, is_active: bool = True, actor=None
) -> LoanSeries:
    _require_active_workspace(license.workspace_id)
    require_setup_administration(license.workspace_id, actor)
    series = LoanSeries(license=license, name=name, code=code, is_active=is_active)
    series.full_clean()
    series.save()
    return series


def update_series(series: LoanSeries, *, name: str | None = None, code: str | None = None, actor=None) -> LoanSeries:
    _require_active_workspace(series.workspace_id)
    require_setup_administration(series.workspace_id, actor)
    update_fields = ["updated_at"]
    if name is not None:
        series.name = name
        update_fields.append("name")
    if code is not None:
        series.code = code
        update_fields.append("code")
    series.full_clean()
    series.save(update_fields=update_fields)
    return series


def set_series_active(series: LoanSeries, *, is_active: bool, actor=None) -> LoanSeries:
    _require_active_workspace(series.workspace_id)
    require_setup_administration(series.workspace_id, actor)
    if series.is_active != is_active:
        series.is_active = is_active
        series.save(update_fields=["is_active", "updated_at"])
    return series


@transaction.atomic
def create_configured_series(
    *,
    license: LoanLicense,
    name: str,
    code: str,
    is_active: bool,
    pawn_loan_prefix: str,
    release_prefix: str,
    number_width: int,
    maximum_number: int,
    actor=None,
    request=None,
) -> LoanSeries:
    """Create a series and both required document sequences atomically."""
    require_setup_administration(license.workspace_id, actor)

    series = create_series(
        license=license, name=name, code=code, is_active=is_active, actor=actor
    )
    _configure_required_sequences(
        series,
        pawn_loan_prefix=pawn_loan_prefix,
        release_prefix=release_prefix,
        number_width=number_width,
        maximum_number=maximum_number,
        actor=actor,
        request=request,
    )
    return series


@transaction.atomic
def update_configured_series(
    series: LoanSeries,
    *,
    name: str,
    code: str,
    is_active: bool,
    pawn_loan_prefix: str,
    release_prefix: str,
    number_width: int,
    maximum_number: int,
    actor=None,
    request=None,
) -> LoanSeries:
    """Update series identity, availability, and both sequences atomically."""
    require_setup_administration(series.workspace_id, actor)

    update_series(series, name=name, code=code, actor=actor)
    set_series_active(series, is_active=is_active, actor=actor)
    _configure_required_sequences(
        series,
        pawn_loan_prefix=pawn_loan_prefix,
        release_prefix=release_prefix,
        number_width=number_width,
        maximum_number=maximum_number,
        actor=actor,
        request=request,
    )
    return series


def _configure_required_sequences(
    series,
    *,
    pawn_loan_prefix,
    release_prefix,
    number_width,
    maximum_number,
    actor,
    request,
):
    common = {
        "series": series,
        "width": number_width,
        "maximum_number": maximum_number,
        "actor": actor,
        "request": request,
    }
    configure_sequence(
        document_kind=LoanDocumentKind.PAWN_LOAN,
        prefix=pawn_loan_prefix,
        **common,
    )
    configure_sequence(
        document_kind=LoanDocumentKind.PAWN_LOAN_RELEASE,
        prefix=release_prefix,
        **common,
    )


def configure_sequence(
    *,
    series: LoanSeries,
    document_kind: LoanDocumentKind | str,
    prefix: str,
    width: int = 5,
    maximum_number: int = 10000,
    actor=None,
    request=None,
) -> LoanNumberSequence:
    _require_active_workspace(series.workspace_id)
    require_setup_administration(series.workspace_id, actor)
    kind = LoanDocumentKind(document_kind).value
    with transaction.atomic():
        sequence, created = LoanNumberSequence.objects.select_for_update().get_or_create(
            series=series,
            document_kind=kind,
            defaults={
                "prefix": prefix,
                "width": width,
                "maximum_number": maximum_number,
                "updated_by": actor,
            },
        )
        old_configuration = None
        if not created:
            old_configuration = _sequence_configuration(sequence)
            sequence.prefix = prefix
            sequence.width = width
            sequence.maximum_number = maximum_number
            sequence.updated_by = actor
            sequence.full_clean()
            sequence.save(
                update_fields=["prefix", "width", "maximum_number", "updated_by", "updated_at"]
            )
        new_configuration = _sequence_configuration(sequence)

    _audit_sequence_configuration(
        sequence=sequence,
        actor=actor,
        request=request,
        created=created,
        old_configuration=old_configuration,
        new_configuration=new_configuration,
    )
    return sequence


def assert_series_can_issue(
    series: LoanSeries, *, as_of_date: date | None = None
) -> None:
    _require_active_workspace(series.workspace_id)
    if not series.is_active:
        raise LicenseSeriesError("The selected loan series is inactive.")
    if not series.license.is_active:
        raise LicenseSeriesError("The selected loan license is inactive.")
    if series.license.is_expired(as_of_date):
        raise LicenseSeriesError("The selected loan license has expired.")


def _require_active_workspace(workspace_id: int) -> None:
    active_workspace_id = current_tenant_workspace_id()
    if active_workspace_id is None:
        raise LicenseSeriesError("License operations require an active tenant schema.")
    if workspace_id != active_workspace_id:
        raise LicenseSeriesError("The object must belong to the active workspace.")


def _record_license_revision(
    license: LoanLicense,
    *,
    kind,
    actor,
    supporting_document=None,
) -> LoanLicenseRevision:
    document = _validated_license_document(supporting_document)
    latest = (
        LoanLicenseRevision.objects.filter(license=license).aggregate(
            value=Max("revision_number")
        )["value"]
        or 0
    )
    revision = LoanLicenseRevision(
        license=license,
        revision_number=latest + 1,
        kind=kind,
        name=license.name,
        license_number=license.license_number,
        issuing_authority=license.issuing_authority,
        issued_on=license.issued_on,
        expires_on=license.expires_on,
        notes=license.notes,
        created_by=actor,
    )
    if document is not None:
        content, filename, mime_type = document
        revision.original_filename = filename
        revision.mime_type = mime_type
        revision.sha256 = hashlib.sha256(content).hexdigest()
        revision.byte_size = len(content)
        revision.supporting_document.save(filename, ContentFile(content), save=False)
    revision.save()
    return revision


def _validated_license_document(uploaded):
    if uploaded is None:
        return None
    content = uploaded.read()
    try:
        uploaded.seek(0)
    except (AttributeError, OSError):
        pass
    if not content:
        raise LicenseSeriesError("The supporting license document is empty.")
    if len(content) > MAX_LICENSE_DOCUMENT_BYTES:
        raise LicenseSeriesError("The supporting license document exceeds 10 MB.")
    if content.startswith(b"%PDF-"):
        mime_type = "application/pdf"
    elif content.startswith(b"\x89PNG\r\n\x1a\n"):
        mime_type = "image/png"
    elif content.startswith(b"\xff\xd8\xff"):
        mime_type = "image/jpeg"
    else:
        raise LicenseSeriesError("Only PDF, PNG, or JPEG license documents are supported.")
    filename = Path(getattr(uploaded, "name", "license-document")).name[:255]
    return bytes(content), filename, mime_type


def _audit_license_revision(revision, *, actor, request=None):
    workspace = revision.license.workspace
    AuditLog.log(
            "SETTINGS_UPDATE",
            user=actor,
            company=workspace,
            description=(
                f"Recorded {revision.get_kind_display().lower()} evidence for "
                f"loan license {revision.license_number}."
            ),
            data={
                "entity": "loan_license_revision",
                "license_id": revision.license_id,
                "revision_id": revision.pk,
                "revision_number": revision.revision_number,
                "kind": revision.kind,
                "document_sha256": revision.sha256,
            },
            request=request,
            success=True,
    )


def _sequence_configuration(sequence: LoanNumberSequence) -> dict:
    return {
        "prefix": sequence.prefix,
        "width": sequence.width,
        "maximum_number": sequence.maximum_number,
    }


def _audit_sequence_configuration(
    *, sequence, actor, request, created, old_configuration, new_configuration
) -> None:
    workspace = sequence.series.license.workspace
    AuditLog.log(
            "SETTINGS_UPDATE",
            user=actor,
            company=workspace,
            description=f"Configured {sequence.document_kind} numbering for series {sequence.series.code}.",
            data={
                "entity": "loan_number_sequence",
                "sequence_id": sequence.pk,
                "series_id": sequence.series_id,
                "created": created,
                "old": old_configuration,
                "new": new_configuration,
            },
            request=request,
            success=True,
    )
