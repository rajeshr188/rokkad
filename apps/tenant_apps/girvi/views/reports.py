from django.utils.translation import gettext as _
from slick_reporting.fields import ComputationField
from slick_reporting.views import Chart, ListReportView, ReportView
from ..models import Loan, LoanPayment, Statement,Release
from ..forms import LoanReportForm
from django.db.models import (Count, F, Q,Sum)

class LoanByCustomerReport(ReportView):
    queryset = Loan.objects.unreleased()
    form_class = LoanReportForm
    group_by = "customer__name"
    columns = [
        "customer__name",
        ComputationField.create(Sum, "loan_amount", verbose_name="total_loan_amount"),
    ]
    chart_settings = [
        Chart(
            "Customer Loan Report",
            Chart.PIE,
            data_source=["sum__loan_amount"],
            title_source=["customer__name"],
        ),
    ]


class LoanTimeSeriesReport(ReportView):
    queryset = Loan.unreleased.all()
    form_class = LoanReportForm
    group_by = "customer__name"
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
        ComputationField.create(Sum, "loan_amount", verbose_name="Total Loan Amount"),
    ]
    columns = [
        "customer__name",
        "__time_series__",
        ComputationField.create(Sum, "loan_amount", verbose_name="Total Loan Amount"),
    ]
    chart_settings = [
        Chart(
            "Customer Loan Time Series",
            Chart.BAR,
            data_source=["sum__loan_amount"],
            title_source=["__time_series__"],
        ),
        Chart(
            "Total Loan Amount Monthly",
            Chart.PIE,
            data_source=["sum__loan_amount"],
            title_source=["customer__name"],
            plot_total=True,
        ),
        Chart(
            "Total Loan Amount [Area Chart]",
            Chart.AREA,
            data_source=["sum__loan_amount"],
            title_source="customer",
        ),
    ]


class SeriesReport(ReportView):
    queryset = Loan.objects.unreleased()
    form_class = LoanReportForm
    group_by = "series__name"
    columns = [
        "series__name",
        ComputationField.create(Sum, "loan_amount", verbose_name="total_loan_amount"),
    ]
    chart_settings = [
        Chart(
            "Series report",
            Chart.PIE,
            data_source=["sum__loan_amount"],
            title_source=["series__name"],
        ),
    ]


class LicenseReport(ReportView):
    queryset = Loan.objects.unreleased()
    form_class = LoanReportForm
    group_by = "series__license__name"
    columns = [
        "series__license__name",
        ComputationField.create(Sum, "loan_amount", verbose_name="total_loan_amount"),
    ]
    chart_settings = [
        Chart(
            "License report",
            Chart.PIE,
            data_source=["sum__loan_amount"],
            title_source=["series__license__name"],
        ),
    ]


class LoanCrosstabReport(ReportView):
    report_title = "Cross tab Report"
    queryset = Loan.unreleased.all()
    group_by = "series__name"
    date_field = "loan_date"
    form_class = LoanReportForm
    time_series_pattern = "annually"
    time_series_columns = [
        ComputationField.create(Sum, "loan_amount", verbose_name="Loan Sum")
    ]

    columns = [
        "series__name",
        "__time_series__",
        ComputationField.create(Sum, "loan_amount", verbose_name="Loan Sum"),
    ]

    chart_settings = [
        Chart(
            "Loan Crosstab Report",
            Chart.COLUMN,
            data_source=["sum__loan_amount"],
            title_source=["series__name"],
        ),
    ]


class LoanListReport(ListReportView):
    queryset = Loan.unreleased.all()
    columns = ["id", "loan_date", "customer__name", "loan_amount"]
