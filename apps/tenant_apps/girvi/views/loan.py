import base64
import datetime

from dateutil.relativedelta import relativedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.files.base import ContentFile
from django.db.models import Count, F, OuterRef, Subquery, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods  # new
from django_tables2.config import RequestConfig
from django_tables2.export.export import TableExport
from dynamic_preferences.registries import global_preferences_registry
from moneyed import Money
from num2words import num2words
from openpyxl import load_workbook

from apps.orgs.registries import company_preference_registry
from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.notify.models import NoticeGroup, Notification
from apps.tenant_apps.rates.models import Rate
from apps.tenant_apps.utils.htmx_utils import for_htmx

from ..filters import LoanFilter
from ..forms import (
    LoanForm,
    LoanItemForm,
    LoanRenewForm,
    LoanReportForm,
    LoanSelectionForm,
)
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
        itemtype: rate_dict.get(itemtype, 0) * weight
        for itemtype, weight in result.items()
    }
    value = round(sum(result_dict.values()))
    try:
        lvratio = round(loan.loan_amount / value, 2) * 100
    except ZeroDivisionError:
        lvratio = 0

    try:
        dvratio = round(loan.due() / value, 2) * 100
    except ZeroDivisionError:
        dvratio = 0
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
        "dvratio": dvratio,
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
    return render(request, "girvi/partials/item-inline.html", {"object": item})


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


def verification_session_list(request):
    sessions = Statement.objects.all()
    return render(
        request,
        "girvi/statement/statement_list.html",
        context={"sessions": sessions},
    )


def verification_session_create(request):
    v_session = Statement.objects.create(created_by=request.user)
    return redirect(v_session.get_absolute_url())


def verification_session_detail(request, pk):
    statement = get_object_or_404(Statement, pk=pk)
    statement_items = statement.statementitem_set.select_related("loan").all()

    summary = {}
    if statement.completed:
        summary["dc"] = statement_items.filter(descrepancy_found=True)
        summary["descrepancy_loans"] = statement.statementitem_set.aggregate(
            total=Count("pk"),
            discrepancy=Count("pk", filter=F("descrepancy_found")),
        )
        summary["missing_loans"] = Loan.objects.unreleased().exclude(
            loan_id__in=statement_items.values_list("loan__loan_id", flat=True)
        )
        summary["unreleased"] = Loan.objects.unreleased()

    return render(
        request,
        "girvi/statement/statement_detail.html",
        context={
            "statement": statement,
            "summary": summary,
            "items": statement_items,
            "summary": summary,
        },
    )


def complete_verification_session(request, pk):
    statement = get_object_or_404(Statement, pk=pk)

    # Subquery to check if a loan is in the statement items
    statement_item_subquery = StatementItem.objects.filter(
        statement=statement, loan_id=OuterRef("pk")
    ).values("pk")

    # # Get loans that are not in the statement items
    # loans = Loan.objects.unreleased().exclude(
    #     pk__in=Subquery(statement_item_subquery)
    # )
    # print(loans.count())
    # # Prepare StatementItem objects for bulk creation
    # statement_items = [
    #     StatementItem(
    #         statement=statement,
    #         loan=loan,
    #         descrepancy_found=True,
    #         descrepancy_note="Loan not found in verification session"
    #     )
    #     for loan in loans
    # ]

    # # Bulk create StatementItem objects
    # StatementItem.objects.bulk_create(statement_items)

    # Update statement completion time
    statement.completed = timezone.now()
    statement.save()
    messages.success(request, f"Verification Session {statement} Completed")
    return redirect(statement.get_absolute_url())


def statement_delete(request, pk):
    statement = get_object_or_404(Statement, pk=pk)
    statement.delete()
    messages.error(request, f"Verification Session {statement} Deleted")
    return redirect("girvi:statement_list")


def statement_item_add(request, pk):
    statement = get_object_or_404(Statement, pk=pk)
    if request.method == "POST":
        loan_id = request.POST.get("loan_id")
        try:
            loan = Loan.objects.get(loan_id=loan_id)
        except Loan.DoesNotExist:
            # Handle the error, e.g., log it, return a custom response, etc.
            loan = None

        if loan:
            if not loan.is_released:
                item = StatementItem.objects.create(statement=statement, loan=loan)
                messages.success(request, f"Added {loan} to {statement}")

            else:
                item = StatementItem.objects.create(
                    statement=statement,
                    loan=loan,
                    descrepancy_found=True,
                    descrepancy_note="Loan already released",
                )
                messages.error(request, f"Loan {loan_id} already released.")
                print(item)
            # Construct the HTML snippet using the item attributes
            item_html = f"""
            <li class="list-group-item d-flex justify-content-between align-items-center">
                {item.loan.loan_id} 
                {'(Discrepancy: ' + item.descrepancy_note + ')' if item.descrepancy_found else ''}
            </li>
            """
            return HttpResponse(item_html)
        else:
            item_html = f"""
            <li>
                {loan_id}
                Not found
            </li>
            """
            return HttpResponse(item_html)
    return HttpResponse("")


def statement_item_delete(request, pk):
    item = get_object_or_404(StatementItem, pk=pk)
    item.delete()
    messages.error(request, f"Item {item} Deleted")
    return HttpResponse("")
