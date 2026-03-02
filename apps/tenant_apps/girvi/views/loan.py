import decimal
import logging
from re import T

import pytz
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q, Sum
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods  # new
from django_tables2.config import RequestConfig
from django_tables2.export.export import TableExport
from moneyed import Money

# from django_fsm import has_transition_perm,can_proceed
# from django_fsm_log.models import StateLog
from apps.orgs.preferences import CompanyPreferences
from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.girvi.models.license import Series
from apps.tenant_apps.utils.htmx_utils import for_htmx, is_htmx, make_get_request

from ..filters import LoanFilter
from ..flows import LoanFlow
from ..forms import (
    ApproveLoanForm,
    CancelLoanForm,
    DeliverLoanForm,
    DisburseLoanForm,
    LoanForm,
    LoanItemForm,
    LoanRenewForm,
    MarkAuctionedLoanForm,
    MarkDefaultedLoanForm,
    MarkSoldLoanForm,
)
from ..models import (
    GivenLoan,
    JournalEntry,
    License,
    LoanChangeLog,
    LoanStatus,
    Release,
)
from apps.tenant_apps.dea.models import Voucher
from ..services import LoanIDGenerator
from ..tables import LoanTable

form_classes = {
    "approve": ApproveLoanForm,
    "disburse": DisburseLoanForm,
    "deliver": DeliverLoanForm,
    "cancel": CancelLoanForm,
    "mark_defaulted": MarkDefaultedLoanForm,
    "mark_auctioned": MarkAuctionedLoanForm,
    "mark_sold": MarkSoldLoanForm,
}
logger = logging.getLogger(__name__)


def _get_loan_journal_entries(loan):
    """
    Get all JournalEntries related to a GivenLoan through the proper relationship chain:
    GivenLoan -> PaymentVoucher -> Voucher -> JournalEntry
    """
    # Import PaymentVoucher model to get its ContentType
    from apps.tenant_apps.dea.models import PaymentVoucher

    # Get all payment vouchers for this loan
    payments = loan.payments.all()

    if not payments.exists():
        return JournalEntry.objects.none()

    # Get ContentType for PaymentVoucher
    payment_content_type = ContentType.objects.get_for_model(PaymentVoucher)
    payment_ids = list(payments.values_list("id", flat=True))

    # Get all vouchers for these payments
    vouchers = Voucher.objects.filter(
        doc_content_type=payment_content_type, doc_object_id__in=payment_ids
    )

    if not vouchers.exists():
        return JournalEntry.objects.none()

    # Get all journal entries for these vouchers
    return (
        JournalEntry.objects.filter(voucher__in=vouchers)
        .select_related("voucher", "posted_by")
        .order_by("-posted_at")
    )


def loan_transition_view(request, pk):
    loan = get_object_or_404(GivenLoan, pk=pk)
    transition_name = request.GET.get("transition") or request.POST.get("transition")
    form_class = form_classes.get(transition_name)

    if not form_class:
        messages.error(request, _("Invalid transition."))
        return redirect(loan.get_absolute_url())

    if request.method == "POST":
        form = form_class(request.POST, user=request.user)
        if form.is_valid():
            flow = LoanFlow(loan, request.user, request.tenant)
            transition_method = getattr(flow, transition_name, None)
            if transition_method and transition_method.can_proceed():
                transition_method(**form.cleaned_data)
                messages.success(request, _("Loan status updated successfully."))
            else:
                messages.error(
                    request,
                    _(
                        "You do not have permission to perform this action or the transition is not valid."
                    ),
                )
            return redirect(loan.get_absolute_url())
    else:
        form = form_class(user=request.user)

    return render(
        request,
        "girvi/loan/loan_transition_form.html",
        {
            "form": form,
            "loan": loan,
            "transition_name": transition_name,
        },
    )


def get_loan_history(loan):
    return loan.loanchangelog_set.all().select_related("author").order_by("-changed")


def loans_created_on_day_excluding_current_month(request):
    today = timezone.now()
    loans = GivenLoan.objects.filter(
        loan_date__day=today.day, release__isnull=True
    ).exclude(loan_date__month=today.month, loan_date__year=today.year)
    return render(request, "girvi/loan/loans_today.html", {"loans": loans})


def ld(request):
    # TODO get last date by series

    prefs = CompanyPreferences(request.user.profile.workspace)
    default_date = prefs.loan_default_date
    user_timezone = "Asia/Kolkata"
    user_tz = pytz.timezone(user_timezone)
    if default_date == "N":
        now = timezone.now()
        user_time = now.astimezone(user_tz)
        return user_time.strftime("%Y-%m-%dT%H:%M")
    else:
        last = GivenLoan.objects.order_by("-id").first()
        if not last:
            now = timezone.now()
            user_time = now.astimezone(user_tz)
            return user_time.strftime("%Y-%m-%dT%H:%M")
        loan_time = last.loan_date.astimezone(user_tz)
        return loan_time.strftime("%Y-%m-%dT%H:%M")


def get_interestrate(request):
    metal = request.GET["itemtype"]
    interest = 0
    prefs = CompanyPreferences(request.user.profile.workspace)
    if metal == "Gold":
        interest = prefs.interest_rate_gold
    elif metal == "Silver":
        interest = prefs.interest_rate_silver
    else:
        interest = prefs.interest_rate_other
    form = LoanItemForm(initial={"interestrate": interest})
    context = {
        "field": form["interestrate"],
    }
    return render(request, "girvi/partials/field.html", context)


# @login_required
# @for_htmx(use_block_from_params=True)
# def loan_list(request):
#     filter = LoanFilter(
#         request.GET,
#         request=request,
#         queryset=Loan.objects.order_by("-id")
#         .with_details(request.grate, request.srate, request.brate)
#         .select_related("customer", "release", "created_by")
#         .prefetch_related("notifications", "loanitems"),
#     )
#     table = LoanTable(filter.qs)

#     RequestConfig(request, paginate={"per_page": 10}).configure(table)
#     export_format = request.GET.get("_export", None)
#     if TableExport.is_valid_format(export_format):
#         # TODO speed up the table export using celery

#         exporter = TableExport(
#             export_format,
#             table,
#             exclude_columns=(
#                 "selection",
#                 "notified",
#                 "months_since_created",
#                 "current_value",
#                 "total_due",
#                 "total_interest",
#             ),
#             dataset_kwargs={"title": "loans"},
#         )
#         return exporter.response(f"table.{export_format}")
#     context = {
#         "filter": filter,
#         "table": table,
#         "export_formats": ["csv", "xls", "xlsx", "json", "html"],
#         "total_loan_amount": filter.qs.total_loanamount(),
#         "total_interest": filter.qs.aggregate(total=Sum("total_interest")),
#     }
#     return TemplateResponse(request, "girvi/loan/loan_list.html", context)


# @login_required
# @for_htmx(use_block_from_params=True)
# def loan_list(request: HttpRequest):
#     return _loan_list(request)


# def _loan_list(request: HttpRequest):
#     filter = LoanFilter(
#         request.GET,
#         request=request,
#         queryset=Loan.objects.order_by("-id")
#         .with_details(request.grate, request.srate, request.brate)
#         .select_related("customer", "release", "created_by")
#         .prefetch_related("notifications", "loanitems"),
#     )
#     table = LoanTable(filter.qs)

#     RequestConfig(request, paginate={"per_page": 10}).configure(table)
#     export_format = request.GET.get("_export", None)
#     if TableExport.is_valid_format(export_format):
#         # TODO speed up the table export using celery

#         exporter = TableExport(
#             export_format,
#             table,
#             exclude_columns=(
#                 "selection",
#                 "notified",
#                 "months_since_created",
#                 "current_value",
#                 "total_due",
#                 "total_interest",
#             ),
#             dataset_kwargs={"title": "loans"},
#         )
#         return exporter.response(f"table.{export_format}")

#     if request.method == "POST":
#         if is_htmx(request):
#             return _loan_list(make_get_request(request))

#     context = {
#         "filter": filter,
#         "table": table,
#         "export_formats": ["csv", "xls", "xlsx", "json", "html"],
#         "total_loan_amount": filter.qs.total_loanamount(),
#         "total_interest": filter.qs.aggregate(total=Sum("total_interest")),
#     }
#     return TemplateResponse(request, "girvi/loan/loan_list.html", context)


@login_required
def loan_list(request: HttpRequest):
    filter = LoanFilter(
        request.GET,
        request=request,
        queryset=GivenLoan.objects.order_by("-id")
        .select_related("borrower", "series", "created_by")
        .prefetch_related("notifications", "loanitems"),
    )
    context = {
        "filter": filter,
        "export_formats": ["csv", "xls", "xlsx", "json", "html"],
        "total_loan_amount": filter.qs.aggregate(total=Sum("loanitems__loanamount")),
        "total_interest": filter.qs.aggregate(total=Sum("loanitems__interest")),
    }
    if is_htmx(request):
        return TemplateResponse(
            request, "girvi/loan/loan_list.html#loan-content", context
        )
    return TemplateResponse(request, "girvi/loan/loan_list.html", context)


@login_required
def loan_table_partial(request: HttpRequest):
    filter = LoanFilter(
        request.GET,
        request=request,
        queryset=GivenLoan.objects.order_by("-id")
        .select_related("borrower", "series", "created_by")
        .prefetch_related("notifications", "loanitems"),
    )
    table = LoanTable(filter.qs)
    RequestConfig(request, paginate={"per_page": 10}).configure(table)
    context = {
        "table": table,
        "total_loan_amount": filter.qs.aggregate(total=Sum("loanitems__loanamount")),
        "total_interest": filter.qs.aggregate(total=Sum("loanitems__interest")),
        "filter": filter,
    }
    if is_htmx(request):
        return TemplateResponse(request, "girvi/loan/_loan_table.html", context)
    else:
        # If not HTMX, render the full loan list page
        context["filter"] = filter
        return TemplateResponse(request, "girvi/loan/loan_list.html", context)


# @login_required
# @for_htmx(use_block="content")
# def loan_save(request, id=None, pk=None):
#     obj = get_object_or_404(Loan, id=id) if id else None
#     form = LoanForm(request.POST or None, instance=obj)

#     if request.method == "POST":
#         if form.is_valid():
#             loan = form.save(commit=False)
#             loan.created_by = request.user
#             loan.save()
#             messages.success(
#                 request, f"{'Updated' if obj else 'Created'} Loan: {loan.loan_id}"
#             )
#             return loan_detail(make_get_request(request), loan.id)

#             # response = TemplateResponse(
#             #     request,
#             #     "girvi/loan/loan_detail.html",
#             #     {"loan": loan, "object": loan, "customer": loan.customer},
#             # )
#             # response["Hx-Push-Url"] = reverse(
#             #     "girvi:girvi_loan_detail", kwargs={"pk": loan.id}
#             # )
#             # return response

#             # response = TemplateResponse(
#             #     request,
#             #     "girvi/loan/loan_detail.html",
#             #     {"loan": loan, "object": loan, "customer": loan.customer},
#             # )
#             # response["HX-Redirect"] = reverse("girvi:girvi_loan_detail", kwargs={"pk": loan.id})
#             # return response

#         else:
#             messages.warning(request, "Please correct the error below.")
#             return TemplateResponse(
#                 request,
#                 "girvi/loan/loan_form.html",
#                 {"form": form, "loan": obj, "object": obj},
#             )

#     if not obj:
#         initial = {}

#         try:
#             latest_loan = Loan.objects.latest("id")
#             series = latest_loan.series.id
#         except Loan.DoesNotExist:
#             print("No loans exist yet.")
#             series = None
#         try:
#             loan_id = generate_loan_id(series_id=series)
#             initial["loan_id"] = loan_id
#             initial["loan_date"] = ld(request)
#             initial["series"] = series
#             # print(f"Generated loan ID: {loan_id}")
#         except License.DoesNotExist as e:
#             print(f"License does not exist: {e}")
#             messages.error(request, "No License objects in database.")
#             response = HttpResponse()
#             response["HX-Redirect"] = reverse("girvi:girvi_license_list")
#             return response
#             # Handle the case where no license exists, e.g., log the error, notify the user, etc.
#         except Exception as e:
#             print(f"Unexpected error: {e}")
#             messages.error(request, "Unexpected error: {e}")
#             response = HttpResponse()
#             response["HX-Redirect"] = reverse("girvi:girvi_license_list")
#             return response

#         if pk:
#             initial["customer"] = get_object_or_404(Customer, pk=pk)
#         form = LoanForm(initial=initial)

#     return TemplateResponse(
#         request, "girvi/loan/loan_form.html", {"form": form, "loan": obj, "object": obj}
#     )


@login_required
@for_htmx(use_block="content")
def loan_save(request, id=None, pk=None):
    """
    Create or update a loan instance.
    Args:
        id (int): Loan ID for updates
        pk (int): Customer ID for new loans
    """
    try:
        # Get existing loan or None for new loan
        loan = get_object_or_404(GivenLoan, id=id) if id else None

        if request.method == "POST":
            form = LoanForm(request.POST, instance=loan)
            if form.is_valid():
                with transaction.atomic():
                    loan = form.save(commit=False)
                    loan.created_by = request.user
                    loan.save()

                messages.success(
                    request, f"{'Updated' if id else 'Created'} Loan: {loan.loan_id}"
                )
                # return loan_detail(make_get_request(request), loan.id)
                # Redirect to detail page
                return HttpResponse(
                    headers={
                        "HX-Redirect": reverse(
                            "girvi:girvi_loan_detail", kwargs={"pk": loan.id}
                        )
                    }
                )

            messages.warning(request, "Please correct the errors below.")
            return TemplateResponse(
                request,
                "girvi/loan/loan_form.html",
                {"form": form, "loan": loan, "object": loan},
            )

        # Handle GET request for new loan
        if not loan:
            initial_data = _get_initial_loan_data(request, pk)
            if not initial_data:
                messages.error(
                    request,
                    "Could not initialize loan data. Please check series and license setup.",
                )
                return HttpResponse(
                    headers={"HX-Redirect": reverse("girvi:girvi_license_list")}
                )

            form = LoanForm(initial=initial_data)
        else:
            form = LoanForm(instance=loan)

        return TemplateResponse(
            request,
            "girvi/loan/loan_form.html",
            {"form": form, "loan": loan, "object": loan},
        )

    except Exception as e:
        logger.warn(f"Error in loan_save: {str(e)}")
        messages.error(request, f"An error occurred while saving loan")
        return HttpResponse(headers={"HX-Redirect": reverse("girvi:girvi_loan_list")})


def _get_initial_loan_data(request, customer_pk=None):
    """Helper function to get initial data for new loan form"""
    try:
        # Try to get initial series
        series = None
        loan_id = None

        try:
            # Try to get latest loan's series
            latest_loan = GivenLoan.objects.select_related("series").latest("id")
            series = latest_loan.series
        except GivenLoan.DoesNotExist:
            # If no loans exist, get default active series
            series = Series.objects.filter(is_active=True).first()

        if not series:
            logger.warning("No active series found for new loan")
            return None

        # Generate preview of next loan ID for display
        try:
            loan_id = LoanIDGenerator.generate(series)
        except Exception as e:
            logger.error(f"Error generating loan_id preview: {e}")
            loan_id = None

        initial = {"series": series, "loan_date": ld(request), "loan_id": loan_id}

        # Add customer if provided
        if customer_pk:
            initial["borrower"] = get_object_or_404(Customer, pk=customer_pk)

        return initial

    except Exception as e:
        logger.error(f"Error getting initial loan data: {str(e)}")
        return None


@require_http_methods(["DELETE"])
@login_required
def loan_delete(request, pk=None):
    obj = get_object_or_404(GivenLoan, id=pk)
    messages.error(request, f" Loan {obj} Deleted")
    obj.delete()
    return HttpResponse(
        status=204,
        headers={
            "Hx-Redirect": reverse("girvi:girvi_loan_list")
            # "hx-Trigger": "loanDeleted"
        },
    )


@login_required
@for_htmx(use_block="content")
def loan_detail(request, pk):
    loan = get_object_or_404(
        GivenLoan.objects.select_related(
            "borrower", "created_by", "series"
        ).prefetch_related("loanitems"),
        pk=pk,
    )

    # transitions = list(transition.name for transition in loan.get_all_status_transitions())
    # possible_transitions = loan.get_possible_transitions(user,request.tenant)
    flow = LoanFlow(loan, request.user, request.tenant)
    current_status = flow.status

    # Use ContentType to filter LoanChangeLog for this GivenLoan
    changelog = (
        LoanChangeLog.objects.filter(
            content_type=ContentType.objects.get_for_model(GivenLoan), object_id=loan.id
        )
        .order_by("changed")
        .values_list("source", flat=True)
    )

    transitions = flow.get_transitions()
    available_transitions = (
        [
            transition.label
            for transition in LoanFlow.status.get_available_transitions(
                flow, current_status, request.user
            )
        ],
    )
    possible_transitions = [
        transition.label for transition in flow.get_outgoing_transitions()
    ]
    # possible_transitions = [transition.label for method,transitions in LoanFlow.status.get_transitions().items() for transition in transitions]

    weight_summary = {item["itemtype"]: item for item in loan.get_weight_summary}
    gold_weight = (
        f"G:{weight_summary.get('Gold', {}).get('total_weight', 0)} gms"
        if weight_summary.get("Gold", {}).get("total_weight", 0) > 0
        else ""
    )
    silver_weight = (
        f"S:{weight_summary.get('Silver', {}).get('total_weight', 0)} gms"
        if weight_summary.get("Silver", {}).get("total_weight", 0) > 0
        else ""
    )
    bronze_weight = (
        f"B:{weight_summary.get('Bronze', {}).get('total_weight', 0)} gms"
        if weight_summary.get("Bronze", {}).get("total_weight", 0) > 0
        else ""
    )

    # Combine the weights, ensuring there are no extra spaces
    weight = " ".join(filter(None, [gold_weight, silver_weight, bronze_weight]))

    gold_pure = (
        f"G:{round(weight_summary.get('Gold', {}).get('pure_weight', 0), 3)} gms"
        if weight_summary.get("Gold", {}).get("pure_weight", 0) > 0
        else ""
    )
    silver_pure = (
        f"S:{round(weight_summary.get('Silver', {}).get('pure_weight', 0), 3)} gms"
        if weight_summary.get("Silver", {}).get("pure_weight", 0) > 0
        else ""
    )
    bronze_pure = (
        f"B:{round(weight_summary.get('Bronze', {}).get('pure_weight', 0), 3)} gms"
        if weight_summary.get("Bronze", {}).get("pure_weight", 0) > 0
        else ""
    )

    # Combine the weights, ensuring there are no extra spaces
    pure = " ".join(filter(None, [gold_pure, silver_pure, bronze_pure]))
    value = loan.current_value

    if value > 0 and loan.get_loan_amount is not None:
        lvratio = round(float(loan.get_loan_amount) / float(value) * 100, 2)
    else:
        lvratio = 0

    due = loan.total_due
    # due = loan.total_due
    dvratio = 0
    if due > 0 and value > 0:
        try:
            dvratio = round(due / value, 2) * 100
        except (decimal.DivisionUndefined, ZeroDivisionError):
            dvratio = 0
    get_storage_box = getattr(loan, "get_storage_box", None)
    location = get_storage_box() if get_storage_box else None
    if location:
        position = location.position_for_item(loan.id)
    else:
        position = None
    context = {
        "object": loan,
        "loan": loan,
        "customer": loan.borrower,
        "items": loan.loanitems.all(),
        "payments": getattr(loan, "loan_payments", []).all()
        if hasattr(loan, "loan_payments")
        else [],
        "value": Money(value, "INR"),
        "worth": value - due,
        "lvratio": lvratio,
        "dvratio": dvratio,
        "weight": weight,
        "pure": pure,
        "je": _get_loan_journal_entries(loan),
        "location": location,
        "position": position,
        "expires": (
            loan.calculate_months_to_exceed_value(value, due)
            if hasattr(loan, "calculate_months_to_exceed_value")
            else 0
        ),
        "possible_transitions": possible_transitions,
        "current_status": current_status,
        "available_transitions": available_transitions,
        "transitions": transitions,
        "change_log": changelog,
    }

    return TemplateResponse(request, "girvi/loan/loan_detail_1.html", context)


@login_required
@for_htmx(use_block="content")
def split_loan_items(request, pk):
    from ..services import LoanSplitService

    loan = get_object_or_404(GivenLoan, pk=pk)
    try:
        service = LoanSplitService(loan=loan, created_by=request.user)
        new_loans = service.split_items()
        messages.success(
            request, f"Successfully split loan into {len(new_loans)} new loans"
        )
        return loan_list(make_get_request(request))
    except ValidationError as e:
        messages.error(request, str(e))
        return redirect("girvi:girvi_loan_detail", pk=pk)


@login_required
@require_http_methods(["POST"])
def merge_loans(request):
    """Handle loan merge action"""
    from ..services import LoanMergeService

    loan_ids = request.POST.getlist("selection")
    if len(loan_ids) < 2:
        messages.error(request, "Please select at least 2 loans to merge")
        return redirect("girvi:loan_list")

    try:
        loans = GivenLoan.objects.filter(id__in=loan_ids)
        if loans.count() < 2:
            messages.error(request, "Please select at least 2 loans to merge")
            return HttpResponse(status=400)

        base_loan = loans.earliest("loan_date")
        borrowers = set(loans.values_list("borrower_id", flat=True))
        if len(borrowers) > 1:
            messages.error(request, "Selected loans must belong to the same borrower")
            return HttpResponse(status=400)

        if loans.filter(status=LoanStatus.RELEASED).exists():
            messages.error(request, "Cannot merge released loans")
            return HttpResponse(status=400)

        loans_to_merge = loans.exclude(id=base_loan.id)

        # Use service for merge
        service = LoanMergeService(target_loan=base_loan, merged_by=request.user)
        service.merge(source_loans=list(loans_to_merge))

        messages.success(request, f"Successfully merged {loans_to_merge.count()} loans")
        return HttpResponse(
            headers={
                "HX-Redirect": reverse(
                    "girvi:girvi_loan_detail", kwargs={"pk": base_loan.id}
                )
            }
        )

    except ValidationError as e:
        messages.error(request, str(e))
        return HttpResponse(status=400)

    except Exception as e:
        logger.error(f"Error in merge_loans: {str(e)}")
        messages.error(request, "An error occurred while merging loans")
        return HttpResponse(status=500)


@login_required
@for_htmx(use_block="content")
def loan_renew(request, pk):
    loan = get_object_or_404(GivenLoan, pk=pk)

    messages.error(request, "Loan renewal is not yet supported for refactored loans.")
    return redirect("girvi:girvi_loan_detail", pk=loan.pk)

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
    loans = GivenLoan.objects.filter(id__in=id_list)
    for i in loans:
        i.delete()
    messages.error(request, f"Deleted {len(id_list)} loans")
    return loan_list(request)
