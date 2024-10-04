import base64
import datetime

from dateutil.relativedelta import relativedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.files.base import ContentFile
from django.db.models import F, Sum
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods  # new
from django_tables2.config import RequestConfig
from django_tables2.export.export import TableExport
from moneyed import Money
from num2words import num2words
from openpyxl import load_workbook

from apps.orgs.registries import company_preference_registry
from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.rates.models import Rate
from apps.tenant_apps.utils.htmx_utils import for_htmx

from ..filters import LoanFilter
from ..forms import LoanForm, LoanItemForm, LoanRenewForm, LoanReportForm
from ..models import *
from ..services import generate_loan_id
from ..tables import LoanTable
import pytz

def ld(request):
    # TODO get last date by series

    default_date = request.user.workspace.preferences["Loan__Default_Date"]
    user_timezone = "Asia/Kolkata"
    user_tz = pytz.timezone(user_timezone)
    if default_date == "N":
        now = timezone.now()
        user_time = now.astimezone(user_tz)
        return user_time.strftime("%Y-%m-%dT%H:%M")
    else:
        last = Loan.objects.order_by("-id").first()
        if not last:
            now = timezone.now()
            user_time = now.astimezone(user_tz)
            return user_time.strftime("%Y-%m-%dT%H:%M")
        loan_time = last.loan_date.astimezone(user_tz)
        return loan_time.strftime("%Y-%m-%dT%H:%M")


def get_interestrate(request):
    metal = request.GET["itemtype"]
    interest = 0
    if metal == "Gold":
        interest = request.user.workspace.preferences["Interest_Rate__gold"]
    elif metal == "Silver":
        interest = request.user.workspace.preferences["Interest_Rate__silver"]
    else:
        interest = request.user.workspace.preferences["Interest_Rate__other"]
    form = LoanItemForm(initial={"interestrate": interest})
    context = {
        "field": form["interestrate"],
    }
    return render(request, "girvi/partials/field.html", context)


@login_required
@for_htmx(use_block_from_params=True)
def loan_list(request):
    filter = LoanFilter(
        request.GET,
        request=request,
        queryset=Loan.objects.order_by("-id")
        .with_details(request.grate, request.srate, request.brate)
        .select_related("customer", "release", "created_by")
        .prefetch_related("notifications", "loanitems"),
    )
    table = LoanTable(filter.qs)

    RequestConfig(request, paginate={"per_page": 10}).configure(table)
    export_format = request.GET.get("_export", None)
    if TableExport.is_valid_format(export_format):
        # TODO speed up the table export using celery

        exporter = TableExport(
            export_format,
            table,
            exclude_columns=(
                "selection",
                "notified",
                "months_since_created",
                "current_value",
                "total_due",
                "total_interest",
            ),
            dataset_kwargs={"title": "loans"},
        )
        return exporter.response(f"table.{export_format}")
    context = {
        "filter": filter,
        "table": table,
        "export_formats": ["csv", "xls", "xlsx", "json", "html"],
        "total_loan_amount": filter.qs.total_loanamount(),
        "total_interest": filter.qs.aggregate(total=Sum("total_interest")),
    }
    return TemplateResponse(request, "girvi/loan/loan_list.html", context)


@login_required
@for_htmx(use_block="content")
def loan_save(request, id=None, pk=None):
    obj = get_object_or_404(Loan, id=id) if id else None
    form = LoanForm(request.POST or None, instance=obj)

    if request.method == "POST":
        if form.is_valid():
            loan = form.save(commit=False)
            loan.created_by = request.user
            loan.save()
            messages.success(
                request, f"{'Updated' if obj else 'Created'} Loan: {loan.loan_id}"
            )
            return loan_detail(request, loan.id)
            # response = TemplateResponse(
            #     request,
            #     "girvi/loan/loan_detail.html",
            #     {"loan": loan, "object": loan, "customer": loan.customer},
            # )
            # response["Hx-Push-Url"] = reverse(
            #     "girvi:girvi_loan_detail", kwargs={"pk": loan.id}
            # )
            # return response

        else:
            messages.warning(request, "Please correct the error below.")
            print(form.errors)

    if not obj:
        initial = {}

        try:
            latest_loan = Loan.objects.latest("id")
            series = latest_loan.series.id
        except Loan.DoesNotExist:
            print("No loans exist yet.")
            series = None
        try:
            loan_id = generate_loan_id(series_id=series)
            initial["loan_id"] = loan_id
            initial["loan_date"] = ld(request)
            initial["series"] = series
            # print(f"Generated loan ID: {loan_id}")
        except License.DoesNotExist as e:
            print(f"License does not exist: {e}")
            messages.error(request, "No License objects in database.")
            response = HttpResponse()
            response["HX-Redirect"] = reverse("girvi:girvi_license_list")
            return response
            # Handle the case where no license exists, e.g., log the error, notify the user, etc.
        except Exception as e:
            print(f"Unexpected error: {e}")
            messages.error(request, "Unexpected error: {e}")
            response = HttpResponse()
            response["HX-Redirect"] = reverse("girvi:girvi_license_list")
            return response

        if pk:
            initial["customer"] = get_object_or_404(Customer, pk=pk)
        form = LoanForm(initial=initial)

    return TemplateResponse(
        request, "girvi/loan/loan_form.html", {"form": form, "loan": obj, "object": obj}
    )


@require_http_methods(["DELETE"])
@login_required
def loan_delete(request, pk=None):
    obj = get_object_or_404(Loan, id=pk)
    obj.delete()
    messages.error(request, f" Loan {obj} Deleted")
    return HttpResponse(
        status=204,
        headers={
            # "Hx-Redirect": reverse("girvi:girvi_loan_list")
            "hx-Trigger": "loanDeleted"
        },
    )


@login_required
@for_htmx(use_block_from_params=True)
def loan_detail(request, pk):
    loan = get_object_or_404(
        Loan.objects.select_related("customer", "created_by", "series")
        .prefetch_related("release", "loanitems", "loan_payments", "statementitem_set")
        .with_details(request.grate, request.srate),
        pk=pk,
    )
    gold_weight = (
        f"G:{loan.total_gold_weight} gms" if loan.total_gold_weight > 0 else ""
    )
    silver_weight = (
        f"S:{loan.total_silver_weight} gms" if loan.total_silver_weight > 0 else ""
    )
    bronze_weight = (
        f"B:{loan.total_bronze_weight} gms" if loan.total_bronze_weight > 0 else ""
    )

    # Combine the weights, ensuring there are no extra spaces
    weight = " ".join(filter(None, [gold_weight, silver_weight, bronze_weight]))

    gold_pure = (
        f"G:{round(loan.pure_gold_weight,3)} gms" if loan.pure_gold_weight > 0 else ""
    )
    silver_pure = (
        f"S:{round(loan.pure_silver_weight,3)} gms"
        if loan.pure_silver_weight > 0
        else ""
    )
    bronze_pure = (
        f"B:{round(loan.pure_bronze_weight,3)} gms"
        if loan.pure_bronze_weight > 0
        else ""
    )

    # Combine the weights, ensuring there are no extra spaces
    pure = " ".join(filter(None, [gold_pure, silver_pure, bronze_pure]))
    value = round(loan.get_current_value(), 2)

    try:
        lvratio = round(loan.loan_amount / value, 2) * 100
    except ZeroDivisionError:
        lvratio = 0

    due = loan.due()
    # due = loan.total_due

    try:
        dvratio = round(due / value, 2) * 100
    except ZeroDivisionError:
        dvratio = 0
    location = loan.get_storage_box()
    if location:
        position = location.position_for_item(loan.id)
    else:
        position = None
    context = {
        "object": loan,
        "loan": loan,
        "customer": loan.customer,
        "items": loan.loanitems.all(),
        "payments": loan.loan_payments.all(),
        "value": Money(value, "INR"),
        "worth": value - due,
        "lvratio": lvratio,
        "dvratio": dvratio,
        "weight": weight,
        "pure": pure,
        "je": JournalEntry.objects.filter(
            Q(content_type=ContentType.objects.get_for_model(loan), object_id=loan.id)
            | Q(
                parent_content_type=ContentType.objects.get_for_model(loan),
                parent_object_id=loan.id,
            )
        ),
        "location": location,
        "position": position,
        "expires": loan.calculate_months_to_exceed_value(value, due),
    }

    return TemplateResponse(request, "girvi/loan/loan_detail.html", context)


@login_required
@for_htmx(use_block="content")
def loan_renew(request, pk):
    loan = get_object_or_404(Loan, pk=pk)

    if request.method == "POST":
        # create a form instance and populate it with data from the request:
        form = LoanRenewForm(request.POST)
        # check whether it's valid:
        if form.is_valid():
            # process the data in form.cleaned_data as required
            new_loanamount = (
                loan.due() + form.cleaned_data["amount"] + form.cleaned_data["interest"]
            )
            newloan = Loan(
                series=loan.series,
                customer=loan.customer,
                lid=Loan.objects.filter(series=loan.series).latest("lid").lid + 1,
                loan_amount=new_loanamount,
            )
            newloan.save()
            # copy and create loan.loanitems to newloan.items
            for item in loan.loanitems.all():
                newloan.loanitems.add(item)
            newloan.save()
            # create a new release object
            try:
                releaseid = Release.objects.latest("id").id + 1
            except Release.DoesNotExist:
                releaseid = 1  # if no release objects exist
            Release.objects.create(
                release_id=releaseid,
                loan=loan,
            )

            # redirect to a new URL:
            messages.success(request, f"Renewed Loan : {newloan.loan_id}")
            return redirect(newloan)

    # if a GET (or any other method) we'll create a blank form
    else:
        form = LoanRenewForm()
    response = TemplateResponse(
        request, "girvi/loan/loan_renew.html", {"form": form, "loan": loan}
    )
    response["Hx-Push-Url"] = reverse("girvi:girvi_loan_renew", kwargs={"pk": loan.id})
    return response


@require_http_methods("POST")
@login_required
def deleteLoan(request):
    id_list = request.POST.getlist("selection")
    loans = Loan.objects.filter(id__in=id_list)
    for i in loans:
        i.delete()
    messages.error(request, f"Deleted {len(id_list)} loans")
    return loan_list(request)


@login_required
def loan_item_update_hx_view(request, parent_id=None, id=None):
    if not request.htmx:
        raise Http404("This view is meant for Htmx requests only.")

    try:
        parent_obj = Loan.objects.get(id=parent_id)
    except Loan.DoesNotExist:
        return HttpResponse("Not found.", status=404)

    instance = None
    if id is not None:
        try:
            instance = LoanItem.objects.get(loan=parent_obj, id=id)
        except LoanItem.DoesNotExist:
            instance = None

    if request.method == "POST":
        form = LoanItemForm(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            new_obj = form.save(commit=False)
            if instance is None:
                new_obj.loan = parent_obj
            image_data = request.POST.get("image_data")

            if image_data:
                image_file = ContentFile(
                    base64.b64decode(image_data.split(",")[1]),
                    name=f"{new_obj.loan.loan_id}_{new_obj.id}.jpg",
                )

                new_obj.pic = image_file
            new_obj.save()
            messages.success(request, f"Created Item : {new_obj.id}")
            context = {"object": new_obj}

            if request.htmx:
                return HttpResponse(status=204, headers={"HX-Trigger": "loanChanged"})
            return render(request, "girvi/partials/item-inline.html", context)
        # else:
        #     context = {"url": url, "form": form, "object": instance}
        #     return render(request, "girvi/partials/item-form.html", context)

    else:
        form = LoanItemForm(instance=instance)

    url = reverse("girvi:girvi_loanitem_create", kwargs={"parent_id": parent_obj.id})
    if instance:
        url = instance.get_hx_edit_url()

    context = {"url": url, "form": form, "object": instance}
    return render(request, "girvi/partials/item-form.html", context)


@login_required
def loanitem_delete(request, parent_id, id):
    item = get_object_or_404(LoanItem, id=id, loan_id=parent_id)
    loan = item.loan
    item.delete()
    messages.error(request, f"Item {item} Deleted")
    loan.save()
    return HttpResponse(status=204, headers={"HX-Trigger": "loanChanged"})


@login_required
def loanitem_detail(request, pk):
    item = get_object_or_404(LoanItem, pk=pk)
    return render(request, "girvi/partials/item-inline-new.html", {"object": item})
