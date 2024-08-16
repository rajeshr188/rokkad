import base64
import uuid
from datetime import datetime
from importlib import import_module

from actstream import action
from django.apps import apps
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.template.response import TemplateResponse
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_http_methods  # new
from django_tables2.config import RequestConfig
from django_tables2.export.export import TableExport
from django_tenants.utils import schema_context
from import_export import resources
from import_export.formats import base_formats
from tablib import Dataset

from apps.tenant_apps.utils.htmx_utils import for_htmx

from .filters import CustomerFilter
from .forms import (AddressForm, ContactForm, CustomerForm, CustomerMergeForm,
                    CustomerPicForm, CustomerRelationshipForm,
                    CustomerReportForm, ExportForm, ImportForm)
from .models import (Address, Contact, Customer, CustomerPic,
                     CustomerRelationship, Proof)
from .tables import CustomerExportTable, CustomerTable


@login_required
def export_form(request):
    if request.method == "POST":
        form = ExportForm(request.POST)
        if form.is_valid():
            return export_data(
                request,
                form.cleaned_data["model_name"],
                form.cleaned_data["export_format"],
            )
    else:
        form = ExportForm()

    return render(request, "export.html", {"form": form})


@login_required
def export_data(request, model_name, export_format):
    # Check if the model exists in any of the tenant apps
    model = None
    for app in settings.TENANT_APPS:
        try:
            # model = apps.get_model(app_label=app, model_name=model_name)
            model = apps.get_model(app.split(".")[-1], model_name)
            break
        except LookupError:
            continue

    if not model:
        return HttpResponseBadRequest(f"Model '{model_name}' does not exist.")

    # Check if the export format is valid
    # valid_formats = [fmt().get_title() for fmt in base_formats()]
    valid_formats = [
        fmt().get_title()
        for fmt in [
            base_formats.CSV,
            base_formats.JSON,
            base_formats.XLS,
            base_formats.HTML,
        ]
    ]
    # valid_formats = ["csv", "json", "xls", "html"]
    if export_format not in valid_formats:
        return HttpResponseBadRequest(f"Invalid export format '{export_format}'.")

    # Get the schema name from the request
    # schema_name = request.user.workspace.schema_name

    # Import the ModelResource for the model
    try:
        admin_module = import_module(f"{app}.admin")
        ModelResource = getattr(admin_module, f"{model_name}Resource")
    except (ImportError, AttributeError):
        ModelResource = resources.modelresource_factory(model=model)
        # # TODO create a default ModelResource on the fly
        # return HttpResponseBadRequest(f"ModelResource for '{model_name}' does not exist.")

    # Export the data
    # with schema_context(schema_name):
    dataset = ModelResource().export()
    export_data = dataset.export(format=export_format)

    # Create the HTTP response with the exported data
    response = HttpResponse(export_data, content_type="application/octet-stream")
    response[
        "Content-Disposition"
    ] = f'attachment; filename="{request.user.workspace}_{model_name}.{export_format}"'
    return response


@login_required
def import_data(request):
    form = ImportForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        model_name = form.cleaned_data["model_name"]
        import_file = form.cleaned_data["import_file"]

        model = None
        for app in settings.TENANT_APPS:
            try:
                model = apps.get_model(app.split(".")[-1], model_name)
                break
            except LookupError:
                continue

        if model is None:
            raise ValueError(f"No model named '{model_name}' found in TENANT_APPS")

        model_resource = resources.modelresource_factory(model=model)()
        dataset = Dataset().load(import_file.read().decode())
        with transaction.atomic():
            result = model_resource.import_data(dataset, raise_errors=True)

        if not result.has_errors():
            # TODO: Handle the imported data (e.g., save it to the database)
            rows_imported = [row for row in result.rows if row.diff]
            return render(
                request, "import_success.html", {"rows_imported": rows_imported}
            )
        else:
            errors = result.get_errors()
            return render(request, "import_error.html", {"errors": errors})

    return render(request, "import.html", {"form": form})


@login_required
@for_htmx(use_block_from_params=True)
def customer_list(request):
    context = {}
    f = CustomerFilter(
        request.GET,
        queryset=Customer.objects.all()
        .prefetch_related("contactno", "address")
        .annotate(
            loans=Count("loan"), loanamount=Coalesce(Sum("loan__loan_amount"), 0)
        ),
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

    return TemplateResponse(request, "contact/customer_list.html", context)


@require_http_methods(["DELETE"])
def customer_delete(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    customer.delete()
    messages.error(request, messages.DEBUG, f"Deleted customer {customer.name}")
    return HttpResponse("")


@login_required
@for_htmx(use_block="content")
def customer_create(request):
    if request.method == "POST":
        form = CustomerForm(request.POST or None, request.FILES)

        if form.is_valid():
            f = form.save(commit=False)
            f.created_by = request.user
            f.save()
            action.send(request.user, action_object=f, verb="created")

            messages.success(request, messages.SUCCESS, f"Customer {f.name} created.")
            if "add" in request.POST:
                response = TemplateResponse(
                    request, "contact/customer_form.html", {"form": CustomerForm()}
                )
                response["HX-Push-Url"] = reverse("contact_customer_create")
                return response

            else:
                response = TemplateResponse(
                    request,
                    "contact/customer_detail.html",
                    {"customer": f, "object": f},
                )
                response["HX-Push-Url"] = reverse(
                    "contact_customer_detail", kwargs={"pk": f.id}
                )
                return response
        else:
            messages.error(request, f"Error creating customer")
            return TemplateResponse(
                request, "contact/customer_form.html", {"form": form}
            )

    else:
        form = CustomerForm()
        return TemplateResponse(request, "contact/customer_form.html", {"form": form})


@login_required
@for_htmx(use_block="content")
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
                messages.SUCCESS,
                f"merged customer {duplicate_name} into {original}",
            )
            return redirect("contact_customer_list")

    return TemplateResponse(
        request, "contact/customer_merge.html", context={"form": form}
    )


@for_htmx(use_block="content")
@login_required
def customer_detail(request, pk=None):
    context = {}
    cust = get_object_or_404(Customer, pk=pk)
    context["object"] = cust
    context["customer"] = cust
    loans = cust.loan_set.unreleased().with_details(request.grate, request.srate)
    context["loans"] = loans
    context["total_loans"] = loans.count()
    context["total_amount"] = sum([i.loan_amount for i in loans])
    worth = [i.worth for i in loans]
    context["worth"] = sum(worth)
    return TemplateResponse(request, "contact/customer_detail.html", context)


@login_required
@for_htmx(use_block="content")
def customer_edit(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    form = CustomerForm(request.POST or None, instance=customer)

    if form.is_valid():
        f = form.save(commit=False)
        f.created_by = request.user
        f.save()
        action.send(request.user, action_object=customer, verb="updated")
        messages.success(
            request, messages.SUCCESS, f"Customer {customer.name} Info Updated"
        )

        response = TemplateResponse(
            request,
            "contact/customer_detail.html",
            {"customer": customer, "object": customer},
        )
        response["HX-Push-Url"] = reverse(
            "contact_customer_detail", kwargs={"pk": customer.id}
        )
        return response

    return TemplateResponse(
        request, "contact/customer_form.html", {"form": form, "customer": customer}
    )


@login_required
def customer_pics(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    pics = customer.pics.all()
    return TemplateResponse(
        request, "contact/customer_pics.html", {"customer": customer, "pics": pics}
    )


@login_required
def add_customer_pic(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    if request.method == "POST":
        form = CustomerPicForm(request.POST, request.FILES)
        if form.is_valid():
            customer_pic = form.save(commit=False)
            customer_pic.customer = customer
            image_data = request.POST.get("image_data")

            if image_data:
                # Generate a unique identifier
                unique_id = uuid.uuid4()

                # Create the image file with the UUID as the name
                image_file = ContentFile(
                    base64.b64decode(image_data.split(",")[1]),
                    name=f"{unique_id}.jpg",
                )
                customer_pic.image = image_file

            customer_pic.save()
            return redirect("contact_customer_detail", pk=customer.id)
    else:
        form = CustomerPicForm()
    return render(
        request,
        "contact/add_customer_pic.html",
        {
            "form": form,
            "customer": customer,
            "url": reverse_lazy(
                "contact_customer_pic_add", kwargs={"customer_id": customer.id}
            ),
        },
    )


@login_required
@require_http_methods(["DELETE"])
def customer_pic_delete(request, pk):
    instance = get_object_or_404(CustomerPic, pk=pk)
    instance.delete()
    messages.error(request, messages.ERROR, f"Customer Pic {instance} deleted.")
    return HttpResponse(status=204, headers={"HX-Trigger": "listChanged"})


@login_required
@require_http_methods(["POST"])
def customer_pic_set_default(request, pk):
    instance = get_object_or_404(CustomerPic, pk=pk)
    customer = instance.customer
    # Update all related CustomerPic instances to set is_default to False
    CustomerPic.objects.filter(customer=customer).update(is_default=False)
    # Set the selected CustomerPic instance to be the default
    instance.is_default = True
    instance.save()
    return HttpResponse(status=204, headers={"HX-Trigger": "listChanged"})


@login_required
def create_relationship(request, from_customer_id):
    from_customer = get_object_or_404(Customer, pk=from_customer_id)

    if request.method == "POST":
        form = CustomerRelationshipForm(request.POST, customer_id=from_customer)
        if form.is_valid():
            print(form.cleaned_data)
            print(form.errors)
            related_customer = form.cleaned_data["related_customer"]
            relationship = form.cleaned_data["relationship"]

            # Create a new CustomerRelationship instance
            CustomerRelationship.objects.create(
                customer=from_customer,
                relationship=relationship,
                related_customer=related_customer,
            )

            return redirect("contact_customer_detail", pk=from_customer_id)

    else:
        form = CustomerRelationshipForm(customer_id=from_customer)

    return render(
        request,
        "contact/create_relationship.html",
        {"form": form, "customer": from_customer},
    )


@login_required
def contact_create(request, pk=None):
    customer = get_object_or_404(Customer, pk=pk)
    form = ContactForm(request.POST or None, initial={"customer": customer})

    if request.method == "POST" and form.is_valid():
        f = form.save(commit=False)
        f.customer = customer
        f.save()
        messages.success(request, messages.SUCCESS, f"Contact {f} created.")
        return HttpResponse(status=204, headers={"HX-Trigger": "listChanged"})
        # return HttpResponse(status=204, headers={"HX-Redirect": reverse("contact_customer_list")})

    return render(
        request,
        "contact/partials/contact_form.html",
        context={"form": form, "customer": customer},
    )


@login_required
def contact_list(request, pk: int = None):
    customer = get_object_or_404(Customer, id=pk)
    contacts = customer.contactno.all()
    return render(
        request,
        "contact/contact_list.html",
        {"contacts": contacts, "customer_id": customer.id},
    )


@login_required
def contact_detail(request, pk):
    contact = get_object_or_404(Contact, pk=pk)
    return render(request, "contact/contact_detail.html", context={"i": contact})


@login_required
def contact_update(request, pk):
    contact = get_object_or_404(Contact, pk=pk)
    form = ContactForm(request.POST or None, instance=contact)
    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, messages.SUCCESS, f"Contact {contact} updated.")
            return render(
                request, "contact/contact_detail.html", context={"i": contact}
            )
    return render(
        request,
        "contact/partials/contact_update_form.html",
        context={"form": form, "contact": contact},
    )


@login_required
@require_http_methods(["DELETE"])
def contact_delete(request, pk):
    contact = get_object_or_404(Contact, pk=pk)
    contact.delete()
    messages.error(request, messages.ERROR, f"Contact {contact} deleted.")
    return HttpResponse(status=204, headers={"HX-Trigger": "listChanged"})


@login_required
def address_list(request, pk: int = None):
    customer = get_object_or_404(Customer, id=pk)
    addresses = customer.address.all()
    return render(
        request,
        "contact/address_list.html",
        {"addresses": addresses, "customer_id": customer.id},
    )


# @login_required
# def address_create(request, pk=None):
#     customer = get_object_or_404(Customer, pk=pk)
#     form = AddressForm(request.POST or None,customer_id = customer.id,)

#     if request.method == "POST" and form.is_valid():
#         address = form.save(commit=False)
#         address.customer = customer

#         address.save()
#         messages.success(request, messages.SUCCESS, f"Address {address} created.")
#         # return HttpResponse(headers={"HX-Trigger": "listChanged"})
#         return render(request,"contact/address_detail.html",context={"i":address})

#     return render(
#         request,
#         "partials/crispy_form.html",
#         context={"form": form, "customer": customer},
#     )

# @login_required
# def address_update(request, pk):
#     address = get_object_or_404(Address, pk=pk)
#     form = AddressForm(request.POST or None, instance=address)
#     if request.method == "POST":
#         if form.is_valid():
#             form.save()
#             messages.success(request, messages.SUCCESS, f"Address {address} updated.")
#             return render(
#                 request, "contact/address_detail.html", context={"i": address}
#             )

#     return render(
#         request,
#         "contact/partials/address_update_form.html",
#         context={"form": form, "address": address},
#     )

@login_required
def address_create_or_update(request, customer_pk=None, address_pk=None):
    customer = get_object_or_404(Customer, pk=customer_pk)
    address = None
    if address_pk:
        address = get_object_or_404(Address, pk=address_pk)
        form = AddressForm(request.POST or None, instance=address, )
    else:
        form = AddressForm(request.POST or None, )

    if request.method == "POST" and form.is_valid():
        address = form.save(commit=False)
        address.customer = customer
        address.save()
        if address_pk:
            messages.success(request, messages.SUCCESS, f"Address {address} updated.")
        else:
            messages.success(request, messages.SUCCESS, f"Address {address} created.")
        # return HttpResponse(headers={"HX-Trigger": "listChanged"})
        return render(request, "contact/address_detail.html", context={"i": address})

    template_name = (
        "contact/partials/address_update_form.html" if address_pk else "contact/partials/address_form.html"
    )
    context = {"form": form, "customer": customer}
    if address:
        context["address"] = address

    return render(request, template_name, context)

@login_required
def address_detail(request, pk):
    address = get_object_or_404(Address, pk=pk)
    return render(request, "contact/address_detail.html", context={"i": address})

@login_required
@require_http_methods(["DELETE"])
def address_delete(request, pk):
    address = get_object_or_404(Address, pk=pk)
    address.delete()
    messages.error(request, messages.ERROR, f"Address {address} deleted.")
    return HttpResponse("")


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


from slick_reporting.fields import ComputationField
from slick_reporting.views import ListReportView, ReportView


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
