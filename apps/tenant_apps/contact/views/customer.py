import http
import stat
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django_tables2 import RequestConfig
from django_tables2.export.export import TableExport
from django.shortcuts import render
from ...utils.htmx_utils import for_htmx, make_get_request
from ..filters import CustomerFilter
from ..forms import CustomerForm, CustomerMergeForm
from ..models import Customer
from ..tables import CustomerTable


@login_required
def customer_list(request):
    context = {}
    f = CustomerFilter(
        request.GET,
        queryset=Customer.objects.all().prefetch_related("contactno", "address"),
    )
    table = CustomerTable(f.qs)
    RequestConfig(request, paginate={"per_page": 10}).configure(table)
    export_format = request.GET.get("_export", None)
    if TableExport.is_valid_format(export_format):
        # TODO speed up the table export using celery

        exporter = TableExport(
            export_format,
            table,
            exclude_columns=("actions",),
            dataset_kwargs={"title": "loans"},
        )
        return exporter.response(f"table.{export_format}")
    context["filter"] = f
    context["table"] = table
    if request.htmx:
        print("htmx request")
        return render(
            request, "contact/customer_list_improved.html#customer-content", context
        )
    return render(request, "contact/customer_list_improved.html", context)


@login_required
def customer_detail(request, pk=None):
    context = {}
    cust = get_object_or_404(Customer, pk=pk)
    context["object"] = cust
    context["customer"] = cust
    loans = cust.loans_received.unreleased().for_table_display()
    context["loans"] = loans
    context["total_loans"] = loans.count()
    context["total_amount"] = sum([i.loan_amount for i in loans])
    worth = [(i.total_current_value or 0) - (i.total_due or 0) for i in loans]
    context["worth"] = sum(worth)

    if request.htmx:
        return render(
            request, "contact/customer_detail_improved.html#customer-detail", context
        )
    return render(request, "contact/customer_detail_improved.html", context)


@login_required
def customer_save(request, pk=None):
    if pk:
        customer = get_object_or_404(Customer, pk=pk)
        form = CustomerForm(
            request.POST or None, instance=customer, customer_id=customer.id
        )

        success_message = f"Customer {customer.name} Info Updated"
    else:
        customer = None
        form = CustomerForm(request.POST or None, instance=customer)

        success_message = "Customer created"

    if request.method == "POST":
        if form.is_valid():
            f = form.save(commit=False)
            f.created_by = request.user
            f.save()
            # action.send(request.user, action_object=f, verb=verb)

            messages.success(request, success_message)

            response = HttpResponse(status=200)
            response["HX-Trigger"] = "listChanged"  # Trigger client-side event
            response["HX-Redirect"] = reverse("contact_customer_detail", args=[f.id])
            return response

        else:
            messages.error(request, "Error saving customer")

    return TemplateResponse(
        request, "contact/customer_form.html", {"form": form, "customer": customer}
    )


@require_http_methods(["DELETE"])
def customer_delete(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    messages.error(request, f"Deleted customer {customer}")
    customer.delete()
    return HttpResponse("")


@login_required
def customer_merge(request):
    form = CustomerMergeForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            # merge logic
            original = form.cleaned_data["original"]
            duplicate = form.cleaned_data["duplicate"]
            duplicate_name = duplicate.name
            original.merge(duplicate)
            messages.success(
                request,
                f"merged customer {duplicate_name} into {original}",
            )
            response = HttpResponse()
            response["HX-redirect"] = reverse("contact_customer_list")
            return response
        else:
            messages.error(request, "Error merging customers")

    return TemplateResponse(
        request, "partials/crispy_form.html", context={"form": form}
    )
