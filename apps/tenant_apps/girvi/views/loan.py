import decimal
import logging
from datetime import datetime

import pytz
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods  # new
from django_tables2.config import RequestConfig
from moneyed import Money

# from django_fsm import has_transition_perm,can_proceed
# from django_fsm_log.models import StateLog
from apps.orgs.preferences import CompanyPreferences
from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.girvi.models.license import Series

from ..filters import LoanFilter
from ..filters import TakenLoanFilter
from ..flows import build_runtime_loan_flow, resolve_runtime_transition_name
from ..forms import (
    LoanForm,
    LoanItemForm,
    LoanRenewForm,
    build_initial_loan_item_formset,
)
from ..models import (
    GivenLoan,
    LoanChangeLog,
    LoanStatus,
    TakenLoan,
)
from ..selectors import (
    build_unified_loan_rows,
    get_given_loan_detail_read_model,
    filter_unified_loans,
    get_loan_totals,
    given_loan_base_qs,
    taken_loan_base_qs,
)
from ..services import (
    LoanCreateCommand,
    LoanCreationService,
    LoanItemCreateInput,
    LoanRenewalCommand,
    LoanRenewalService,
    LoanTransitionService,
)
from ..tables import LoanTable, TakenLoanTable, UnifiedLoanTable
from ..transition_registry import (
    build_transition_actions,
    get_transition_form_class,
    get_transition_form_ui,
    normalize_transition_name,
)
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


def loan_transition_view(request, pk):
    loan = get_object_or_404(GivenLoan, pk=pk)
    raw_transition_name = request.GET.get("transition") or request.POST.get("transition")
    transition_name = normalize_transition_name(raw_transition_name)
    transition_name = resolve_runtime_transition_name(loan, transition_name)
    form_class = get_transition_form_class(transition_name)
    transition_ui = get_transition_form_ui(transition_name)

    if not form_class:
        messages.error(request, _("Invalid transition."))
        return redirect(loan.get_absolute_url())

    if request.method == "POST":
        form = form_class(request.POST, user=request.user)
        if form.is_valid():
            result = LoanTransitionService(loan, request.user, request.tenant).execute(
                transition_name, **form.cleaned_data
            )
            getattr(messages, result.level)(request, result.message)
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
            "transition_ui": transition_ui,
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
    metal = request.GET.get("itemtype")
    field_prefix = ""

    if metal is None:
        for key, value in request.GET.items():
            if key.endswith("-itemtype"):
                metal = value
                field_prefix = key[: -len("-itemtype")]
                break

    interest = 0
    prefs = CompanyPreferences(request.user.profile.workspace)
    if metal == "Gold":
        interest = prefs.interest_rate_gold
    elif metal == "Silver":
        interest = prefs.interest_rate_silver
    else:
        interest = prefs.interest_rate_other

    form = LoanItemForm(prefix=field_prefix or None, initial={"interestrate": interest})
    context = {
        "field": form["interestrate"],
    }
    return render(request, "girvi/partials/field.html", context)


@login_required
def loan_list(request: HttpRequest):
    loan_kind = request.GET.get("loan_kind", "given")

    if loan_kind == "taken":
        f = TakenLoanFilter(request.GET, request=request, queryset=taken_loan_base_qs())
        totals = get_loan_totals(taken_qs=f.qs)
    elif loan_kind == "all":
        f = None
        totals = get_loan_totals(
            given_qs=given_loan_base_qs(), taken_qs=taken_loan_base_qs()
        )
    else:
        loan_kind = "given"
        f = LoanFilter(request.GET, request=request, queryset=given_loan_base_qs())
        totals = get_loan_totals(given_qs=f.qs)

    context = {
        "filter": f,
        "loan_kind": loan_kind,
        "export_formats": ["csv", "xls", "xlsx", "json", "html"],
        **totals,
    }
    if request.htmx:
        return render(request, "girvi/loan/loan_list.html#loan-content", context)
    return render(request, "girvi/loan/loan_list.html", context)


@login_required
def loan_table_partial(request: HttpRequest):
    loan_kind = request.GET.get("loan_kind", "given")

    if loan_kind == "taken":
        f = TakenLoanFilter(request.GET, request=request, queryset=taken_loan_base_qs())
        table = TakenLoanTable(f.qs)
        totals = get_loan_totals(taken_qs=f.qs)
    elif loan_kind == "all":
        query = request.GET.get("query", "").strip()
        status = request.GET.get("status", "All")
        given_qs, taken_qs = filter_unified_loans(
            given_loan_base_qs(), taken_loan_base_qs(), query=query, status=status
        )
        f = None
        table = UnifiedLoanTable(build_unified_loan_rows(given_qs, taken_qs))
        totals = get_loan_totals(given_qs=given_qs, taken_qs=taken_qs)
    else:
        loan_kind = "given"
        f = LoanFilter(request.GET, request=request, queryset=given_loan_base_qs())
        table = LoanTable(f.qs)
        totals = get_loan_totals(given_qs=f.qs)

    RequestConfig(request, paginate={"per_page": 10}).configure(table)
    context = {
        "table": table,
        "loan_kind": loan_kind,
        "filter": f,
        **totals,
    }
    if request.htmx:
        return render(request, "girvi/loan/loan_list.html#loan-table", context)
    return render(request, "girvi/loan/loan_list.html", context)


def _extract_initial_item_inputs(item_formset):
    initial_items = []
    for item_data in getattr(item_formset, "cleaned_data", []) if item_formset else []:
        if not item_data or item_data.get("DELETE"):
            continue
        if not any(
            item_data.get(field) not in (None, "")
            for field in ("item", "itemdesc", "weight", "loanamount")
        ):
            continue
        initial_items.append(
            LoanItemCreateInput(
                item=item_data.get("item"),
                itemdesc=item_data.get("itemdesc") or "",
                itemtype=item_data.get("itemtype") or "Gold",
                quantity=item_data.get("quantity") or 1,
                weight=item_data.get("weight"),
                purity=item_data.get("purity"),
                loanamount=item_data.get("loanamount"),
                interestrate=item_data.get("interestrate"),
            )
        )
    return initial_items


def _build_loan_create_command(form, user, item_formset=None):
    return LoanCreateCommand(
        borrower=form.cleaned_data["borrower"],
        series=form.cleaned_data["series"],
        loan_date=form.cleaned_data["loan_date"],
        tenure=form.cleaned_data["tenure"],
        interest_type=form.cleaned_data["interest_type"],
        created_by=user,
        loan_id=form.cleaned_data.get("loan_id") or "",
        initial_items=_extract_initial_item_inputs(item_formset),
    )


def _parse_preview_loan_date(raw_value):
    if not raw_value:
        return timezone.now()
    if isinstance(raw_value, datetime):
        return raw_value

    for fmt in ("%Y-%m-%dT%H:%M", "%d-%m-%Y %H:%M"):
        try:
            return datetime.strptime(str(raw_value), fmt)
        except (TypeError, ValueError):
            continue

    return raw_value


def _build_preview_initial_item_inputs(data):
    initial_items = []

    try:
        total_forms = int(data.get("items-TOTAL_FORMS") or 0)
    except (TypeError, ValueError):
        total_forms = 0

    for index in range(total_forms):
        item_data = {
            "itemdesc": data.get(f"items-{index}-itemdesc") or "",
            "itemtype": data.get(f"items-{index}-itemtype") or "Gold",
            "quantity": data.get(f"items-{index}-quantity") or 1,
            "weight": data.get(f"items-{index}-weight"),
            "purity": data.get(f"items-{index}-purity"),
            "loanamount": data.get(f"items-{index}-loanamount"),
            "interestrate": data.get(f"items-{index}-interestrate"),
        }
        if any(
            item_data.get(field) not in (None, "")
            for field in ("itemdesc", "weight", "loanamount")
        ):
            initial_items.append(LoanItemCreateInput(**item_data))

    return initial_items


def _build_create_preview_from_data(data, user):
    borrower = None
    series = None

    borrower_id = data.get("borrower")
    if borrower_id:
        try:
            borrower = Customer.objects.select_related("account").filter(pk=int(borrower_id)).first()
        except (TypeError, ValueError):
            borrower = None

    series_id = data.get("series")
    if series_id:
        try:
            series = Series.objects.filter(pk=int(series_id)).first()
        except (TypeError, ValueError):
            series = None

    try:
        tenure = int(data.get("tenure") or 3)
    except (TypeError, ValueError):
        tenure = 3

    interest_type = (
        data.get("interest_type")
        or GivenLoan._meta.get_field("interest_type").default
    )

    return LoanCreationService.preview(
        LoanCreateCommand(
            borrower=borrower,
            series=series,
            loan_date=_parse_preview_loan_date(data.get("loan_date")),
            tenure=tenure,
            interest_type=interest_type,
            created_by=user,
            loan_id="",
            initial_items=_build_preview_initial_item_inputs(data),
        )
    )


def _loan_detail_redirect_response(loan_id):
    return HttpResponse(
        headers={
            "HX-Redirect": reverse("girvi:girvi_loan_detail", kwargs={"pk": loan_id})
        }
    )


def _render_loan_form_response(
    request, *, loan=None, customer_pk=None, form=None, item_formset=None
):
    creation_preview = None
    item_formset_class = build_initial_loan_item_formset()

    if form is None:
        if loan is None:
            initial_data = _get_initial_loan_data(request, customer_pk)
            if not initial_data:
                messages.error(
                    request,
                    "Could not initialize loan data. Please check series and license setup.",
                )
                return HttpResponse(
                    headers={"HX-Redirect": reverse("girvi:girvi_license_list")}
                )
            form = LoanForm(initial=initial_data)
            item_formset = item_formset or item_formset_class(prefix="items")
            creation_preview = initial_data.get("creation_preview")
        else:
            form = LoanForm(instance=loan)
    elif loan is None and form.is_bound:
        item_formset = item_formset or item_formset_class(request.POST or None, prefix="items")
        preview_fields = {"borrower", "series", "loan_date", "tenure", "interest_type"}
        if preview_fields.issubset(form.cleaned_data.keys()):
            creation_preview = LoanCreationService.preview(
                _build_loan_create_command(form, request.user, item_formset)
            )

    return TemplateResponse(
        request,
        "girvi/loan/loan_form.html",
        {
            "form": form,
            "loan": loan,
            "object": loan,
            "creation_preview": creation_preview,
            "item_formset": item_formset if loan is None else None,
        },
    )


def _handle_loan_create_post(request):
    item_formset_class = build_initial_loan_item_formset()
    form = LoanForm(request.POST)
    item_formset = item_formset_class(request.POST, prefix="items")

    form_is_valid = form.is_valid()
    formset_is_valid = item_formset.is_valid()

    if form_is_valid and formset_is_valid:
        result = LoanCreationService.execute(
            _build_loan_create_command(form, request.user, item_formset)
        )
        if result.success:
            messages.success(request, result.message)
            return _loan_detail_redirect_response(result.loan.id)

        form.add_error(None, result.message)

    messages.warning(request, "Please correct the errors below.")
    return _render_loan_form_response(request, form=form, item_formset=item_formset)


def _handle_loan_update_post(request, loan):
    form = LoanForm(request.POST, instance=loan)
    if form.is_valid():
        with transaction.atomic():
            loan = form.save(commit=False)
            if not loan.created_by:
                loan.created_by = request.user
            loan.save()

        messages.success(request, f"Updated Loan: {loan.loan_id}")
        return _loan_detail_redirect_response(loan.id)

    messages.warning(request, "Please correct the errors below.")
    return _render_loan_form_response(request, loan=loan, form=form)


@login_required
def loan_save(request, id=None, pk=None):
    """Backward-compatible dispatcher. Prefer `loan_create` / `loan_update`."""
    if id is not None:
        return loan_update(request, pk=id)
    if pk is not None:
        return loan_create_for_customer(request, customer_pk=pk)
    return loan_create(request)


@login_required
@require_http_methods(["GET"])
def loan_create_preview(request):
    preview = _build_create_preview_from_data(request.GET, request.user)
    return render(
        request,
        "girvi/loan/_creation_preview.html",
        {"creation_preview": preview, "loan": None},
    )


@login_required
def loan_create(request):
    """Dedicated create endpoint using LoanCreationService for POST writes."""
    try:
        if request.method == "POST":
            return _handle_loan_create_post(request)
        return _render_loan_form_response(request)
    except Exception as e:
        logger.warning(f"Error in loan_create: {str(e)}")
        messages.error(request, "An error occurred while creating loan")
        return HttpResponse(headers={"HX-Redirect": reverse("girvi:girvi_loan_list")})


@login_required
def loan_create_for_customer(request, customer_pk):
    """Dedicated create endpoint with borrower preselection."""
    try:
        if request.method == "POST":
            return _handle_loan_create_post(request)
        return _render_loan_form_response(request, customer_pk=customer_pk)
    except Exception as e:
        logger.warning(f"Error in loan_create_for_customer: {str(e)}")
        messages.error(request, "An error occurred while creating loan")
        return HttpResponse(headers={"HX-Redirect": reverse("girvi:girvi_loan_list")})


@login_required
def loan_update(request, pk):
    """Dedicated update endpoint for existing loans."""
    try:
        loan = get_object_or_404(GivenLoan, id=pk)
        if request.method == "POST":
            return _handle_loan_update_post(request, loan)
        return _render_loan_form_response(request, loan=loan)
    except Exception as e:
        logger.warning(f"Error in loan_update: {str(e)}")
        messages.error(request, "An error occurred while saving loan")
        return HttpResponse(headers={"HX-Redirect": reverse("girvi:girvi_loan_list")})


def _get_initial_loan_data(request, customer_pk=None):
    """Helper function to get initial data for new loan form"""
    try:
        # Try to get initial series
        series = None

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

        borrower = (
            get_object_or_404(Customer.objects.select_related("account"), pk=customer_pk)
            if customer_pk
            else None
        )
        preview_command = LoanCreateCommand(
            borrower=borrower,
            series=series,
            loan_date=timezone.now(),
            tenure=3,
            interest_type=GivenLoan._meta.get_field("interest_type").default,
            created_by=request.user,
            loan_id="",
        )
        creation_preview = LoanCreationService.preview(preview_command)

        initial = {
            "series": series,
            "loan_date": ld(request),
            "loan_id": creation_preview.expected_loan_id or None,
            "creation_preview": creation_preview,
        }

        # Add customer if provided
        if borrower:
            initial["borrower"] = borrower

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
        ).prefetch_related(
            "loanitems",
            "renewals_as_source__renewed_loan",
            "renewal_record__source_loan",
        ),
        pk=pk,
    )

    flow = build_runtime_loan_flow(loan, request.user, request.tenant)
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
    transition_actions = build_transition_actions(loan, possible_transitions)

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

    interest_reporting = {
        "gross_accrued": getattr(loan, "gross_accrued_interest", decimal.Decimal("0.00")),
        "paid": loan.interest_paid_total()
        if hasattr(loan, "interest_paid_total")
        else decimal.Decimal("0.00"),
        "outstanding": getattr(loan, "outstanding_interest", decimal.Decimal("0.00")),
        "receivable_balance": loan.interest_receivable_balance()
        if hasattr(loan, "interest_receivable_balance")
        else decimal.Decimal("0.00"),
        "last_accrual_date": getattr(loan, "last_accrual_date", None),
    }

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
        "transition_actions": transition_actions,
        "current_status": current_status,
        "change_log": changelog,
        "renewals_as_source": list(loan.renewals_as_source.all()),
        "origin_renewal": loan.renewal_record.first(),
        "interest_reporting": interest_reporting,
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

    if request.method == "POST":
        form = LoanRenewForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            command = LoanRenewalCommand(
                source_loan_id=loan.pk,
                renewal_date=cd["renewal_date"],
                mode=cd["mode"],
                interest_paid=cd["interest_paid"],
                principal_paid=cd["principal_paid"],
                requested_extra_amount=cd.get("requested_extra_amount") or 0,
                created_by=request.user,
                payment_method=cd["payment_method"],
                reference_number=cd.get("reference_number", ""),
                notes=cd.get("notes", ""),
            )
            result = LoanRenewalService().execute(command)
            if result.success:
                for warn in result.warnings:
                    messages.warning(request, warn)
                messages.success(request, result.message)
                return redirect("girvi:girvi_loan_detail", pk=result.new_loan_id)
            else:
                messages.error(request, result.message)
    else:
        form = LoanRenewForm(
            initial={"renewal_date": timezone.now().strftime("%Y-%m-%dT%H:%M")}
        )
        # Build preview from defaults so template can show current financials
        preview = LoanRenewalService().preview(
            LoanRenewalCommand(
                source_loan_id=loan.pk,
                renewal_date=timezone.now(),
                mode="PAY_AND_RENEW",
                created_by=request.user,
            )
        )

    return render(
        request,
        "girvi/loan/loan_renew.html",
        {
            "loan": loan,
            "form": form,
            "preview": preview if request.method == "GET" else None,
        },
    )


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
    rm = get_given_loan_detail_read_model(pk)
    return render(
        request,
        "girvi/loan/loan_detail_1.html#items-tab",
        {"loan": rm["loan"], "items": rm["items"], "summary": rm["summary"]},
    )


@login_required
@require_http_methods(["GET"])
def loan_detail_payments_tab(request, pk):
    rm = get_given_loan_detail_read_model(pk)
    return render(
        request,
        "girvi/loan/loan_detail_1.html#payments-tab",
        {
            "loan": rm["loan"],
            "payments": rm["payments"],
            "summary": rm["summary"],
        },
    )


@login_required
@require_http_methods(["GET"])
def loan_detail_transactions_tab(request, pk):
    rm = get_given_loan_detail_read_model(pk)
    return render(
        request,
        "girvi/loan/loan_detail_1.html#transactions-tab",
        {
            "loan": rm["loan"],
            "je": rm["journal_entries"],
            "summary": rm["summary"],
        },
    )


@login_required
@require_http_methods(["GET"])
def loan_detail_statement_tab(request, pk):
    rm = get_given_loan_detail_read_model(pk)
    return render(
        request,
        "girvi/loan/loan_detail_1.html#statement-tab",
        {
            "loan": rm["loan"],
            "statement_items": rm["statement_items"],
            "summary": rm["summary"],
        },
    )


@login_required
@require_http_methods(["GET"])
def loan_detail_notices_tab(request, pk):
    rm = get_given_loan_detail_read_model(pk)
    return render(
        request,
        "girvi/loan/loan_detail_1.html#notices-tab",
        {
            "loan": rm["loan"],
            "notifications": rm["notifications"],
            "summary": rm["summary"],
        },
    )


@login_required
@require_http_methods(["GET"])
def loan_detail_release_tab(request, pk):
    rm = get_given_loan_detail_read_model(pk)
    return render(
        request,
        "girvi/loan/loan_detail_1.html#release-tab",
        {"loan": rm["loan"], "summary": rm["summary"]},
    )
