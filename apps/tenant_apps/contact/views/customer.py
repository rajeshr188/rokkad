from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django_tables2.export.export import TableExport
from django.shortcuts import render
from ..filters import CustomerFilter
from ..forms import CustomerForm, CustomerMergeForm
from ..models import Customer
from ..tables import CustomerTable
from .common import (
    get_customer_detail_context,
    get_customer_for_detail,
    render_customer_detail_fragment,
)


CUSTOMER_LIST_TEMPLATE = "contact/customer_list_improved.html"


def _get_customer_list_context(request):
    customer_queryset = Customer.objects.all().prefetch_related("contactno", "address")
    customer_filter = CustomerFilter(request.GET, queryset=customer_queryset)
    filtered_queryset = customer_filter.qs
    paginator = Paginator(filtered_queryset, 12)
    page_obj = paginator.get_page(request.GET.get("page"))

    return {
        "filter": customer_filter,
        "customers": page_obj.object_list,
        "page_obj": page_obj,
        "results_count": paginator.count,
    }


@login_required
def customer_list(request):
    context = _get_customer_list_context(request)
    export_format = request.GET.get("_export", None)
    if TableExport.is_valid_format(export_format):
        table = CustomerTable(context["filter"].qs)
        exporter = TableExport(
            export_format,
            table,
            exclude_columns=("actions",),
            dataset_kwargs={"title": "loans"},
        )
        return exporter.response(f"table.{export_format}")

    if request.htmx:
        fragment_name = "customer-list-results"
        if request.headers.get("HX-Target") == "content":
            fragment_name = "customer-content"
        return render(request, f"{CUSTOMER_LIST_TEMPLATE}#{fragment_name}", context)
    return render(request, CUSTOMER_LIST_TEMPLATE, context)


@login_required
def customer_detail(request, pk=None):
    cust = get_customer_for_detail(pk)
    context = get_customer_detail_context(cust)

    if request.htmx:
        return render(request, "contact/customer_detail_improved.html#customer-detail", context)
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
            messages.success(request, success_message)

            if pk:
                # Update from detail page: refresh hero section, close modal
                refreshed = get_customer_for_detail(f.id)
                return render_customer_detail_fragment(
                    request,
                    refreshed,
                    "customer-hero",
                    headers={
                        "HX-Retarget": "#customer-hero",
                        "HX-Reswap": "outerHTML",
                        "HX-Trigger": "contactModalClose",
                    },
                )
            else:
                # Create: navigate to the new customer's detail page
                response = HttpResponse(status=200)
                response["HX-Redirect"] = reverse("contact_customer_detail", args=[f.id])
                return response

        else:
            messages.error(request, "Error saving customer")

    return TemplateResponse(
        request, "contact/customer_form.html", {"form": form, "customer": customer}
    )


@require_http_methods(["POST","DELETE"])
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
        request, "contact/customer_merge_form.html", context={"form": form}
    )
