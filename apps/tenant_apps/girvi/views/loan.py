import base64
import datetime
import math
import textwrap

from dateutil.relativedelta import relativedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.files.base import ContentFile
from django.db.models import (Count, F, Max, OuterRef, Prefetch, Q, Subquery,
                              Sum)
from django.db.models.functions import Coalesce, ExtractMonth, ExtractYear
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods  # new
from django.views.decorators.http import require_POST
from django.views.generic.dates import (DayArchiveView, MonthArchiveView,
                                        TodayArchiveView, WeekArchiveView,
                                        YearArchiveView)
from django_tables2.config import RequestConfig
from django_tables2.export.export import TableExport
from dynamic_preferences.registries import global_preferences_registry
from moneyed import Money
from num2words import num2words
from openpyxl import load_workbook
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Table, TableStyle

from apps.orgs.registries import company_preference_registry
from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.notify.models import NoticeGroup, Notification
from apps.tenant_apps.rates.models import Rate
from apps.tenant_apps.utils.htmx_utils import for_htmx
from apps.tenant_apps.utils.loan_pdf import (get_custom_jsk, get_loan_template,
                                             get_notice_pdf, print_labels_pdf)

from ..filters import LoanFilter
from ..forms import (LoanForm, LoanItemForm, LoanRenewForm, LoanReportForm,
                     LoanSelectionForm)
from ..models import *
from ..tables import LoanTable

# We instantiate a manager for our global preferences
global_preferences = global_preferences_registry.manager()
# company_preferences = company_preference_registry.manager()


def create_loan_notification(request, pk=None):
    # get loan instance
    loan = get_object_or_404(Loan, pk=pk)
    # create a noticegroup
    import random
    import string

    # Generate a random string of 3 letters
    random_string = "".join(random.choice(string.ascii_letters) for _ in range(3))
    ng = NoticeGroup.objects.create(
        name=f"{loan.loan_id}-{random_string}-{datetime.now().date()}"
    )
    notification = Notification.objects.create(
        group=ng,
        customer=loan.customer,
    )
    # add the loan to the notification
    notification.loans.add(loan)
    notification.save()
    return redirect(notification.get_absolute_url())


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


def ld(request):
    # TODO get last date by series
    # default_date = global_preferences["Loan__Default_Date"]
    default_date = request.user.workspace.preferences["Loan__Default_Date"]
    if default_date == "N":
        return datetime.now()
    else:
        last = Loan.objects.order_by("id").last()
        if not last:
            return datetime.now()
        return last.loan_date


def get_interestrate(request):
    metal = request.GET["itemtype"]
    interest = 0
    if metal == "Gold":
        # interest = global_preferences["Interest_Rate__gold"]
        interest = request.user.workspace.preferences["Interest_Rate__gold"]
    elif metal == "Silver":
        # interest = global_preferences["Interest_Rate__silver"]
        interest = request.user.workspace.preferences["Interest_Rate__silver"]
    else:
        # interest = global_preferences["Interest_Rate__other"]
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
        .with_details(request.grate, request.srate)
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
def create_loan(request, pk=None):
    if request.method == "POST":
        form = LoanForm(request.POST, request.FILES)
        if form.is_valid():
            l = form.save(commit=False)
            l.created_by = request.user

            image_data = request.POST.get("image_data")
            if image_data:
                image_file = ContentFile(
                    base64.b64decode(image_data.split(",")[1]),
                    name=f"{l.loan_id}_{l.customer.name}_{l.id}.jpg",
                )
                l.pic = image_file

            l.save()
            messages.success(request, f"Created Loan : {l.loan_id}")

            response = TemplateResponse(
                request,
                "girvi/loan/loan_detail.html",
                {"loan": l, "object": l},
            )
            response["Hx-Push-Url"] = reverse(
                "girvi:girvi_loan_detail", kwargs={"pk": l.id}
            )
            return response

        messages.warning(request, "Please correct the error below.")
        response = TemplateResponse(
            request, "girvi/loan/loan_form.html", {"form": form}
        )
        return response

    # try:
    #     series = Loan.objects.latest().series
    #     lid = series.loan_set.last().lid + 1
    # except Loan.DoesNotExist:
    #     series = Series.objects.first()
    #     lid = 1
    try:
        series = Loan.objects.latest().series
        last_loan = series.loan_set.last()
        if last_loan is None:
            lid = 1
        else:
            lid = last_loan.lid + 1
    except (Loan.DoesNotExist, Series.DoesNotExist):
        series = Series.objects.first()
        if series is None:
            messages.error(request, "No Series objects in database.")
        # if series is None:
        #     # Check if there are any License objects
        #     license = License.objects.first()
        #     if license is None:
        #         # Create a new License object
        #         license = License.objects.create(name="Default License", other_field="value")
        #     try:
        #         # Create a new Series object
        #         series = Series.objects.create(name="Default Series", license=license)
        #         lid = 1
        #     except IntegrityError:
        #         # Handle the exception, e.g., log an error message
        #         pass
        lid = 1

    initial = {
        "loan_date": ld(request),
        "series": series,
        "lid": lid,
    }
    if pk:
        initial["customer"] = get_object_or_404(Customer, pk=pk)

    form = LoanForm(initial=initial)
    return TemplateResponse(request, "girvi/loan/loan_form.html", {"form": form})


@login_required
@for_htmx(use_block="content")
def loan_update(request, id=None):
    obj = get_object_or_404(Loan, id=id)
    form = LoanForm(request.POST or None, instance=obj)

    if form.is_valid():
        l = form.save(commit=False)
        l.created_by = request.user
        image_data = request.POST.get("image_data")
        if image_data:
            image_file = ContentFile(
                base64.b64decode(image_data.split(",")[1]),
                name=f"{l.loan_id}_{l.customer.name}_{l.id}.jpg",
            )
            l.pic = image_file

        l.save()
        messages.success(request, messages.SUCCESS, f"updated Loan {l.loan_id}")

        response = TemplateResponse(
            request, "girvi/loan/loan_detail.html", {"loan": obj, "object": obj}
        )
        response["Hx-Push-Url"] = reverse(
            "girvi:girvi_loan_detail", kwargs={"pk": obj.id}
        )
        return response

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
        status=204, headers={"Hx-Redirect": reverse("girvi:girvi_loan_list")}
    )


@login_required
def next_loanid(request):
    try:
        series = request.GET.get("series")
        s = get_object_or_404(Series, pk=series)

        last_loan = s.loan_set.last()
        if last_loan:
            lid = last_loan.lid + 1
        else:
            lid = 1

        form = LoanForm(initial={"lid": lid})
        context = {
            "field": form["lid"],
        }
        return render(request, "girvi/partials/field.html", context)
    except (Series.DoesNotExist, Exception) as e:
        # Handle exceptions here, you can log the error or return an error response
        # For simplicity, here we are returning a basic error message
        return render(
            request,
            "error.html",
            {"error_message": "An error occurred in next_loanid."},
        )


@login_required
@for_htmx(use_block_from_params=True)
def loan_detail(request, pk):
    loan = get_object_or_404(
        Loan.objects.select_related(
            "customer", "series", "release", "created_by"
        ).prefetch_related("loan_payments", "loanitems"),
        pk=pk,
    )

    # Use values() and annotate() to perform calculations in the database
    weights = loan.get_weight
    result = [f"{item['itemtype']}:{round(item['total_weight'],3)}" for item in weights]
    weight = " ".join(result)

    pures = loan.get_pure
    result = {item["itemtype"]: round(item["pure_weight"], 3) for item in pures}

    rate_dict = {
        "Gold": request.grate.buying_rate,
        "Silver": request.srate.buying_rate,
    }

    # Calculate the total value
    result_dict = {
        itemtype: rate_dict.get(itemtype, None) * weight
        for itemtype, weight in result.items()
    }
    value = round(sum(result_dict.values()))
    try:
        lvratio = round(loan.loan_amount / value, 2) * 100
    except ZeroDivisionError:
        lvratio = 0
    context = {
        "object": loan,
        "sunken": loan.total() < value,
        # "items": loan.loanitems.all(),
        "statements": loan.statementitem_set.all(),
        "loan": loan,
        "weight": weight,
        "pure": result,
        # "customer_pic_url":f"{l.loan_id}_{l.customer.name}_{l.id}.jpg",
        "value": Money(value, "INR"),
        "worth": value - loan.due(),
        "lvratio": lvratio,
        "new_item_url": reverse(
            "girvi:girvi_loanitem_create", kwargs={"parent_id": loan.id}
        ),
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


@login_required
def notice(request):
    qyr = request.GET.get("qyr", 0)

    a_yr_ago = timezone.now() - relativedelta(years=int(qyr))

    # get all loans with selected ids
    selected_loans = (
        Loan.objects.unreleased()
        .filter(loan_date__lt=a_yr_ago)
        .order_by("customer")
        .select_related("customer")
    )

    # get a list of unique customers for the selected loans
    # customers = selected_loans.values('customer').distinct().count()
    customers = (
        Customer.objects.filter(loan__in=selected_loans)
        .distinct()
        .prefetch_related("loan_set", "address", "contactno")
    )

    data = {}
    data["loans"] = selected_loans
    data["loancount"] = selected_loans.count()
    data["total"] = selected_loans.total_loanamount()
    data["interest"] = selected_loans.with_total_interest()
    data["cust"] = customers

    return render(request, "girvi/loan/notice.html", context={"data": data})


@require_http_methods("POST")
@login_required
def deleteLoan(request):
    id_list = request.POST.getlist("selection")
    loans = Loan.objects.filter(id__in=id_list)
    for i in loans:
        i.delete()
    messages.error(request, f"Deleted {len(id_list)} loans")
    return loan_list(request)


def print_labels(request):
    # check if user wanted all rows to be selected
    all = request.POST.get("selectall")
    selected_loans = None

    if all == "selected":
        print("all selected")
        # get query parameters if all row selected and retrive queryset
        print(request.GET)
        filter = LoanFilter(
            request.GET,
            queryset=Loan.objects.unreleased()
            .select_related("customer", "release")
            .prefetch_related("notifications", "loanitems"),
        )

        selected_loans = filter.qs.order_by("customer")
        print(f"selected loans: {selected_loans.count()}")
    else:
        print("partially selected")
        # get the selected loan ids from the request
        selection = request.POST.getlist("selection")

        selected_loans = (
            Loan.objects.unreleased().filter(id__in=selection).order_by("customer")
        )

    if selected_loans:
        form = LoanSelectionForm(initial={"loans": selected_loans})
        from render_block import render_block_to_string

        response = render_block_to_string(
            "girvi/loan/print_labels.html", "content", {"form": form}, request
        )
        return HttpResponse(content=response)
        # return render(request, 'girvi/loan/print_labels.html', {'form': form})

    return HttpResponse(status=200, content="No unreleased loans selected.")


@for_htmx(use_block="content")
def print_label(request):
    if request.method == "POST":
        form = LoanSelectionForm(request.POST)
        if form.is_valid():
            loans = form.cleaned_data["loans"]
            return print_labels_pdf(loans)

        return render(request, "girvi/loan/print_labels.html", {"form": form})

    else:
        form = LoanSelectionForm()
        return render(request, "girvi/loan/print_labels.html", {"form": form})


@login_required
def notify_print(request):
    # check if user wanted all rows to be selected
    all = request.POST.get("selectall")
    selected_loans = None

    if all == "selected":
        print("all selected")
        # get query parameters if all row selected and retrive queryset
        print(request.GET)
        filter = LoanFilter(
            request.GET,
            queryset=Loan.objects.unreleased()
            .select_related("customer", "release")
            .prefetch_related("notifications", "loanitems"),
        )

        selected_loans = filter.qs.order_by("customer")
        print(f"selected loans: {selected_loans.count()}")
    else:
        print("partially selected")
        # get the selected loan ids from the request
        selection = request.POST.getlist("selection")

        selected_loans = (
            Loan.objects.unreleased().filter(id__in=selection).order_by("customer")
        )

    if selected_loans:
        # Create a new NoticeGroup
        ng = NoticeGroup.objects.create(name=datetime.now())

        # Get a queryset of customers with selected loans
        customers = Customer.objects.filter(loan__in=selected_loans).distinct()

        # Create a list of Notification objects to create
        notifications_to_create = []
        for customer in customers:
            notifications_to_create.append(
                Notification(
                    group=ng,
                    customer=customer,
                )
            )
        # Use bulk_create to create the notifications
        try:
            notifications = Notification.objects.bulk_create(notifications_to_create)
        except IntegrityError:
            print("Error adding notifications.")

        # Add loans to the notifications
        for notification in notifications:
            loans = selected_loans.filter(customer=notification.customer)
            notification.loans.set(loans)
            notification.save()
        return redirect(ng.get_absolute_url())

    return HttpResponse(status=200, content="No unreleased loans selected.")


@login_required
def print_loan(request, pk=None):
    loan = get_object_or_404(Loan, pk=pk)
    template = request.user.workspace.preferences["Loan__LoanPDFTemplate"]
    if template == "c":
        pdf = get_custom_jsk(loan=loan)
    else:
        pdf = get_loan_template(loan=loan)
    # Create a response object
    response = HttpResponse(pdf, content_type="application/pdf")
    # response["Content-Disposition"] = 'attachment; filename="pledge.pdf"'
    response["Content-Disposition"] = f"inline; filename='{loan.lid}.pdf'"
    return response


# @user_passes_test(lambda user: user.is_superuser)
def statement_create(request):
    if request.method == "POST":
        try:
            myfile = request.FILES["myfile"]
            wb = load_workbook(myfile, read_only=True)
            sheet = wb.active
        except KeyError:
            return JsonResponse(
                {"error": "file field is missing in the request."}, status=400
            )
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)

        with transaction.atomic():
            statement = Statement.objects.create(created_by=request.user)
            statement_items = []

            for row in sheet.iter_rows(min_row=0):
                loan_id = row[0].value
                loan = Loan.objects.filter(loanid=loan_id).first()

                if loan:
                    statement_items.append(
                        StatementItem(statement=statement, loan=loan)
                    )

            StatementItem.objects.bulk_create(statement_items)

        return JsonResponse(
            {
                "message": f"Statement {statement} with {len(statement_items)} items created."
            },
            status=201,
        )

    return JsonResponse(
        {"error": "This endpoint only accepts POST requests."}, status=405
    )


@login_required
def check_girvi(request, pk=None):
    if pk:
        statement = get_object_or_404(Statement, pk=pk)
    else:
        statement = Statement.objects.last()

    unreleased = list(Loan.objects.unreleased().values_list("loan_id", flat=True))
    unreleased_set = set(unreleased)
    physical = list(
        StatementItem.objects.filter(statement=statement).values_list(
            "loan__loan_id", flat=True
        )
    )
    statement_set = set(physical)
    data = {}
    data["records"] = len(unreleased_set)
    data["items"] = len(statement_set)

    data["missing_records"] = list(statement_set - unreleased_set)
    data["missing_items"] = list(unreleased_set - statement_set)
    missing_records = Loan.objects.filter(loan_id__in=data["missing_records"])
    missing_items = Loan.objects.filter(loan_id__in=data["missing_items"])
    return render(
        request,
        "girvi/loan/girvi_upload.html",
        context={
            "data": data,
            "statement": statement,
            "missing_items": missing_items,
            "missing_records": missing_records,
        },
    )


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
    return render(request, "girvi/partials/item-inline.html", {"object": item})


from django.utils.translation import gettext as _
from slick_reporting.fields import ComputationField
from slick_reporting.views import Chart, ListReportView, ReportView

class LoanByCustomerReport(ReportView):
    queryset = Loan.objects.unreleased()
    form_class = LoanReportForm
    group_by = "customer__name"
    columns = [
        "customer__name",
        ComputationField.create(Sum, "loan_amount", verbose_name="total_loan_amount"),
    ]
    chart_settings = [
        Chart(
            "Customer Loan Report",
            Chart.PIE,
            data_source=["sum__loan_amount"],
            title_source=["customer__name"],
        ),
    ]

class LoanTimeSeriesReport(ReportView):
    queryset = Loan.unreleased.all()
    form_class = LoanReportForm
    group_by = "customer__name"
    time_series_pattern = "annually"
    # options are: "daily", "weekly", "bi-weekly", "monthly", "quarterly", "semiannually", "annually" and "custom"

    time_series_selector = True
    time_series_selector_choices = (
        ("daily", _("Daily")),
        ("weekly", _("Weekly")),
        ("bi-weekly", _("Bi-Weekly")),
        ("monthly", _("Monthly")),
    )
    time_series_selector_default = "bi-weekly"

    time_series_selector_label = _("Period Pattern")
    # The label for the time series selector

    time_series_selector_allow_empty = True

    date_field = "loan_date"
    title = _("Loan Time Series Report")
    time_series_columns = [
        ComputationField.create(Sum, "loan_amount", verbose_name="Total Loan Amount"),
    ]
    columns = [
        "customer__name",
        "__time_series__",
        ComputationField.create(Sum, "loan_amount", verbose_name="Total Loan Amount"),
    ]
    chart_settings = [
        Chart(
            "Customer Loan Time Series",
            Chart.BAR,
            data_source=["sum__loan_amount"],
            title_source=["__time_series__"],
        ),
        Chart(
            "Total Loan Amount Monthly",
            Chart.PIE,
            data_source=["sum__loan_amount"],
            title_source=["customer__name"],
            plot_total=True,
        ),
        Chart(
            "Total Loan Amount [Area Chart]",
            Chart.AREA,
            data_source=["sum__loan_amount"],
            title_source="customer",
        ),
    ]


class SeriesReport(ReportView):
    queryset = Loan.objects.unreleased()
    form_class = LoanReportForm
    group_by = "series__name"
    columns = [
        "series__name",
        ComputationField.create(Sum, "loan_amount", verbose_name="total_loan_amount"),
    ]
    chart_settings = [
        Chart(
            "Series report",
            Chart.PIE,
            data_source=["sum__loan_amount"],
            title_source=["series__name"],

        ),
    ]


class LicenseReport(ReportView):
    queryset = Loan.objects.unreleased()
    form_class = LoanReportForm
    group_by = "series__license__name"
    columns = [
        "series__license__name",
        ComputationField.create(Sum, "loan_amount", verbose_name="total_loan_amount"),
    ]
    chart_settings = [
        Chart(
            "License report",
            Chart.PIE,
            data_source=["sum__loan_amount"],
            title_source=["series__license__name"],
        ),
    ]


class LoanCrosstabReport(ReportView):
    report_title = "Cross tab Report"
    queryset = Loan.unreleased.all()
    group_by = "customer__name"
    date_field = "loan_date"
    form_class = LoanReportForm

    columns = [
        "customer__name",
        "__crosstab__",
        ComputationField.create(Sum, "loan_amount", verbose_name="Loan Sum"),
    ]


class LoanListReport(ListReportView):
    queryset = Loan.unreleased.all()
    columns = ["id", "loan_date", "customer__name", "loan_amount"]
