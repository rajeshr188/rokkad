from django.contrib import messages
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from slick_reporting.fields import ComputationField
from slick_reporting.views import Chart, ListReportView, ReportView

from ..forms import LoanReportForm
from ..models import (
    GirviPostingOutboxEvent,
    GirviPostingOutboxStatus,
    GivenLoan,
    LoanChangeLog,
    Series,
)
from ..selectors import (
    build_operations_console_read_model,
    build_loan_accounting_reconciliation_report_context,
    build_operational_controls_report_context,
)
from .access import GirviPermissionRequiredMixin, girvi_permission_required


class LoanByCustomerReport(GirviPermissionRequiredMixin, ReportView):
    required_permissions = ("girvi_report_view",)
    queryset = GivenLoan.objects.filter(release__isnull=True)
    form_class = LoanReportForm
    group_by = "borrower__firstname"
    columns = [
        "borrower__firstname",
        "borrower__lastname",
        ComputationField.create(
            Sum, "loanitems__loanamount", verbose_name="total_loan_amount"
        ),
    ]
    chart_settings = [
        Chart(
            "Customer Loan Report",
            Chart.PIE,
            data_source=["sum__loanitems__loanamount"],
            title_source=["borrower__firstname"],
        ),
    ]


class LoanTimeSeriesReport(GirviPermissionRequiredMixin, ReportView):
    required_permissions = ("girvi_report_view",)
    queryset = GivenLoan.objects.filter(release__isnull=True)
    form_class = LoanReportForm
    group_by = "borrower__firstname"
    time_series_pattern = "annually"
    # options are: "daily", "weekly", "bi-weekly", "monthly", "quarterly", "semiannually", "annually" and "custom"

    time_series_selector = True
    time_series_selector_choices = (
        ("daily", _("Daily")),
        ("weekly", _("Weekly")),
        ("bi-weekly", _("Bi-Weekly")),
        ("monthly", _("Monthly")),
    )
    time_series_selector_default = "bi-weekly"

    time_series_selector_label = _("Period Pattern")
    # The label for the time series selector

    time_series_selector_allow_empty = True

    date_field = "loan_date"
    title = _("Loan Time Series Report")
    time_series_columns = [
        ComputationField.create(
            Sum, "loanitems__loanamount", verbose_name="Total Loan Amount"
        ),
    ]
    columns = [
        "borrower__firstname",
        "borrower__lastname",
        "__time_series__",
        ComputationField.create(
            Sum, "loanitems__loanamount", verbose_name="Total Loan Amount"
        ),
    ]
    chart_settings = [
        Chart(
            "Customer Loan Time Series",
            Chart.BAR,
            data_source=["sum__loanitems__loanamount"],
            title_source=["__time_series__"],
        ),
        Chart(
            "Total Loan Amount Monthly",
            Chart.PIE,
            data_source=["sum__loanitems__loanamount"],
            title_source=["borrower__firstname"],
            plot_total=True,
        ),
        Chart(
            "Total Loan Amount [Area Chart]",
            Chart.AREA,
            data_source=["sum__loanitems__loanamount"],
            title_source="borrower",
        ),
    ]


class SeriesReport(GirviPermissionRequiredMixin, ReportView):
    required_permissions = ("girvi_report_view",)
    queryset = GivenLoan.objects.filter(release__isnull=True)
    form_class = LoanReportForm
    group_by = "series__name"
    columns = [
        "series__name",
        ComputationField.create(
            Sum, "loanitems__loanamount", verbose_name="total_loan_amount"
        ),
    ]
    chart_settings = [
        Chart(
            "Series report",
            Chart.PIE,
            data_source=["sum__loanitems__loanamount"],
            title_source=["series__name"],
        ),
    ]


class LicenseReport(GirviPermissionRequiredMixin, ReportView):
    required_permissions = ("girvi_report_view",)
    queryset = GivenLoan.objects.filter(release__isnull=True)
    form_class = LoanReportForm
    group_by = "series__license__name"
    columns = [
        "series__license__name",
        ComputationField.create(
            Sum, "loanitems__loanamount", verbose_name="total_loan_amount"
        ),
    ]
    chart_settings = [
        Chart(
            "License report",
            Chart.PIE,
            data_source=["sum__loanitems__loanamount"],
            title_source=["series__license__name"],
        ),
    ]


class LoanCrosstabReport(GirviPermissionRequiredMixin, ReportView):
    required_permissions = ("girvi_report_view",)
    report_title = "Cross tab Report"
    queryset = GivenLoan.objects.filter(release__isnull=True)
    group_by = "series__name"
    date_field = "loan_date"
    form_class = LoanReportForm
    time_series_pattern = "annually"
    time_series_columns = [
        ComputationField.create(Sum, "loanitems__loanamount", verbose_name="Loan Sum")
    ]

    columns = [
        "series__name",
        "__time_series__",
        ComputationField.create(Sum, "loanitems__loanamount", verbose_name="Loan Sum"),
    ]

    chart_settings = [
        Chart(
            "Loan Crosstab Report",
            Chart.COLUMN,
            data_source=["sum__loanitems__loanamount"],
            title_source=["series__name"],
        ),
    ]


class LoanListReport(GirviPermissionRequiredMixin, ListReportView):
    required_permissions = ("girvi_report_view",)
    queryset = GivenLoan.objects.filter(release__isnull=True)
    columns = [
        "id",
        "loan_date",
        "borrower__firstname",
        "borrower__lastname",
        ComputationField.create(
            Sum, "loanitems__loanamount", verbose_name="loan_amount"
        ),
    ]


@girvi_permission_required("girvi_report_view")
def loan_accounting_reconciliation_report(request):
    context = build_loan_accounting_reconciliation_report_context()
    return render(
        request,
        "girvi/reports/loan_accounting_reconciliation_report.html",
        context,
    )


@girvi_permission_required("girvi_report_view")
def girvi_operations_console(request):
    if request.method == "POST":
        event = get_object_or_404(
            GirviPostingOutboxEvent,
            pk=request.POST.get("retry_event_id"),
        )
        if event.status not in {
            GirviPostingOutboxStatus.FAILED,
            GirviPostingOutboxStatus.DEAD_LETTER,
        }:
            messages.warning(
                request,
                "Only failed or dead-letter outbox events can be retried.",
            )
            return redirect("girvi:girvi_operations_console")

        event.status = GirviPostingOutboxStatus.PENDING
        event.available_at = timezone.now()
        event.claimed_at = None
        event.last_error = ""
        event.save(
            update_fields=[
                "status",
                "available_at",
                "claimed_at",
                "last_error",
                "updated_at",
            ]
        )
        messages.success(request, f"Queued outbox event #{event.pk} for retry.")
        return redirect("girvi:girvi_operations_console")

    read_model = build_operations_console_read_model()

    return render(
        request,
        "girvi/reports/operations_console.html",
        read_model,
    )


@girvi_permission_required("girvi_report_view")
def loan_operational_controls_report(request):
    context = build_operational_controls_report_context()
    return render(
        request,
        "girvi/reports/loan_operational_controls_report.html",
        context,
    )
