from datetime import datetime

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
from ..services import BulkReleaseService, ReleaseLifecycleService
from ..tables import ReleaseTable


@login_required
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


@login_required
def release_create(request, pk=None):
    if request.POST:
        form = ReleaseForm(request.POST or None)
        if form.is_valid():
            try:
                release = ReleaseLifecycleService.create_release(
                    loan=form.cleaned_data["loan"],
                    created_by=request.user,
                    release_date=form.cleaned_data["release_date"],
                    released_by=form.cleaned_data.get("released_by"),
                )
            except ValidationError as exc:
                form.add_error(None, exc)
                messages.error(request, str(exc))
            else:
                # return HttpResponse(status = 200,headers={"HX-Trigger":loanChanged})
                response = redirect("girvi:girvi_loan_detail", pk=release.loan.pk)
                response["HX-Push-Url"] = reverse(
                    "girvi:girvi_loan_detail", kwargs={"pk": release.loan.pk}
                )
                return response
    else:
        loan = None
        if pk:
            loan = get_object_or_404(GivenLoan, pk=pk)
            form = ReleaseForm(
                initial={
                    # "release_id": increlid,
                    "loan": loan,
                    "release_date": timezone.now(),
                    "released_by": loan.borrower,
                }
            )
        else:
            form = ReleaseForm(
                initial={
                    # "release_id": increlid,
                    "release_date": datetime.now(),
                }
            )
    if request.htmx:
        return TemplateResponse(
            request, "girvi/release/release_form.html#release-form-content", context={"form": form}
        )
    return TemplateResponse(request, "girvi/release/release_form.html", context={"form": form})


@login_required
def release_detail(request, pk):
    release = get_object_or_404(Release, pk=pk)
    if request.htmx:
        return TemplateResponse(
            request, "girvi/release/release_detail.html#release-detail-content", {"object": release}
        )
    return TemplateResponse(
        request, "girvi/release/release_detail.html", {"object": release}
    )


@login_required
def release_update_view(request, pk):
    release = get_object_or_404(Release, pk=pk)
    print("Release:", release)  # Debugging statement
    if request.method == "POST":
        form = ReleaseForm(request.POST or None, instance=release)
        if form.is_valid():
            form.save()
            return redirect(reverse_lazy("girvi:girvi_release_list"))
    else:
        form = ReleaseForm(instance=release)
        # form.fields['loan'].initial = release.loan.id  # Explicitly set the initial value
        print("Form:", form)  # Debugging statement
        print("Form instance:", form.instance)  # Debugging statement
        print("Form loan field:", form["loan"].value())  # Debugging statement
    return render(request, "girvi/release/release_form.html", {"form": form})


class ReleaseDeleteView(LoginRequiredMixin, DeleteView):
    model = Release
    success_url = reverse_lazy("girvi:girvi_release_list")
    template_name = "girvi/release/release_confirm_delete.html"


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
                BulkReleaseService.build_preview_context(loans, date),
            )
        else:
            return TemplateResponse(
                request, "girvi/release/bulk_release.html", {"form": form}
            )
    form = BulkReleaseService.build_bulk_form(request.GET.getlist("selection"))
    if request.htmx:
        return TemplateResponse(request, "girvi/release/bulk_release.html#bulk-release-content", {"form": form})
    return TemplateResponse(request, "girvi/release/bulk_release.html", {"form": form})


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
def get_release_details(request):
    # get the loans from request
    loan_ids = request.POST.getlist("loans")  # list of loan ids

    loans = GivenLoan.objects.filter(id__in=loan_ids)
    return render(request, "girvi/release/bulk_release_details.html", {"loans": loans})
