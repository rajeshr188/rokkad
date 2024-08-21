from django.views.generic.dates import (DayArchiveView, MonthArchiveView,
                                        TodayArchiveView, WeekArchiveView,
                                        YearArchiveView)
from django.contrib.auth.mixins import LoginRequiredMixin
from ..models import Loan

class LoanYearArchiveView(LoginRequiredMixin, YearArchiveView):
    queryset = Loan.objects.all()
    date_field = "loan_date"
    make_object_list = True


class LoanMonthArchiveView(LoginRequiredMixin, MonthArchiveView):
    queryset = Loan.objects.unreleased()
    date_field = "loan_date"
    make_object_list = True

    def get_context_data(self, *args, **kwargs):
        data = super().get_context_data(**kwargs)
        data["count"] = len(data)
        return data


class LoanWeekArchiveView(LoginRequiredMixin, WeekArchiveView):
    queryset = Loan.objects.unreleased()
    date_field = "loan_date"
    week_format = "%W"


class LoanDayArchiveView(LoginRequiredMixin, DayArchiveView):
    queryset = Loan.objects.unreleased()
    date_field = "loan_date"
    allow_empty = True


class LoanTodayArchiveView(TodayArchiveView):
    queryset = Loan.objects.unreleased()
    date_field = "loan_date"
    allow_empty = True
    # template_name = "girvi/loan/loan_archive_day.html"
