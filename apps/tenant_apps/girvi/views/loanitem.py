# views.py
from django.shortcuts import render
from django_tables2 import RequestConfig

from ..filters import LoanItemFilter
from ..models import LoanItem
from ..tables import LoanItemTable


def loanitem_list(request):
    filter = LoanItemFilter(request.GET, queryset=LoanItem.objects.all())
    table = LoanItemTable(filter.qs)
    RequestConfig(request, paginate={"per_page": 10}).configure(table)
    return render(
        request, "girvi/loan/loanitem_list.html", {"table": table, "filter": filter}
    )
