"""Read-only first-loan setup guidance; loan commands retain final validation."""

from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.db.models import Q
from django.utils import timezone

from apps.tenant_apps.loans.domain import LoanDocumentKind, ValuationMethod
from .rate_readiness import get_metal_rate_readiness
from .monitoring_policy import LoanRiskAssessmentError, resolve_monitoring_policy
from apps.tenant_apps.loans.models import LoanLicense, LoanProductVersion, LoanSeries, current_tenant_workspace_id
from apps.tenant_apps.loans.services import (
    NumberAllocationError, preview_number, resolve_pawn_loan_economic_policy,
    resolve_pawn_metal_interest_rate_policy,
)


def get_pawn_setup_checklist(workspace):
    if current_tenant_workspace_id() != workspace.pk:
        raise ValueError("Loan setup must belong to the active Workspace.")
    today = timezone.localdate()
    licenses = LoanLicense.objects.filter(workspace=workspace, is_active=True, issued_on__lte=today, expires_on__gte=today, is_legacy_reference=False)
    series_ready = False
    economics_ready = False
    valuation_ready = False
    series_rows = []
    monitoring_by_license = {}
    quote_rows = get_metal_rate_readiness(workspace=workspace, as_of_date=today, metals=("GOLD", "SILVER", "BRONZE"))
    quotes = {row["metal"]: row for row in quote_rows}
    for series in LoanSeries.objects.filter(license__in=licenses, is_active=True).select_related("license").prefetch_related("number_sequences"):
        try:
            loan_number = preview_number(series=series, document_kind=LoanDocumentKind.PAWN_LOAN).value
        except (NumberAllocationError, ValueError):
            continue
        series_ready = True
        row = {"series": series, "loan_number": loan_number, "policy": None, "metals": [], "ready": False}
        if series.license_id not in monitoring_by_license:
            try:
                monitoring_by_license[series.license_id] = (resolve_monitoring_policy(
                    workspace_id=workspace.pk, license_id=series.license_id, as_of_date=today), "")
            except LoanRiskAssessmentError as exc:
                monitoring_by_license[series.license_id] = (None, str(exc))
        row["monitoring_policy"], row["monitoring_error"] = monitoring_by_license[series.license_id]
        try:
            row["release_number"] = preview_number(series=series, document_kind=LoanDocumentKind.PAWN_LOAN_RELEASE).value
        except (NumberAllocationError, ValueError) as exc:
            row["release_error"] = str(exc)
        try:
            policy = resolve_pawn_loan_economic_policy(workspace_id=workspace.pk, license_id=series.license_id, series_id=series.pk, as_of_date=today)
        except ValueError as exc:
            row["error"] = str(exc)
            series_rows.append(row)
            continue
        row["policy"] = policy
        for metal in ("GOLD", "SILVER", "BRONZE"):
            try:
                rate = resolve_pawn_metal_interest_rate_policy(workspace_id=workspace.pk, license_id=series.license_id, series_id=series.pk, metal=metal, as_of_date=today)
            except ValueError:
                continue
            appraisal_only = policy.valuation_method == ValuationMethod.LATEST_APPRAISAL.value
            usable = appraisal_only or quotes[metal]["fresh"]
            row["metals"].append({"metal": metal, "label": _(metal.title()), "rate": rate, "quote": quotes[metal], "ready": usable, "appraisal_only": appraisal_only})
        economics_ready |= bool(row["metals"])
        row["ready"] = any(metal["ready"] for metal in row["metals"])
        valuation_ready |= row["ready"]
        series_rows.append(row)

    quote_description = "; ".join(
        f"{row['label']}: INR {row['rate'].buying_rate}/g, dated {timezone.localtime(row['rate'].effective_at).date()}"
        if row["usable"] else f"{row['label']}: no usable INR pure-metal buying price"
        for row in quote_rows
    )

    def url(name, **kwargs):
        return reverse("workspace_loans:" + name, kwargs={"workspace_slug": workspace.slug, **kwargs})

    license_choices = list(licenses[:2])
    series_url = url("license_detail", pk=license_choices[0].pk) if len(license_choices) == 1 else url("license_list") + "#license-register"
    steps = [
        {"key": "license", "title": _("License"), "complete": licenses.exists(),
         "description": _("Add an active, unexpired license and its supporting evidence. Review evidence warnings in the license register."),
         "action_label": _("Review licenses") if license_choices else _("Add license"), "action_url": url("license_list") + "#license-register" if license_choices else url("license_create")},
        {"key": "series", "title": _("Numbering series"), "complete": series_ready,
         "description": _("Open a license and add a running series with available loan numbers. Configure release numbering there too."),
         "action_label": _("Set up a series"), "action_url": series_url},
        {"key": "economics", "title": _("Calculation and interest policies"), "complete": economics_ready,
         "description": _("Set policies effective today, including monthly interest, for the metals you lend against in at least one usable series. Review fees if your business charges them."),
         "action_label": _("Open Economic Setup"), "action_url": url("pawn_economics_setup")},
        {"key": "product", "title": _("Loan product"), "complete": LoanProductVersion.objects.filter(
            workspace=workspace, product__workspace=workspace, product__is_active=True, status="ACTIVE",
         ).filter(Q(available_from__isnull=True) | Q(available_from__lte=today)).filter(
             Q(available_until__isnull=True) | Q(available_until__gte=today),
         ).exists(),
         "description": _("Standard product drafts are prepared for you. Review their terms and enable the products you offer. Check availability for the loan date."),
         "action_label": _("Choose lending products"), "action_url": url("loan_product_list")},
    ]
    steps.append({
        "key": "metal_rates", "title": _("Metal valuation prices"), "blocking": False,
        "complete": valuation_ready,
        "description": quote_description + ". Add buying prices per gram at the 100% reference grade for the gold, silver or bronze you lend against. An appraisal-only policy does not require a price. Each loan checks its selected policy, date and metals. New lending checks the configured quote-age limit; active-loan monitoring uses its separate age limits.",
        "action_label": _("Review metal prices"),
        "action_url": reverse("workspace_rates:rate_list", kwargs={"workspace_slug": workspace.slug}),
    })
    monitoring_count = sum(row["monitoring_policy"] is not None for row in series_rows)
    return {"steps": steps, "ready": all(step["complete"] for step in steps), "as_of_date": today,
        "series_rows": series_rows, "quote_rows": quote_rows,
        "monitoring": {"ready": bool(series_rows) and monitoring_count == len(series_rows),
            "available_count": monitoring_count, "total_count": len(series_rows)}}
