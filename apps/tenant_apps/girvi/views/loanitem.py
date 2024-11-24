# views.py
from django.shortcuts import render
from django_tables2 import RequestConfig
from ..models import LoanItem
from ..tables import LoanItemTable


from ..filters import LoanItemFilter

def loanitem_list(request):
    filter = LoanItemFilter(request.GET, queryset=LoanItem.objects.all())
    table = LoanItemTable(filter.qs)
    RequestConfig(request, paginate={"per_page": 10}).configure(table)
    return render(request, "girvi/loan/loanitem_list.html", {"table": table, "filter": filter})