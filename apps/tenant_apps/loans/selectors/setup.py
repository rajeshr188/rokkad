"""Read-only first-loan setup guidance; loan commands retain final validation."""

from django.urls import reverse
from django.db.models import Q
from django.utils import timezone

from apps.tenant_apps.loans.domain import LoanDocumentKind
from apps.tenant_apps.loans.models import LoanLicense, LoanProductVersion, LoanSeries, current_tenant_workspace_id
from apps.tenant_apps.loans.services import (
    NumberAllocationError, preview_number, resolve_pawn_loan_economic_policy,
    resolve_pawn_metal_interest_rate_policy,
)


def get_pawn_setup_checklist(workspace):
    if current_tenant_workspace_id() != workspace.pk:
        raise ValueError("Loan setup must belong to the active Workspace.")
    today = timezone.localdate()
    licenses = LoanLicense.objects.filter(workspace=workspace, is_active=True, issued_on__lte=today, expires_on__gte=today)
    series_ready = False
    economics_ready = False
    for series in LoanSeries.objects.filter(license__in=licenses, is_active=True).select_related("license"):
        try:
            preview_number(series=series, document_kind=LoanDocumentKind.PAWN_LOAN)
        except (NumberAllocationError, ValueError):
            continue
        series_ready = True
        try:
            resolve_pawn_loan_economic_policy(workspace_id=workspace.pk, license_id=series.license_id, as_of_date=today)
            for metal in ("GOLD", "SILVER"):
                resolve_pawn_metal_interest_rate_policy(workspace_id=workspace.pk, license_id=series.license_id, metal=metal, as_of_date=today)
        except ValueError:
            continue
        economics_ready = True
        break

    def url(name, **kwargs):
        return reverse("workspace_loans:" + name, kwargs={"workspace_slug": workspace.slug, **kwargs})

    license_choices = list(licenses[:2])
    series_url = url("license_detail", pk=license_choices[0].pk) if len(license_choices) == 1 else url("license_list") + "#license-register"
    steps = [
        {"key": "license", "title": "License", "complete": licenses.exists(),
         "description": "Add an active, unexpired license and its supporting evidence. Review evidence warnings in the license register.",
         "action_label": "Review licenses" if license_choices else "Add license", "action_url": url("license_list") + "#license-register" if license_choices else url("license_create")},
        {"key": "series", "title": "Numbering series", "complete": series_ready,
         "description": "Open a license and add an active series with an available PawnLoan number. Configure release numbering there too.",
         "action_label": "Set up a series", "action_url": series_url},
        {"key": "economics", "title": "Calculation and interest policies", "complete": economics_ready,
         "description": "Set policies effective today, including gold and silver interest, for at least one usable series. Review fees if your business charges them.",
         "action_label": "Open Economic Setup", "action_url": url("pawn_economics_setup")},
        {"key": "product", "title": "Loan product", "complete": LoanProductVersion.objects.filter(
            workspace=workspace, product__workspace=workspace, product__is_active=True, status="ACTIVE",
         ).filter(Q(available_from__isnull=True) | Q(available_from__lte=today)).filter(
             Q(available_until__isnull=True) | Q(available_until__gte=today),
         ).exists(),
         "description": "Review product terms, activate a version, and check its availability dates. A new loan needs a product available for its loan date.",
         "action_label": "Review loan products", "action_url": url("loan_product_list")},
    ]
    return {"steps": steps, "ready": all(step["complete"] for step in steps), "as_of_date": today}
