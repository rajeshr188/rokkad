from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.template.response import TemplateResponse
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, UpdateView
from django_filters.views import FilterView
from django_tables2.config import RequestConfig
from django_tables2.export.views import ExportMixin
from django_tables2.views import SingleTableMixin
from num2words import num2words

from apps.tenant_apps.utils.htmx_utils import for_htmx

from ..filters import ReceiptFilter
from ..forms import ReceiptForm
from ..models import Receipt, ReceiptAllocation
from ..tables import ReceiptTable

# class ReceiptListView(ExportMixin, SingleTableMixin, FilterView):
#     model = Receipt
#     table_class = ReceiptTable
#     filterset_class = ReceiptFilter
#     template_name = "sales/receipt_list.html"
#     paginate_by = 25


@for_htmx(use_block="content")
@login_required
def receipt_list(request):
    filter = ReceiptFilter(
        request.GET,
        queryset=Receipt.objects.all().select_related("customer", "created_by"),
    )
    table = ReceiptTable(filter.qs, prefix="receipt-")
    RequestConfig(request, paginate={"per_page": 10}).configure(table)
    context = {"filter": filter, "table": table}
    return TemplateResponse(request, "sales/receipt_list.html", context=context)


class ReceiptCreateView(CreateView):
    model = Receipt
    form_class = ReceiptForm
    success_url = reverse_lazy("sales:sales_receipt_list")


class ReceiptUpdateView(UpdateView):
    model = Receipt
    form_class = ReceiptForm
    success_url = reverse_lazy("sales:sales_receipt_list")


class ReceiptDetailView(DetailView):
    model = Receipt


class ReceiptUpdateView(UpdateView):
    model = Receipt
    form_class = ReceiptForm
    success_url = reverse_lazy("sales_receipt_list")


# create a function view on receipt list page  to reallot all receipts
def reallocate_receipts(request):
    receipts = Receipt.objects.all()
    for receipt in receipts:
        receipt.reallocate()
    return redirect("sales_receipt_list")


class ReceiptDeleteView(DeleteView):
    model = Receipt
    success_url = reverse_lazy("sales:sales_receipt_list")


@login_required
def receipt_allocate(request, pk):
    receipt = get_object_or_404(Receipt, id=pk)
    receipt.allot()
    return redirect(receipt)
