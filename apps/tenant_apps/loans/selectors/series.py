"""Series available for new lending; retained registers remain ordinary records."""
from django.db.models import F
from django.utils import timezone

from apps.tenant_apps.loans.domain import LoanDocumentKind
from apps.tenant_apps.loans.models import LoanSeries


def running_series(workspace, *, as_of_date=None):
    day = as_of_date or timezone.localdate()
    return LoanSeries.objects.filter(
        workspace=workspace, is_active=True, license__is_active=True,
        license__is_legacy_reference=False,
        license__issued_on__lte=day, license__expires_on__gte=day,
        number_sequences__document_kind=LoanDocumentKind.PAWN_LOAN.value,
        number_sequences__is_active=True,
        number_sequences__next_number__lte=F("number_sequences__maximum_number"),
    ).select_related("license").prefetch_related("number_sequences").order_by("license__license_number", "code")


def series_new_loan_status(series, *, as_of_date=None):
    day = as_of_date or timezone.localdate()
    if not series.is_active:
        return {"label": "Stopped for new loans", "reason": "The owner has closed this series to new lending.", "running": False}
    license = series.license
    if (not license.is_active or license.is_legacy_reference or not license.issued_on
            or not license.expires_on or not license.issued_on <= day <= license.expires_on):
        return {"label": "Licence unavailable", "reason": "The licence is not available for current lending.", "running": False}
    sequence = next((row for row in series.number_sequences.all()
                     if row.document_kind == LoanDocumentKind.PAWN_LOAN.value), None)
    if sequence is None or not sequence.is_active:
        return {"label": "Numbering unavailable", "reason": "An active loan-number sequence is required.", "running": False}
    if sequence.next_number > sequence.maximum_number:
        return {"label": "Numbers exhausted", "reason": "All configured loan numbers have been issued or reserved.", "running": False}
    return {"label": "Running", "reason": "Open for new loans with available numbering and a current licence.", "running": True}
