from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from ..models import Customer


CUSTOMER_DETAIL_TEMPLATE = "contact/customer_detail_improved.html"


def get_customer_for_detail(pk):
    return get_object_or_404(
        Customer.objects.prefetch_related(
            "address",
            "contactno",
            "proofs",
            "pics",
            "relationships_created__related_customer",
        ),
        pk=pk,
    )


def render_customer_detail_fragment(
    request, customer, fragment_name, context=None, status=200, headers=None
):
    response = render(
        request,
        f"{CUSTOMER_DETAIL_TEMPLATE}#{fragment_name}",
        {"customer": customer, **(context or {})},
        status=status,
    )
    for key, value in (headers or {}).items():
        response[key] = value
    return response


def get_customer_detail_context(customer):
    loans = customer.loans_received.unreleased().for_table_display()
    return {
        "object": customer,
        "customer": customer,
        "loans": loans,
        "total_loans": loans.count(),
        "total_amount": loans.total_loan_amount(),
        "worth": loans.total_current_value() or 0,
    }


def render_customer_detail_page(request, customer, status=200, headers=None):
    response = render(
        request,
        f"{CUSTOMER_DETAIL_TEMPLATE}#customer-detail",
        get_customer_detail_context(customer),
        status=status,
    )
    for key, value in (headers or {}).items():
        response[key] = value
    return response


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
