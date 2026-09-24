"""Read-only PawnLoan reporting and export HTTP endpoints."""

from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.http import content_disposition_header, urlencode
from django.urls import reverse
from apps.tenant_apps.loans.selectors.reports import get_pawn_report_page
from apps.tenant_apps.loans.selectors.portfolio_analysis import ANALYSIS_SECTIONS, get_portfolio_analysis
from apps.tenant_apps.loans.services.report_exports import PawnLoanReportDataset

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
    *ANALYSIS_SECTIONS,
)
REPORT_EXPORT_FORMATS = (("csv", "CSV"), ("xlsx", "XLSX"), ("pdf", "PDF"))


REPORT_SECTIONS = (
    ("portfolio", "Loan balances"), ("summary", "Portfolio summary"), ("daily", "Daily activity"),
    ("issues", "Integrity findings"), ("license_expiry", "License expiry"),
    ("accruals", "Finalized accruals"), ("repayments", "Repayments"),
    ("releases", "Releases"), ("renewals", "Release and renew"),
    ("custody", "Collateral custody"), ("statements", "Borrower statements"),
    *ANALYSIS_SECTIONS,
)


@loans_workspace_required
def pawn_loan_reports(request):
    as_of_date = _report_as_of_date(request)
    section = request.GET.get("section", "portfolio")
    if section not in dict(REPORT_SECTIONS):
        raise Http404("Unknown report section.")
    query = (request.GET.get("q") or "").strip()[:200] if section == "statements" else ""
    if section in dict(ANALYSIS_SECTIONS):
        analysis = get_portfolio_analysis(section=section, as_of_date=as_of_date)
        for row in analysis["rows"]:
            if row["filters"]:
                row["url"] = reverse("workspace_loans:pawn_loan_list", args=[request.loans_workspace.slug]) + "?" + urlencode(row["filters"])
        analysis["columns"] = tuple(column.replace("INR", "\u20b9") for column in analysis["columns"])
        context = {"analysis": analysis, "as_of_date": as_of_date}
    else:
        context = get_pawn_report_page(section=section, as_of_date=as_of_date, page=request.GET.get("page"), query=query)
    context.update({
        "section": section, "section_title": dict(REPORT_SECTIONS)[section],
        "report_sections": REPORT_SECTIONS, "query": query,
        "pagination_query": urlencode({"section": section, "as_of": as_of_date.isoformat(), "q": query}),
        "can_export": request.loans_workspace_access.can("report.export"),
        "can_send_notice": request.loans_workspace_access.can("data.edit"),
        "report_is_current": as_of_date == timezone.localdate(),
        "report_export_sections": REPORT_EXPORT_SECTIONS,
        "report_export_formats": REPORT_EXPORT_FORMATS,
    })
    return render(request, "loans/pawn/reports.html", context)


@loans_action_required("report.export")
def pawn_loan_report_export(request, section, export_format):
    as_of_date = _report_as_of_date(request)
    try:
        if section in dict(ANALYSIS_SECTIONS):
            analysis = get_portfolio_analysis(section=section, as_of_date=as_of_date)
            dataset = PawnLoanReportDataset(section, f"{analysis['title']} - {as_of_date}",
                analysis["columns"], tuple(tuple(row["cells"]) for row in analysis["rows"]) + (tuple(analysis["totals"]),), notes=analysis["scope"])
        else:
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
    try:
        value = parse_date(raw)
    except ValueError:
        value = None
    if value is None:
        raise Http404("Report date must use YYYY-MM-DD.")
    return value


def _can_administer(request):
    return request.loans_workspace_access.can(LOANS_ADMIN_ACTION)


__all__ = ["pawn_loan_report_export", "pawn_loan_reports", "pawn_party_statement"]
