from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from ..models import Customer


@login_required
def reallot_receipts(request, pk):
    customer = Customer.objects.get(pk=pk)
    customer.reallot_receipts()
    return redirect(customer.get_absolute_url())


@login_required
def reallot_payments(request, pk):
    customer = Customer.objects.get(pk=pk)
    customer.reallot_payments()
    return redirect(customer.get_absolute_url())


from slick_reporting.views import ListReportView


class CustomerReport(ListReportView):
    report_model = Customer
    report_title = "Newly created Customers Report"
    date_field = "created"
    filters = ["relatedas", "relatedto", "name"]
    columns = [
        "name",
        "relatedas",
        "relatedto",
        "created",
    ]
    limit_records = 10
    default_order_by = "-created"
