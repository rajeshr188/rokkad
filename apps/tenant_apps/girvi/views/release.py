from datetime import datetime
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render, reverse
from django.template.response import TemplateResponse
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import DeleteView
from django_tables2.config import RequestConfig

from ..filters import ReleaseFilter
from ..forms import BulkReleaseForm, ReleaseForm
from ..models import GivenLoan, Release
from ..services import (
    BulkReleaseService,
    ReleaseCreateCommand,
    ReleaseLifecycleService,
)
from ..service_modules.custody import build_release_readiness_checklist
from ..tables import ReleaseTable
from .access import (
    GirviPermissionRequiredMixin,
    girvi_permission_required,
    girvi_workspace_required,
)


logger = logging.getLogger(__name__)


@girvi_workspace_required
def release_list(request):
    filter = ReleaseFilter(
        request.GET,
        queryset=Release.objects.order_by("-id").select_related("loan"),
    )
    table = ReleaseTable(filter.qs)
    context = {"filter": filter, "table": table}

    RequestConfig(request, paginate={"per_page": 10}).configure(table)
    # export_format = request.GET.get("_export", None)
    # if TableExport.is_valid_format(export_format):
    #     exporter = TableExport(export_format, table, exclude_columns=())
    #     return exporter.response(f"table.{export_format}")
    if request.htmx:
        return TemplateResponse(request, "girvi/release/release_list.html#release-list-content", context)
    return TemplateResponse(request, "girvi/release/release_list.html", context)


def _build_release_preview(form, user):
    loan = getattr(form, "loan_preview", None)
    release_date = None
    released_by = None

    cleaned_data = getattr(form, "cleaned_data", None) or {}
    if cleaned_data:
        loan = cleaned_data.get("loan") or loan
        release_date = cleaned_data.get("release_date")
        released_by = cleaned_data.get("released_by")
    else:
        initial = getattr(form, "initial", {}) or {}
        loan = initial.get("loan") or loan
        release_date = initial.get("release_date")
        released_by = initial.get("released_by")

        if getattr(form, "is_bound", False):
            form_data = getattr(form, "data", {}) or {}
            release_date = form_data.get(form.add_prefix("release_date")) or release_date
            released_by = form_data.get(form.add_prefix("released_by")) or released_by

    if not loan or not user:
        return None

    return ReleaseLifecycleService.preview(
        ReleaseCreateCommand(
            loan=loan,
            created_by=user,
            release_date=release_date,
            released_by=released_by,
        )
    )


@girvi_permission_required("girvi_loan_release")
def release_create(request, pk=None):
    release_preview = None
    release_checklist = None

    if request.POST:
        form = ReleaseForm(request.POST or None)
        form_is_valid = form.is_valid()
        release_preview = _build_release_preview(form, request.user)

        if form_is_valid:
            release_checklist = build_release_readiness_checklist(
                form.cleaned_data["loan"]
            )
            if not release_checklist["can_release"]:
                for blocker in release_checklist["blockers"]:
                    form.add_error(None, blocker)
                messages.error(request, "Release checklist is not ready.")
            else:
                result = ReleaseLifecycleService.execute(
                    ReleaseCreateCommand(
                        loan=form.cleaned_data["loan"],
                        created_by=request.user,
                        release_date=form.cleaned_data["release_date"],
                        released_by=form.cleaned_data.get("released_by"),
                    )
                )
                if result.success:
                    for warning in result.warnings:
                        messages.warning(request, warning)
                    messages.success(request, result.message)
                    response = redirect("girvi:girvi_loan_detail", pk=result.release.loan.pk)
                    response["HX-Push-Url"] = reverse(
                        "girvi:girvi_loan_detail", kwargs={"pk": result.release.loan.pk}
                    )
                    return response

                form.add_error(None, result.message)
                messages.error(request, result.message)
    else:
        loan = None
        if pk:
            loan = get_object_or_404(GivenLoan, pk=pk)
            release_checklist = build_release_readiness_checklist(loan)
            if not release_checklist["can_release"]:
                return redirect("girvi:release_loan_check_custody", loan_id=loan.pk)
            form = ReleaseForm(
                initial={
                    "loan": loan,
                    "release_date": timezone.now(),
                    "released_by": loan.borrower,
                }
            )
        else:
            form = ReleaseForm(
                initial={
                    "release_date": datetime.now(),
                }
            )
        release_preview = _build_release_preview(form, request.user)

    context = {
        "form": form,
        "release_preview": release_preview,
        "release_checklist": release_checklist,
    }
    if getattr(request, "htmx", False):
        return TemplateResponse(
            request, "girvi/release/release_form.html#release-form-content", context=context
        )
    return TemplateResponse(request, "girvi/release/release_form.html", context=context)


@girvi_workspace_required
def release_detail(request, pk):
    release = get_object_or_404(Release, pk=pk)
    if request.htmx:
        return TemplateResponse(
            request, "girvi/release/release_detail.html#release-detail-content", {"object": release}
        )
    return TemplateResponse(
        request, "girvi/release/release_detail.html", {"object": release}
    )


@girvi_permission_required("girvi_loan_release")
def release_update_view(request, pk):
    release = get_object_or_404(Release, pk=pk)
    logger.debug("Editing release %s", release.pk)
    if request.method == "POST":
        form = ReleaseForm(request.POST or None, instance=release)
        if form.is_valid():
            form.save()
            return redirect(reverse_lazy("girvi:girvi_release_list"))
    else:
        form = ReleaseForm(instance=release)
        # form.fields['loan'].initial = release.loan.id  # Explicitly set the initial value
        logger.debug(
            "Release update form initialized",
            extra={
                "release_id": release.pk,
                "loan_field": form["loan"].value(),
            },
        )
    return render(request, "girvi/release/release_form.html", {"form": form})


class ReleaseDeleteView(GirviPermissionRequiredMixin, LoginRequiredMixin, DeleteView):
    model = Release
    success_url = reverse_lazy("girvi:girvi_release_list")
    template_name = "girvi/release/release_confirm_delete.html"
    required_permissions = ("girvi_loan_release",)


# def bulk_release(request):
#     # if this is a POST request we need to process the form data
#     if request.method == "POST":
#         # create a form instance and populate it with data from the request:
#         form = BulkReleaseForm(request.POST)
#         # check whether it's valid:
#         if form.is_valid():
#             date = form.cleaned_data["date"]
#             loans = form.cleaned_data["loans"]

#             if not date:
#                 date = timezone.now().date()
#             try:
#                 last_release = Release.objects.latest("id")
#                 next_releaseid = int(last_release.release_id) + 1
#             except Release.DoesNotExist:
#                 next_releaseid = 1
#             new_releases: List[Release] = []
#             for loan in loans:
#                 try:
#                     l = Loan.objects.get(loan_id=loan.loan_id)
#                 except Loan.DoesNotExist:
#                     # raise CommandError(f"Failed to create Release as {loan} does not exist")
#                     print(f"Failed to create Release as {loan} does not exist")
#                     continue
#                 release_id = str(next_releaseid)
#                 next_releaseid += 1
#                 new_release = Release(
#                     release_id=release_id,
#                     loan=l,
#                     release_date=date,  # datetime.now(timezone.utc),
#                     created_by=request.user,
#                 )
#                 new_releases.append(new_release)
#             try:
#                 with transaction.atomic():
#                     Release.objects.bulk_create(new_releases)
#                     # create journal_entries
#             except IntegrityError:
#                 print("Failed creating Release as already Released")

#     # if a GET (or any other method) we'll create a blank form
#     else:
#         selected_loans = request.GET.getlist("selection", "")
#         qs = Loan.unreleased.filter(id__in=selected_loans).values_list("id", flat=True)
#         form = BulkReleaseForm(initial={"loans": qs})
#         form_g = SearchLoanForm()
#     return TemplateResponse(request, "girvi/release/bulk_release.html", {"form": form, "form_g": form_g})


@girvi_permission_required("girvi_loan_release")
def bulk_release(request):
    if request.method == "POST":
        form = BulkReleaseForm(request.POST)
        if form.is_valid():
            date = form.cleaned_data["date"]
            loans = list(form.cleaned_data["loans"])

            if not date:
                date = timezone.now().date()

            return TemplateResponse(
                request,
                "girvi/release/release_formset.html",
                BulkReleaseService.build_preview_context(loans, date, user=request.user),
            )
        else:
            return TemplateResponse(
                request, "girvi/release/bulk_release.html", {"form": form}
            )
    form = BulkReleaseService.build_bulk_form(request.GET.getlist("selection"))
    if request.htmx:
        return TemplateResponse(request, "girvi/release/bulk_release.html#bulk-release-content", {"form": form})
    return TemplateResponse(request, "girvi/release/bulk_release.html", {"form": form})


@girvi_permission_required("girvi_loan_release")
def submit_release_formset(request):
    if request.method == "POST":
        formset = BulkReleaseService.bind_submit_formset(request.POST)
        commit_policy = request.POST.get(
            "commit_policy", BulkReleaseService.DEFAULT_COMMIT_POLICY
        )
        result = BulkReleaseService.commit_formset_with_policy(
            formset, request.user, commit_policy=commit_policy
        )
        if result["success"]:
            return render(
                request,
                "girvi/release/release_success.html",
                {
                    "instances": result["instances"],
                    "commit_policy": result.get("commit_policy"),
                    "skipped_released_count": result.get("skipped_released_count", 0),
                },
            )
        return render(request, "girvi/release/release_formset.html", result)
    return HttpResponseNotAllowed(["POST"])


@require_POST
@girvi_permission_required("girvi_loan_release")
def get_release_details(request):
    # get the loans from request
    loan_ids = request.POST.getlist("loans")  # list of loan ids

    loans = GivenLoan.objects.filter(id__in=loan_ids)
    return render(request, "girvi/release/bulk_release_details.html", {"loans": loans})
