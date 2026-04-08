from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.dates import (
    DayArchiveView,
    MonthArchiveView,
    TodayArchiveView,
    WeekArchiveView,
    YearArchiveView,
)

from ..models import GivenLoan


class LoanYearArchiveView(LoginRequiredMixin, YearArchiveView):
    queryset = GivenLoan.objects.all()
    date_field = "loan_date"
    make_object_list = True
    template_name = "girvi/loan_archive_year.html"


class LoanMonthArchiveView(LoginRequiredMixin, MonthArchiveView):
    queryset = GivenLoan.objects.filter(release__isnull=True)
    date_field = "loan_date"
    make_object_list = True
    template_name = "girvi/loan_archive_month.html"

    def get_context_data(self, *args, **kwargs):
        data = super().get_context_data(**kwargs)
        data["count"] = len(data)
        return data


class LoanWeekArchiveView(LoginRequiredMixin, WeekArchiveView):
    queryset = GivenLoan.objects.filter(release__isnull=True)
    date_field = "loan_date"
    week_format = "%W"
    template_name = "girvi/loan_archive_week.html"


class LoanDayArchiveView(LoginRequiredMixin, DayArchiveView):
    queryset = GivenLoan.objects.filter(release__isnull=True)
    date_field = "loan_date"
    allow_empty = True
    template_name = "girvi/loan_archive_day.html"


class LoanTodayArchiveView(TodayArchiveView):
    queryset = GivenLoan.objects.filter(release__isnull=True)
    date_field = "loan_date"
    allow_empty = True
    template_name = "girvi/loan_archive_day.html"
