from django.db.models import Sum, Value, F
from django.db.models.functions import Concat
from django.utils.translation import gettext as _
from slick_reporting.fields import ComputationField
from slick_reporting.views import Chart, ListReportView, ReportView

from ..forms import LoanReportForm
from ..models import GivenLoan


class LoanByCustomerReport(ReportView):
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


class LoanTimeSeriesReport(ReportView):
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


class SeriesReport(ReportView):
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


class LicenseReport(ReportView):
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


class LoanCrosstabReport(ReportView):
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


class LoanListReport(ListReportView):
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
