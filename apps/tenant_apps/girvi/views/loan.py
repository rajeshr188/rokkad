import decimal
import logging

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

from ..filters import LoanFilter
from ..filters import TakenLoanFilter
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
    UndoDisburseLoanForm,
    UndoReleaseLoanForm,
)
from ..models import (
    GivenLoan,
    JournalEntry,
    License,
    LoanChangeLog,
    LoanStatus,
    Release,
    TakenLoan,
)
from apps.tenant_apps.dea.models import Voucher
from ..payment_service import record_loan_disbursal, reverse_loan_disbursal, reverse_loan_release
from ..services import LoanIDGenerator
from ..tables import LoanTable, TakenLoanTable, UnifiedLoanTable

form_classes = {
    "approve": ApproveLoanForm,
    "disburse": DisburseLoanForm,
    # "deliver" is intentionally absent: releasing a loan MUST go through the
    # Release create form (which runs the custody check and posts accounting).
    # flow.deliver() is fired internally by Release.save(), not as a standalone action.
    "cancel": CancelLoanForm,
    "mark_defaulted": MarkDefaultedLoanForm,
    "mark_auctioned": MarkAuctionedLoanForm,
    "mark_sold": MarkSoldLoanForm,
    "undo_disburse": UndoDisburseLoanForm,
    "undo_release": UndoReleaseLoanForm,
}
logger = logging.getLogger(__name__)


def _parse_selected_ids(raw_ids):
    """Return cleaned integer IDs and count of invalid tokens."""
    cleaned = []
    invalid_count = 0
    for raw_id in raw_ids:
        try:
            parsed = int(raw_id)
            if parsed > 0:
                cleaned.append(parsed)
            else:
                invalid_count += 1
        except (TypeError, ValueError):
            invalid_count += 1
    # Preserve order, remove duplicates
    cleaned = list(dict.fromkeys(cleaned))
    return cleaned, invalid_count


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
                if transition_name == "undo_disburse":
                    try:
                        with transaction.atomic():
                            transition_method(**form.cleaned_data)
                            reverse_loan_disbursal(loan, request.user)
                        messages.success(
                            request,
                            _("Disbursal reversed successfully. Loan returned to Approved."),
                        )
                    except (ValueError, ValidationError) as exc:
                        messages.error(request, str(exc))
                    return redirect(loan.get_absolute_url())

                elif transition_name == "undo_release":
                    try:
                        with transaction.atomic():
                            release = loan.release
                            transition_method(**form.cleaned_data)
                            reverse_loan_release(loan, request.user)
                            release.delete()
                        messages.success(
                            request,
                            _("Release reversed successfully. Loan returned to Disbursed."),
                        )
                    except (ValueError, ValidationError) as exc:
                        messages.error(request, str(exc))
                    return redirect(loan.get_absolute_url())

                transition_method(**form.cleaned_data)

                if transition_name == "disburse" and loan.status == LoanStatus.DISBURSED:
                    try:
                        payment, created = record_loan_disbursal(loan, request.user)
                        if created:
                            messages.success(
                                request,
                                _(
                                    f"Loan status updated successfully. Disbursal voucher {payment.payment_id} posted."
                                ),
                            )
                        else:
                            messages.success(
                                request,
                                _(
                                    f"Loan status updated successfully. Disbursal already recorded as {payment.payment_id}."
                                ),
                            )
                    except Exception as exc:
                        logger.exception(
                            "Disbursal posting failed for loan %s", loan.pk
                        )
                        messages.warning(
                            request,
                            _(
                                f"Loan status updated successfully, but disbursal posting failed: {exc}"
                            ),
                        )
                    return redirect(loan.get_absolute_url())

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


@login_required
def loan_list(request: HttpRequest):
    loan_kind = request.GET.get("loan_kind", "given")

    def get_given_qs():
        return (
            GivenLoan.objects.get_queryset()
            .for_table_display()
            .order_by("-id")
            .select_related("borrower", "series", "created_by")
            .prefetch_related("notifications", "loanitems")
        )

    def get_taken_qs():
        # TakenLoan does not have a release relation; avoid for_table_display()
        # because shared duration annotations reference release__release_date.
        return (
            TakenLoan.objects.get_queryset()
            .with_metal_weights()
            .with_itemwise_amounts()
            .with_current_value()
            .order_by("-id")
            .select_related("lender", "series", "created_by")
            .prefetch_related("repledgedloanitems")
        )

    if loan_kind == "taken":
        taken_qs = get_taken_qs()
        filter = TakenLoanFilter(request.GET, request=request, queryset=taken_qs)
    elif loan_kind == "all":
        filter = None
    else:
        loan_kind = "given"
        given_qs = get_given_qs()
        filter = LoanFilter(request.GET, request=request, queryset=given_qs)

    if loan_kind == "given":
        total_loan_amount = filter.qs.aggregate(total=Sum("loanitems__loanamount"))
        total_interest = filter.qs.aggregate(total=Sum("loanitems__interest"))
    elif loan_kind == "taken":
        total_loan_amount = filter.qs.aggregate(
            total=Sum("repledgedloanitems__repledged_loanamount")
        )
        total_interest = filter.qs.aggregate(total=Sum("repledgedloanitems__interest"))
    else:
        given_qs = get_given_qs()
        taken_qs = get_taken_qs()
        given_total = given_qs.aggregate(total=Sum("loanitems__loanamount"))["total"] or 0
        taken_total = taken_qs.aggregate(total=Sum("repledgedloanitems__repledged_loanamount"))["total"] or 0
        given_interest = given_qs.aggregate(total=Sum("loanitems__interest"))["total"] or 0
        taken_interest = taken_qs.aggregate(total=Sum("repledgedloanitems__interest"))["total"] or 0
        total_loan_amount = {"total": given_total + taken_total}
        total_interest = {"total": given_interest + taken_interest}

    context = {
        "filter": filter,
        "loan_kind": loan_kind,
        "export_formats": ["csv", "xls", "xlsx", "json", "html"],
        "total_loan_amount": total_loan_amount,
        "total_interest": total_interest,
    }
    if request.htmx:
        return render(request, "girvi/loan/loan_list.html#loan-content", context)
    return render(request, "girvi/loan/loan_list.html", context)


@login_required
def loan_table_partial(request: HttpRequest):
    loan_kind = request.GET.get("loan_kind", "given")

    def get_given_qs():
        return (
            GivenLoan.objects.get_queryset()
            .for_table_display()
            .order_by("-id")
            .select_related("borrower", "series", "created_by")
            .prefetch_related("notifications", "loanitems")
        )

    def get_taken_qs():
        # TakenLoan does not have a release relation; avoid for_table_display()
        # because shared duration annotations reference release__release_date.
        return (
            TakenLoan.objects.get_queryset()
            .with_metal_weights()
            .with_itemwise_amounts()
            .with_current_value()
            .order_by("-id")
            .select_related("lender", "series", "created_by")
            .prefetch_related("repledgedloanitems")
        )

    if loan_kind == "taken":
        taken_qs = get_taken_qs()
        filter = TakenLoanFilter(request.GET, request=request, queryset=taken_qs)
        table = TakenLoanTable(filter.qs)
        total_loan_amount = filter.qs.aggregate(
            total=Sum("repledgedloanitems__repledged_loanamount")
        )
        total_interest = filter.qs.aggregate(total=Sum("repledgedloanitems__interest"))
    elif loan_kind == "all":
        given_qs = get_given_qs()
        taken_qs = get_taken_qs()
        query = request.GET.get("query", "").strip()
        status = request.GET.get("status", "All")
        if query:
            given_qs = given_qs.filter(
                Q(id__icontains=query)
                | Q(loan_id__icontains=query)
                | Q(borrower__firstname__icontains=query)
                | Q(borrower__lastname__icontains=query)
            )
            taken_qs = taken_qs.filter(
                Q(id__icontains=query)
                | Q(loan_id__icontains=query)
                | Q(lender__firstname__icontains=query)
                | Q(lender__lastname__icontains=query)
            )
        if status == "Released":
            given_qs = given_qs.filter(release__isnull=False)
            taken_qs = taken_qs.filter(status=LoanStatus.RELEASED)
        elif status == "UnReleased":
            given_qs = given_qs.filter(release__isnull=True)
            taken_qs = taken_qs.exclude(status=LoanStatus.RELEASED)

        all_rows = [
            {
                "id": row.id,
                "loan_type": "Given",
                "loan_id": row.loan_id,
                "loan_date": row.loan_date,
                "party": row.borrower.name,
                "status": row.status,
                "loan_amount": row.get_loan_amount,
            }
            for row in given_qs
        ] + [
            {
                "id": row.id,
                "loan_type": "Taken",
                "loan_id": row.loan_id,
                "loan_date": row.loan_date,
                "party": row.lender.name,
                "status": row.status,
                "loan_amount": row.get_loan_amount,
            }
            for row in taken_qs
        ]
        all_rows.sort(key=lambda row: row["loan_date"], reverse=True)

        filter = None
        table = UnifiedLoanTable(all_rows)
        total_loan_amount = {
            "total": (given_qs.aggregate(total=Sum("loanitems__loanamount"))["total"] or 0)
            + (
                taken_qs.aggregate(total=Sum("repledgedloanitems__repledged_loanamount"))["total"]
                or 0
            )
        }
        total_interest = {
            "total": (given_qs.aggregate(total=Sum("loanitems__interest"))["total"] or 0)
            + (taken_qs.aggregate(total=Sum("repledgedloanitems__interest"))["total"] or 0)
        }
    else:
        loan_kind = "given"
        given_qs = get_given_qs()
        filter = LoanFilter(request.GET, request=request, queryset=given_qs)
        table = LoanTable(filter.qs)
        total_loan_amount = filter.qs.aggregate(total=Sum("loanitems__loanamount"))
        total_interest = filter.qs.aggregate(total=Sum("loanitems__interest"))

    RequestConfig(request, paginate={"per_page": 10}).configure(table)
    context = {
        "table": table,
        "loan_kind": loan_kind,
        "total_loan_amount": total_loan_amount,
        "total_interest": total_interest,
        "filter": filter,
    }
    if request.htmx:
        return render(request, "girvi/loan/loan_list.html#loan-table", context)
    return render(request, "girvi/loan/loan_list.html", context)


@login_required
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
        logger.warning(f"Error in loan_save: {str(e)}")
        messages.error(request, f"An error occurred while saving loan")
        return HttpResponse(headers={"HX-Redirect": reverse("girvi:girvi_loan_list")})


@login_required
def loan_create(request):
    """Create loan endpoint wrapper for unambiguous route semantics."""
    return loan_save(request)


@login_required
def loan_create_for_customer(request, customer_pk):
    """Create loan endpoint wrapper with borrower preselection."""
    return loan_save(request, pk=customer_pk)


@login_required
def loan_update(request, pk):
    """Update loan endpoint wrapper for unambiguous route semantics."""
    return loan_save(request, id=pk)


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
def loan_detail(request, pk):
    loan = get_object_or_404(
        GivenLoan.objects.select_related(
            "borrower", "created_by", "series"
        ).prefetch_related("loanitems"),
        pk=pk,
    )

    flow = LoanFlow(loan, request.user, request.tenant)
    current_status = flow.status

    # Full changelog objects for timeline display
    changelog = (
        LoanChangeLog.objects.filter(
            content_type=ContentType.objects.get_for_model(GivenLoan), object_id=loan.id
        )
        .select_related("author")
        .order_by("changed")
    )

    possible_transitions = [
        transition.label for transition in flow.get_outgoing_transitions()
    ]

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
        "value": Money(value, "INR"),
        "worth": value - due,
        "lvratio": lvratio,
        "dvratio": dvratio,
        "weight": weight,
        "pure": pure,
        "location": location,
        "position": position,
        "expires": (
            loan.calculate_months_to_exceed_value(value, due)
            if hasattr(loan, "calculate_months_to_exceed_value")
            else 0
        ),
        "possible_transitions": possible_transitions,
        "current_status": current_status,
        "change_log": changelog,
    }

    if request.htmx:
        return render(request, "girvi/loan/loan_detail_1.html#loan-detail", context)
    return render(request, "girvi/loan/loan_detail_1.html", context)


@login_required
def split_loan_items(request, pk):
    from ..services import LoanSplitService

    loan = get_object_or_404(GivenLoan, pk=pk)
    try:
        service = LoanSplitService(loan=loan, created_by=request.user)
        new_loans = service.split_items()
        messages.success(
            request, f"Successfully split loan into {len(new_loans)} new loans"
        )
        return HttpResponse(headers={"HX-Redirect": reverse("girvi:girvi_loan_list")})
    except ValidationError as e:
        messages.error(request, str(e))
        return redirect("girvi:girvi_loan_detail", pk=pk)


@login_required
@require_http_methods(["POST"])
def merge_loans(request):
    """Handle loan merge action"""
    from ..services import LoanMergeService

    loan_kind = request.POST.get("loan_kind", "given")
    if loan_kind != "given":
        messages.error(request, "Merge is available only for Given loans")
        return HttpResponse(status=400)

    raw_loan_ids = request.POST.getlist("selection")
    loan_ids, invalid_count = _parse_selected_ids(raw_loan_ids)
    if invalid_count:
        logger.warning("merge_loans rejected invalid IDs: %s", raw_loan_ids)
        messages.error(request, "Invalid loan selection.")
        return HttpResponse(status=400, content="Invalid loan selection.")

    if len(loan_ids) < 2:
        messages.error(request, "Please select at least 2 loans to merge")
        return HttpResponse(status=400, content="Please select at least 2 loans to merge")

    try:
        loans = GivenLoan.objects.filter(id__in=loan_ids)
        if loans.count() != len(loan_ids):
            messages.error(request, "Some selected loans no longer exist")
            return HttpResponse(status=400, content="Some selected loans no longer exist")

        if loans.count() < 2:
            messages.error(request, "Please select at least 2 loans to merge")
            return HttpResponse(status=400, content="Please select at least 2 loans to merge")

        base_loan = loans.earliest("loan_date")
        borrowers = set(loans.values_list("borrower_id", flat=True))
        if len(borrowers) > 1:
            messages.error(request, "Selected loans must belong to the same borrower")
            return HttpResponse(status=400, content="Selected loans must belong to the same borrower")

        if loans.filter(Q(release__isnull=False) | Q(status=LoanStatus.RELEASED)).exists():
            messages.error(request, "Cannot merge released loans")
            return HttpResponse(status=400, content="Cannot merge released loans")

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
        return HttpResponse(status=400, content=str(e))

    except Exception as e:
        logger.error(f"Error in merge_loans: {str(e)}")
        messages.error(request, "An error occurred while merging loans")
        return HttpResponse(status=500, content="An error occurred while merging loans")


@login_required
def loan_renew(request, pk):
    loan = get_object_or_404(GivenLoan, pk=pk)

    messages.error(request, "Loan renewal is not yet supported for refactored loans.")
    return redirect("girvi:girvi_loan_detail", pk=loan.pk)


@require_http_methods("POST")
@login_required
def deleteLoan(request):
    loan_kind = request.POST.get("loan_kind", "given")
    raw_ids = request.POST.getlist("selection")
    id_list, invalid_count = _parse_selected_ids(raw_ids)

    if invalid_count:
        logger.warning("deleteLoan rejected invalid IDs: %s", raw_ids)
        messages.error(request, "Invalid loan selection.")
        return HttpResponse(status=400, content="Invalid loan selection.")

    if not id_list:
        messages.error(request, "Please select at least one loan to delete.")
        return HttpResponse(status=400, content="Please select at least one loan to delete.")

    if loan_kind == "taken":
        loans = TakenLoan.objects.filter(id__in=id_list)
        if loans.count() != len(id_list):
            messages.error(request, "Some selected taken loans no longer exist")
            return HttpResponse(status=400, content="Some selected taken loans no longer exist")
        if loans.filter(status=LoanStatus.RELEASED).exists():
            messages.error(request, "Cannot bulk delete released taken loans")
            return HttpResponse(status=400, content="Cannot bulk delete released taken loans")
    elif loan_kind == "all":
        messages.error(request, "Delete from All tab is disabled. Use Given or Taken tab.")
        return HttpResponse(status=400, content="Delete from All tab is disabled. Use Given or Taken tab.")
    else:
        loans = GivenLoan.objects.filter(id__in=id_list)
        if loans.count() != len(id_list):
            messages.error(request, "Some selected given loans no longer exist")
            return HttpResponse(status=400, content="Some selected given loans no longer exist")
        if loans.filter(release__isnull=False).exists():
            messages.error(request, "Cannot bulk delete released given loans")
            return HttpResponse(status=400, content="Cannot bulk delete released given loans")

    deleted_count = loans.count()
    loans.delete()
    messages.success(request, f"Deleted {deleted_count} loans")
    return HttpResponse(
        headers={
            "HX-Redirect": f"{reverse('girvi:girvi_loan_list')}?loan_kind={loan_kind}"
        }
    )


# ---------------------------------------------------------------------------
# Loan detail tab endpoints (lazy-loaded via HTMX)
# ---------------------------------------------------------------------------


@login_required
@require_http_methods(["GET"])
def loan_detail_items_tab(request, pk):
    loan = get_object_or_404(GivenLoan.objects.prefetch_related("loanitems"), pk=pk)
    return render(
        request,
        "girvi/loan/loan_detail_1.html#items-tab",
        {"loan": loan, "items": loan.loanitems.all()},
    )


@login_required
@require_http_methods(["GET"])
def loan_detail_payments_tab(request, pk):
    loan = get_object_or_404(GivenLoan, pk=pk)
    payments = loan.payments.order_by("-payment_date")
    return render(
        request,
        "girvi/loan/loan_detail_1.html#payments-tab",
        {"loan": loan, "payments": payments},
    )


@login_required
@require_http_methods(["GET"])
def loan_detail_transactions_tab(request, pk):
    loan = get_object_or_404(GivenLoan, pk=pk)
    return render(
        request,
        "girvi/loan/loan_detail_1.html#transactions-tab",
        {"loan": loan, "je": _get_loan_journal_entries(loan)},
    )


@login_required
@require_http_methods(["GET"])
def loan_detail_statement_tab(request, pk):
    loan = get_object_or_404(GivenLoan, pk=pk)
    return render(request, "girvi/loan/loan_detail_1.html#statement-tab", {"loan": loan})


@login_required
@require_http_methods(["GET"])
def loan_detail_notices_tab(request, pk):
    loan = get_object_or_404(
        GivenLoan.objects.prefetch_related("notifications"), pk=pk
    )
    return render(
        request,
        "girvi/loan/loan_detail_1.html#notices-tab",
        {"loan": loan, "notifications": loan.notifications.all()},
    )


@login_required
@require_http_methods(["GET"])
def loan_detail_release_tab(request, pk):
    loan = get_object_or_404(GivenLoan, pk=pk)
    return render(request, "girvi/loan/loan_detail_1.html#release-tab", {"loan": loan})
