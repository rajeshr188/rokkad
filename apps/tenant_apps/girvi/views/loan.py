import logging

import pytz
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
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
from apps.tenant_apps.contact.facade import customer_queryset
from apps.tenant_apps.girvi.models.license import Series
from apps.tenant_apps.party.services.customer_bridge import ensure_party_customer

from ..filters import LoanFilter
from ..filters import TakenLoanFilter
from ..flows import build_runtime_loan_flow, resolve_runtime_transition_name
from ..lifecycle import lifecycle_status_badge_class, lifecycle_status_label
from ..forms import (
    LoanCreateForm,
    LoanForm,
    LoanItemForm,
    LoanRenewForm,
    build_initial_loan_item_formset,
)
from ..models import (
    GivenLoan,
    LoanChangeLog,
    TakenLoan,
)
from ..policies import assert_loan_header_editable
from ..selectors import (
    build_unified_loan_rows,
    build_given_loan_action_readiness,
    get_given_loan_detail_read_model,
    filter_unified_loans,
    get_loan_totals,
    given_loan_base_qs,
    taken_loan_base_qs,
)
from ..services import (
    LoanCreateCommand,
    LoanCreationService,
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
from ..service_modules.bulk_operations import (
    BulkLoanOperationError,
    LoanBulkDeleteCommand,
    LoanBulkOperationService,
    LoanMergeCommand,
)
from ..service_modules.loan_workflow import LoanWorkflowService
from ..service_modules.transition_workflow import TransitionWorkflowService
from .access import girvi_permission_required, girvi_workspace_required
logger = logging.getLogger(__name__)


def _transition_form_kwargs(*, transition_name, request_user, loan, workspace, post_data=None):
    kwargs = {"user": request_user}
    if transition_name in {"disburse_loan", "activate"}:
        kwargs.update(
            {
                "loan": loan,
                "workspace": workspace,
            }
        )
    if post_data is not None:
        return {"data": post_data, **kwargs}
    return kwargs


@girvi_permission_required("girvi_loan_approve")
def loan_transition_view(request, pk):
    loan = get_object_or_404(GivenLoan, pk=pk)
    transition_context = TransitionWorkflowService.resolve_transition_context(loan, request)
    status_label = transition_context["status_label"]
    status_badge_class = transition_context["status_badge_class"]
    transition_name = transition_context["transition_name"]
    form_class = transition_context["form_class"]
    transition_ui = transition_context["transition_ui"]

    if not form_class:
        messages.error(request, _("Invalid transition."))
        return redirect(loan.get_absolute_url())

    policy_error = TransitionWorkflowService.assert_allowed(
        loan,
        transition_name,
        user=request.user,
        workspace=getattr(request, "tenant", None),
    )
    if policy_error:
        messages.error(request, policy_error)
        return redirect(loan.get_absolute_url())

    if request.method == "POST":
        form = form_class(
            **_transition_form_kwargs(
                transition_name=transition_name,
                request_user=request.user,
                loan=loan,
                workspace=request.tenant,
                post_data=request.POST,
            )
        )
        if form.is_valid():
            payload = {
                key: value for key, value in form.cleaned_data.items() if value is not None
            }
            result = LoanTransitionService(loan, request.user, request.tenant).execute(
                transition_name, **payload
            )
            getattr(messages, result.level)(request, result.message)
            return redirect(loan.get_absolute_url())
    else:
        form = form_class(
            **_transition_form_kwargs(
                transition_name=transition_name,
                request_user=request.user,
                loan=loan,
                workspace=request.tenant,
            )
        )

    return render(
        request,
        "girvi/loan/loan_transition_form.html",
        {
            "form": form,
            "loan": loan,
            "transition_name": transition_name,
            "transition_ui": transition_ui,
            "status_label": status_label,
            "status_badge_class": status_badge_class,
            "disbursal_preview": getattr(form, "disbursal_preview", None),
        },
    )


def get_loan_history(loan):
    return loan.loanchangelog_set.all().select_related("author").order_by("-changed")


@girvi_workspace_required
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


@girvi_workspace_required
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


@girvi_workspace_required
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


@girvi_workspace_required
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
        "table_hx_endpoint": reverse("girvi:loan_table_partial"),
        "table_hx_target": "#loan-table-container",
        "table_hx_select": "#loan-table-container",
        "table_hx_disable_select": True,
        "table_hx_swap": "outerHTML",
        **totals,
    }
    if request.htmx:
        return render(request, "girvi/loan/loan_list.html#loan-table", context)
    return render(request, "girvi/loan/loan_list.html", context)


def _extract_initial_item_inputs(item_formset):
    return LoanWorkflowService.extract_initial_item_inputs(item_formset)


def _build_loan_create_command(form, user, item_formset=None):
    return LoanWorkflowService.build_loan_create_command(form, user, item_formset)


def _parse_preview_loan_date(raw_value):
    return LoanWorkflowService.parse_preview_loan_date(raw_value)


def _build_preview_initial_item_inputs(data):
    return LoanWorkflowService.build_preview_initial_item_inputs(data)


def _build_create_preview_from_data(data, user):
    return LoanWorkflowService.build_create_preview_from_data(data, user)


def _loan_detail_redirect_response(request, loan_id):
    detail_url = reverse("girvi:girvi_loan_detail", kwargs={"pk": loan_id})
    return redirect(detail_url)


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
                return redirect("girvi:girvi_license_list")
            form = LoanCreateForm(initial=initial_data)
            item_formset = item_formset or item_formset_class(prefix="items")
            creation_preview = initial_data.get("creation_preview")
        else:
            form = LoanForm(instance=loan)
    elif loan is None and form.is_bound:
        item_formset = item_formset or item_formset_class(request.POST or None, prefix="items")
        preview_fields = {
            "borrower_party",
            "series",
            "loan_date",
            "tenure",
            "interest_type",
        }
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
    form = LoanCreateForm(request.POST)
    item_formset = item_formset_class(request.POST, prefix="items")

    form_is_valid = form.is_valid()
    formset_is_valid = item_formset.is_valid()

    if form_is_valid and formset_is_valid:
        result = LoanCreationService.execute(
            _build_loan_create_command(form, request.user, item_formset)
        )
        if result.success:
            messages.success(request, result.message)
            return _loan_detail_redirect_response(request, result.loan.id)

        form.add_error(None, result.message)

    messages.warning(request, "Please correct the errors below.")
    return _render_loan_form_response(request, form=form, item_formset=item_formset)


def _handle_loan_update_post(request, loan):
    assert_loan_header_editable(loan)
    form = LoanForm(request.POST, instance=loan)
    if form.is_valid():
        loan = LoanWorkflowService.persist_loan_update(form, user=request.user)

        messages.success(request, f"Updated Loan: {loan.loan_id}")
        return _loan_detail_redirect_response(request, loan.id)

    messages.warning(request, "Please correct the errors below.")
    return _render_loan_form_response(request, loan=loan, form=form)


@girvi_workspace_required
def loan_save(request, id=None, pk=None):
    """Backward-compatible dispatcher. Prefer `loan_create` / `loan_update`."""
    if id is not None:
        return loan_update(request, pk=id)
    if pk is not None:
        return loan_create_for_customer(request, customer_pk=pk)
    return loan_create(request)


@girvi_permission_required("girvi_loan_create")
@require_http_methods(["GET"])
def loan_create_preview(request):
    preview = _build_create_preview_from_data(request.GET, request.user)
    return render(
        request,
        "girvi/loan/_creation_preview.html",
        {"creation_preview": preview, "loan": None},
    )


@girvi_permission_required("girvi_loan_create")
def loan_create(request):
    """Dedicated create endpoint using LoanCreationService for POST writes."""
    try:
        if request.method == "POST":
            return _handle_loan_create_post(request)
        return _render_loan_form_response(request)
    except Exception as e:
        logger.warning(f"Error in loan_create: {str(e)}")
        messages.error(request, "An error occurred while creating loan")
        return redirect("girvi:girvi_loan_list")


@girvi_permission_required("girvi_loan_create")
def loan_create_for_customer(request, customer_pk):
    """Dedicated create endpoint with borrower preselection."""
    try:
        if request.method == "POST":
            return _handle_loan_create_post(request)
        return _render_loan_form_response(request, customer_pk=customer_pk)
    except Exception as e:
        logger.warning(f"Error in loan_create_for_customer: {str(e)}")
        messages.error(request, "An error occurred while creating loan")
        return redirect("girvi:girvi_loan_list")


@girvi_permission_required("girvi_loan_edit")
def loan_update(request, pk):
    """Dedicated update endpoint for existing loans."""
    try:
        loan = get_object_or_404(GivenLoan, id=pk)
        assert_loan_header_editable(loan)
        if request.method == "POST":
            return _handle_loan_update_post(request, loan)
        return _render_loan_form_response(request, loan=loan)
    except ValidationError as e:
        messages.error(request, "; ".join(getattr(e, "messages", None) or [str(e)]))
        return redirect("girvi:girvi_loan_detail", pk=pk)
    except Exception as e:
        logger.warning(f"Error in loan_update: {str(e)}")
        messages.error(request, "An error occurred while saving loan")
        return redirect("girvi:girvi_loan_list")


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
            get_object_or_404(customer_queryset().select_related("account"), pk=customer_pk)
            if customer_pk
            else None
        )
        borrower_party = getattr(borrower, "party", None) if borrower else None
        preview_command = LoanCreateCommand(
            borrower=borrower,
            borrower_party=borrower_party,
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
        if borrower_party:
            initial["borrower_party"] = borrower_party

        return initial

    except Exception as e:
        logger.error(f"Error getting initial loan data: {str(e)}")
        return None


@require_http_methods(["DELETE"])
@girvi_permission_required("girvi_loan_delete")
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


@girvi_workspace_required
def loan_detail(request, pk):
    rm = get_given_loan_detail_read_model(pk)
    loan = rm["loan"]
    display = rm["display"]

    flow = build_runtime_loan_flow(loan, request.user, request.tenant)
    current_status = flow.status
    current_status_label = lifecycle_status_label(current_status)
    current_status_badge_class = lifecycle_status_badge_class(current_status)

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
    action_readiness = build_given_loan_action_readiness(
        loan,
        transition_actions=transition_actions,
        release_action=rm["release_action"],
        changelog=list(changelog),
    )

    context = {
        "object": loan,
        "loan": loan,
        "customer": loan.borrower,
        "value": Money(display["value"], "INR"),
        "worth": display["worth"],
        "lvratio": display["lvratio"],
        "dvratio": display["dvratio"],
        "weight": display["weight"],
        "pure": display["pure"],
        "location": display["location"],
        "position": display["position"],
        "expires": (
            loan.calculate_months_to_exceed_value(display["value"], display["due"])
            if hasattr(loan, "calculate_months_to_exceed_value")
            else 0
        ),
        "possible_transitions": possible_transitions,
        "transition_actions": transition_actions,
        "release_action": rm["release_action"],
        "action_readiness": action_readiness,
        "current_status": current_status,
        "current_status_label": current_status_label,
        "current_status_badge_class": current_status_badge_class,
        "change_log": changelog,
        "renewals_as_source": list(rm["renewals_as_source"]),
        "origin_renewal": rm["origin_renewal"],
        "interest_reporting": display["interest_reporting"],
    }

    if request.htmx:
        return render(request, "girvi/loan/loan_detail_1.html#loan-detail", context)
    return render(request, "girvi/loan/loan_detail_1.html", context)


@girvi_permission_required("girvi_loan_bulk", "girvi_loan_edit", require_all=False)
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


@girvi_permission_required("girvi_loan_bulk")
@require_http_methods(["POST"])
def merge_loans(request):
    """Handle loan merge action"""
    loan_kind = request.POST.get("loan_kind", "given")

    try:
        result = LoanBulkOperationService.merge_given_loans(
            LoanMergeCommand(
                raw_ids=request.POST.getlist("selection"),
                loan_kind=loan_kind,
                merged_by=request.user,
            )
        )

        messages.success(request, f"Successfully merged {result.merged_count} loans")
        return HttpResponse(
            headers={
                "HX-Redirect": reverse(
                    "girvi:girvi_loan_detail", kwargs={"pk": result.target_loan.id}
                )
            }
        )

    except BulkLoanOperationError as e:
        if e.message == "Invalid loan selection.":
            logger.warning(
                "merge_loans rejected invalid IDs: %s",
                request.POST.getlist("selection"),
            )
        messages.error(request, e.message)
        return HttpResponse(status=e.status_code, content=e.message)

    except Exception as e:
        logger.error(f"Error in merge_loans: {str(e)}")
        messages.error(request, "An error occurred while merging loans")
        return HttpResponse(status=500, content="An error occurred while merging loans")


@girvi_permission_required("girvi_loan_edit")
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
@girvi_permission_required("girvi_loan_delete")
def deleteLoan(request):
    loan_kind = request.POST.get("loan_kind", "given")
    try:
        result = LoanBulkOperationService.delete_selected_loans(
            LoanBulkDeleteCommand(
                raw_ids=request.POST.getlist("selection"),
                loan_kind=loan_kind,
            )
        )
    except BulkLoanOperationError as e:
        if e.message == "Invalid loan selection.":
            logger.warning(
                "deleteLoan rejected invalid IDs: %s",
                request.POST.getlist("selection"),
            )
        messages.error(request, e.message)
        return HttpResponse(status=e.status_code, content=e.message)

    messages.success(request, f"Deleted {result.deleted_count} loans")
    return HttpResponse(
        headers={
            "HX-Redirect": f"{reverse('girvi:girvi_loan_list')}?loan_kind={result.loan_kind}"
        }
    )


# ---------------------------------------------------------------------------
# Loan detail tab endpoints (lazy-loaded via HTMX)
# ---------------------------------------------------------------------------


@girvi_workspace_required
@require_http_methods(["GET"])
def loan_detail_items_tab(request, pk):
    rm = get_given_loan_detail_read_model(pk)
    return render(
        request,
        "girvi/loan/loan_detail_1.html#items-tab",
        {"loan": rm["loan"], "items": rm["items"], "summary": rm["summary"]},
    )


@girvi_workspace_required
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


@girvi_workspace_required
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


@girvi_workspace_required
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


@girvi_workspace_required
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


@girvi_workspace_required
@require_http_methods(["GET"])
def loan_detail_release_tab(request, pk):
    rm = get_given_loan_detail_read_model(pk)
    return render(
        request,
        "girvi/loan/loan_detail_1.html#release-tab",
        {
            "loan": rm["loan"],
            "summary": rm["summary"],
            "release_action": rm["release_action"],
        },
    )
