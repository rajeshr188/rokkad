from __future__ import annotations

from datetime import date

from django.core.exceptions import ValidationError
from django.db import transaction
from django_tenants.utils import get_public_schema_name, schema_context

from apps.orgs.audit import AuditLog
from apps.tenant_apps.loans.domain import LoanDocumentKind
from apps.tenant_apps.loans.models import (
    LoanLicense,
    LoanNumberSequence,
    LoanSeries,
    current_tenant_workspace_id,
)


class LicenseSeriesError(ValueError):
    """Raised when a license, series, or sequence operation is not allowed."""


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
) -> LoanLicense:
    _require_active_workspace(workspace.pk)
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
    return license


def update_license(license: LoanLicense, *, actor=None, **changes) -> LoanLicense:
    allowed = {"name", "license_number", "issuing_authority", "issued_on", "expires_on", "notes"}
    unexpected = set(changes) - allowed
    if unexpected:
        raise LicenseSeriesError(
            f"Unsupported license fields: {', '.join(sorted(unexpected))}."
        )
    _require_active_workspace(license.workspace_id)
    for field, value in changes.items():
        setattr(license, field, value)
    license.updated_by = actor
    license.full_clean()
    license.save(update_fields=[*changes, "updated_by", "updated_at"])
    return license


def activate_license(
    license: LoanLicense, *, actor=None, as_of_date: date | None = None
) -> LoanLicense:
    _require_active_workspace(license.workspace_id)
    if license.is_expired(as_of_date):
        raise LicenseSeriesError("An expired license cannot be activated.")
    if not license.is_active:
        license.is_active = True
        license.updated_by = actor
        license.save(update_fields=["is_active", "updated_by", "updated_at"])
    return license


def expire_license(license: LoanLicense, *, actor=None) -> LoanLicense:
    _require_active_workspace(license.workspace_id)
    if license.is_active:
        license.is_active = False
        license.updated_by = actor
        license.save(update_fields=["is_active", "updated_by", "updated_at"])
    return license


def create_series(
    *, license: LoanLicense, name: str, code: str, is_active: bool = True
) -> LoanSeries:
    _require_active_workspace(license.workspace_id)
    series = LoanSeries(license=license, name=name, code=code, is_active=is_active)
    series.full_clean()
    series.save()
    return series


def update_series(series: LoanSeries, *, name: str | None = None, code: str | None = None) -> LoanSeries:
    _require_active_workspace(series.workspace_id)
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


def set_series_active(series: LoanSeries, *, is_active: bool) -> LoanSeries:
    _require_active_workspace(series.workspace_id)
    if series.is_active != is_active:
        series.is_active = is_active
        series.save(update_fields=["is_active", "updated_at"])
    return series


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
    with schema_context(get_public_schema_name()):
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
