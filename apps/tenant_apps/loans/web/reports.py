"""Read-only PawnLoan reporting and export HTTP endpoints."""

from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.http import content_disposition_header

from apps.tenant_apps.loans.access import LOANS_ADMIN_ACTION, loans_workspace_required, loans_action_required
from apps.tenant_apps.loans.services import (
    PawnLoanReportExportError,
    build_party_statement_dataset,
    build_pawn_loan_report_dataset,
    render_report_dataset,
)
from apps.tenant_apps.loans.selectors import (
    get_pawn_loan_reports,
    get_pawn_party_statement,
)
from apps.tenant_apps.party.models import Party


REPORT_EXPORT_SECTIONS = (
    ("active", "Active loans"),
    ("daily", "Daily disbursals / repayments"),
    ("interest_due", "Interest due"),
    ("overdue", "Overdue loans"),
    ("releases_renewals", "Releases / renewals"),
    ("storage", "Storage inventory"),
    ("license_expiry", "License expiry"),
)
REPORT_EXPORT_FORMATS = (("csv", "CSV"), ("xlsx", "XLSX"), ("pdf", "PDF"))


@loans_workspace_required
def pawn_loan_reports(request):
    as_of_date = _report_as_of_date(request)
    report = get_pawn_loan_reports(as_of_date=as_of_date)
    parties = (
        Party.objects.filter(pawn_loans__workspace=request.loans_workspace)
        .distinct()
        .order_by("display_name")
    )
    return render(request, "loans/pawn/reports.html", {
        "report": report,
        "parties": parties,
        "can_administer": _can_administer(request),
        "can_export": request.loans_workspace_access.can("report.export"),
        "can_send_notice": request.loans_workspace_access.can("data.edit"),
        "report_is_current": as_of_date == timezone.localdate(),
        "report_export_sections": REPORT_EXPORT_SECTIONS,
        "report_export_formats": REPORT_EXPORT_FORMATS,
    })


@loans_action_required("report.export")
def pawn_loan_report_export(request, section, export_format):
    as_of_date = _report_as_of_date(request)
    try:
        dataset = build_pawn_loan_report_dataset(
            get_pawn_loan_reports(as_of_date=as_of_date), section
        )
        content, content_type = render_report_dataset(dataset, export_format)
    except PawnLoanReportExportError as exc:
        return HttpResponse(str(exc), status=400)
    response = HttpResponse(content, content_type=content_type)
    response["Content-Disposition"] = content_disposition_header(
        True, f"pawn-loans-{section}-{as_of_date}.{export_format}"
    )
    return response


@loans_workspace_required
def pawn_party_statement(request, party_pk, export_format=None):
    if export_format:
        request.loans_workspace_access.require("report.export")
    party = get_object_or_404(
        Party.objects.filter(
            pawn_loans__workspace=request.loans_workspace
        ).distinct(),
        pk=party_pk,
    )
    statement = get_pawn_party_statement(
        party_id=party.pk, as_of_date=_report_as_of_date(request)
    )
    if export_format:
        try:
            content, content_type = render_report_dataset(
                build_party_statement_dataset(statement), export_format
            )
        except PawnLoanReportExportError as exc:
            return HttpResponse(str(exc), status=400)
        response = HttpResponse(content, content_type=content_type)
        response["Content-Disposition"] = content_disposition_header(
            True,
            f"party-statement-{party.pk}-{statement.as_of_date}.{export_format}",
        )
        return response
    return render(
        request, "loans/pawn/party_statement.html", {"statement": statement, "can_export": request.loans_workspace_access.can("report.export")}
    )


def _report_as_of_date(request):
    raw = (request.GET.get("as_of") or "").strip()
    if not raw:
        return timezone.localdate()
    value = parse_date(raw)
    if value is None:
        raise Http404("Report date must use YYYY-MM-DD.")
    return value


def _can_administer(request):
    return request.loans_workspace_access.can(LOANS_ADMIN_ACTION)


__all__ = ["pawn_loan_report_export", "pawn_loan_reports", "pawn_party_statement"]
