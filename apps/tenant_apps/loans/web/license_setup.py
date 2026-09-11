"""License evidence and series setup views; lifecycle rules remain in services."""

import uuid

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.utils import timezone
from django.utils.http import content_disposition_header
from django.views.decorators.http import require_POST

from apps.tenant_apps.loans.access import loans_setup_required
from apps.tenant_apps.loans.domain import LoanDocumentKind
from apps.tenant_apps.loans.forms import (
    LoanLicenseForm,
    LoanLicenseRenewalForm,
    LoanSeriesSetupForm,
)
from apps.tenant_apps.loans.models import (
    LoanLicense,
    LoanLicenseRevision,
    LoanSeries,
)
from apps.tenant_apps.loans.selectors import get_loan_license_register
from apps.tenant_apps.loans.services import (
    LicenseSeriesError,
    LoanOperationalNoticeError,
    NumberAllocationError,
    activate_license,
    create_configured_series,
    create_license,
    create_license_expiry_notice,
    expire_license,
    preview_number,
    render_loan_license_register_pdf,
    renew_license,
    update_configured_series,
    update_license,
)


@loans_setup_required
def license_list(request):
    from apps.tenant_apps.loans.selectors.setup import get_pawn_setup_checklist

    register_rows = get_loan_license_register(request.loans_workspace.pk)
    return render(
        request,
        "loans/setup/license_list.html",
        {
            "register_rows": register_rows,
            "loan_setup": get_pawn_setup_checklist(request.loans_workspace),
            "as_of_date": timezone.localdate(),
        },
    )


@loans_setup_required
def license_register_pdf(request):
    as_of_date = timezone.localdate()
    rows = get_loan_license_register(
        request.loans_workspace.pk,
        as_of_date=as_of_date,
    )
    content = render_loan_license_register_pdf(
        workspace=request.loans_workspace,
        rows=rows,
        as_of_date=as_of_date,
    )
    response = HttpResponse(content, content_type="application/pdf")
    response["Content-Disposition"] = content_disposition_header(
        True,
        f"loan-license-register-{as_of_date.isoformat()}.pdf",
    )
    return response


@loans_setup_required
def license_detail(request, pk):
    license = _license_for_workspace(request, pk)
    revisions = license.revisions.select_related("created_by").order_by(
        "-revision_number"
    )
    series_rows = []
    for series in license.series.prefetch_related("number_sequences").all():
        series_rows.append(
            {
                "series": series,
                "loan_preview": _safe_preview(series, LoanDocumentKind.PAWN_LOAN),
                "release_preview": _safe_preview(
                    series, LoanDocumentKind.PAWN_LOAN_RELEASE
                ),
            }
        )
    return render(
        request,
        "loans/setup/license_detail.html",
        {
            "license": license,
            "series_rows": series_rows,
            "revisions": revisions,
            "expiry_notices": license.operational_notices.order_by("-created_at"),
        },
    )


@loans_setup_required
@require_POST
def license_expiry_notice_create(request, pk):
    license = _license_for_workspace(request, pk)
    try:
        create_license_expiry_notice(
            license.pk, request_key=uuid.uuid4().hex, actor=request.user
        )
    except (LoanOperationalNoticeError, ValidationError, ValueError) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "License expiry alert queued for the workspace Owner.")
    return redirect("workspace_loans:license_detail", workspace_slug=request.loans_workspace.slug, pk=license.pk)


@loans_setup_required
def license_create(request):
    form = LoanLicenseForm(request.POST or None, request.FILES or None)
    form.instance.workspace = request.loans_workspace
    if request.method == "POST" and form.is_valid():
        try:
            license = create_license(
                workspace=request.loans_workspace,
                actor=request.user,
                request=request,
                **form.cleaned_data,
            )
        except LicenseSeriesError as exc:
            form.add_error("supporting_document", str(exc))
        else:
            messages.success(request, "Loan license and initial evidence created.")
            return redirect("workspace_loans:license_detail", workspace_slug=request.loans_workspace.slug, pk=license.pk)
    return render(request, "loans/setup/license_form.html", {"form": form})


@loans_setup_required
def license_update(request, pk):
    license = _license_for_workspace(request, pk)
    form = LoanLicenseForm(
        request.POST or None,
        request.FILES or None,
        instance=license,
    )
    if request.method == "POST" and form.is_valid():
        try:
            update_license(
                license,
                actor=request.user,
                request=request,
                **form.cleaned_data,
            )
        except LicenseSeriesError as exc:
            form.add_error("supporting_document", str(exc))
        else:
            messages.success(request, "License amendment evidence recorded.")
            return redirect("workspace_loans:license_detail", workspace_slug=request.loans_workspace.slug, pk=license.pk)
    return render(
        request,
        "loans/setup/license_form.html",
        {"form": form, "license": license},
    )


@loans_setup_required
def license_renew(request, pk):
    license = _license_for_workspace(request, pk)
    form = LoanLicenseRenewalForm(
        request.POST or None,
        request.FILES or None,
        license=license,
    )
    if request.method == "POST" and form.is_valid():
        try:
            renew_license(
                license,
                actor=request.user,
                request=request,
                **form.cleaned_data,
            )
        except LicenseSeriesError as exc:
            form.add_error("supporting_document", str(exc))
        else:
            messages.success(request, "License renewal evidence recorded and activated.")
            return redirect("workspace_loans:license_detail", workspace_slug=request.loans_workspace.slug, pk=license.pk)
    return render(
        request,
        "loans/setup/license_renewal_form.html",
        {"form": form, "license": license},
    )


@loans_setup_required
@never_cache
def license_revision_document(request, pk, revision_pk):
    license = _license_for_workspace(request, pk)
    revision = get_object_or_404(
        LoanLicenseRevision,
        pk=revision_pk,
        license=license,
    )
    if not revision.has_document:
        raise Http404("This license revision has no supporting document.")
    revision.supporting_document.open("rb")
    content = revision.supporting_document.read()
    revision.supporting_document.close()
    response = HttpResponse(content, content_type=revision.mime_type)
    response["Content-Disposition"] = content_disposition_header(
        True,
        revision.original_filename,
    )
    response["X-Content-Type-Options"] = "nosniff"
    return response


@loans_setup_required
@require_POST
def license_expire(request, pk):
    license = _license_for_workspace(request, pk)
    expire_license(license, actor=request.user)
    messages.success(request, "Loan license deactivated; existing loans remain linked.")
    return redirect("workspace_loans:license_detail", workspace_slug=request.loans_workspace.slug, pk=license.pk)


@loans_setup_required
@require_POST
def license_activate(request, pk):
    license = _license_for_workspace(request, pk)
    try:
        activate_license(license, actor=request.user)
        messages.success(request, "Loan license activated.")
    except LicenseSeriesError as exc:
        messages.error(request, str(exc))
    return redirect("workspace_loans:license_detail", workspace_slug=request.loans_workspace.slug, pk=license.pk)


@loans_setup_required
def series_create(request, license_pk):
    license = _license_for_workspace(request, license_pk)
    form = LoanSeriesSetupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        series = create_configured_series(
            license=license,
            actor=request.user,
            request=request,
            **form.cleaned_data,
        )
        messages.success(request, "Loan series and numbering sequences created.")
        return redirect("workspace_loans:license_detail", workspace_slug=request.loans_workspace.slug, pk=license.pk)
    return render(
        request,
        "loans/setup/series_form.html",
        {"form": form, "license": license},
    )


@loans_setup_required
def series_update(request, pk):
    series = _series_for_workspace(request, pk)
    initial = _series_initial(series)
    form = LoanSeriesSetupForm(request.POST or None, instance=series, initial=initial)
    if request.method == "POST" and form.is_valid():
        update_configured_series(
            series,
            actor=request.user,
            request=request,
            **form.cleaned_data,
        )
        messages.success(request, "Loan series setup updated.")
        return redirect("workspace_loans:license_detail", workspace_slug=request.loans_workspace.slug, pk=series.license_id)
    return render(
        request,
        "loans/setup/series_form.html",
        {"form": form, "license": series.license, "series": series},
    )


def _license_for_workspace(request, pk):
    return get_object_or_404(
        LoanLicense, pk=pk, workspace=request.loans_workspace
    )


def _series_for_workspace(request, pk):
    return get_object_or_404(
        LoanSeries.objects.select_related("license"),
        pk=pk,
        license__workspace=request.loans_workspace,
    )


def _safe_preview(series, kind):
    try:
        return {"value": preview_number(series=series, document_kind=kind).value}
    except NumberAllocationError as exc:
        return {"error": str(exc)}
    except ValueError as exc:
        return {"error": str(exc)}


def _series_initial(series):
    sequences = {item.document_kind: item for item in series.number_sequences.all()}
    loan = sequences.get(LoanDocumentKind.PAWN_LOAN.value)
    release = sequences.get(LoanDocumentKind.PAWN_LOAN_RELEASE.value)
    baseline = loan or release
    return {
        "pawn_loan_prefix": loan.prefix if loan else "PL-",
        "release_prefix": release.prefix if release else "RL-",
        "number_width": baseline.width if baseline else 5,
        "maximum_number": baseline.maximum_number if baseline else 10000,
    }
