"""Read models for regulatory license readiness and the license register."""

from dataclasses import dataclass
from datetime import date

from django.utils import timezone

from apps.tenant_apps.loans.models import (
    LoanLicense,
    LoanLicenseRevision,
    current_tenant_workspace_id,
)


class LoanLicenseRegisterError(ValueError):
    pass


@dataclass(frozen=True)
class LoanLicenseRegisterRow:
    license: LoanLicense
    current_revision: LoanLicenseRevision | None
    status: str
    days_remaining: int
    blockers: tuple[str, ...]


def get_loan_license_register(
    workspace_id: int,
    *,
    as_of_date: date | None = None,
    expiry_warning_days: int = 30,
) -> tuple[LoanLicenseRegisterRow, ...]:
    active_workspace_id = current_tenant_workspace_id()
    if active_workspace_id is None or workspace_id != active_workspace_id:
        raise LoanLicenseRegisterError(
            "License register must belong to the active workspace."
        )
    if expiry_warning_days < 0:
        raise LoanLicenseRegisterError("Expiry warning days cannot be negative.")
    as_of_date = as_of_date or timezone.localdate()
    licenses = LoanLicense.objects.filter(workspace_id=workspace_id).prefetch_related(
        "revisions"
    )
    rows = []
    for license in licenses:
        revisions = tuple(license.revisions.all())
        current_revision = revisions[-1] if revisions else None
        days_remaining = (license.expires_on - as_of_date).days
        blockers = []
        if not license.is_active:
            blockers.append("License is inactive.")
        if days_remaining < 0:
            blockers.append("License is expired.")
        if current_revision is None or not current_revision.has_document:
            blockers.append("Current license document is missing.")
        if not license.is_active:
            status = "INACTIVE"
        elif days_remaining < 0:
            status = "EXPIRED"
        elif current_revision is None or not current_revision.has_document:
            status = "DOCUMENT_MISSING"
        elif days_remaining <= expiry_warning_days:
            status = "EXPIRING"
        else:
            status = "READY"
        rows.append(
            LoanLicenseRegisterRow(
                license=license,
                current_revision=current_revision,
                status=status,
                days_remaining=days_remaining,
                blockers=tuple(blockers),
            )
        )
    return tuple(rows)


__all__ = [
    "LoanLicenseRegisterError",
    "LoanLicenseRegisterRow",
    "get_loan_license_register",
]
