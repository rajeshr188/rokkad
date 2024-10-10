from datetime import datetime
from typing import List

from django import forms
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render, reverse
from django.template.response import TemplateResponse
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST
from django.views.generic import CreateView, DeleteView, DetailView, UpdateView
from django_filters.views import FilterView
from django_tables2.config import RequestConfig
from django_tables2.export.export import TableExport
from django_tables2.export.views import ExportMixin
from django_tables2.views import SingleTableMixin

from apps.tenant_apps.utils.htmx_utils import for_htmx

from ..filters import ReleaseFilter
from ..forms import BulkReleaseForm, ReleaseForm, ReleaseFormSet
from ..models import Loan, Release
from ..tables import ReleaseTable


@login_required
@for_htmx(use_block_from_params="true")
def release_list(request):
    stats = {}
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
    return TemplateResponse(request, "girvi/release/release_list.html", context)


@login_required
@for_htmx(use_block="content")
def release_create(request, pk=None):
    if request.POST:
        form = ReleaseForm(request.POST or None)
        if form.is_valid():
            release = form.save(commit=False)
            release.created_by = request.user
            release.save()

            # return HttpResponse(status = 200,headers={"HX-Trigger":loanChanged})
            response = redirect("girvi:girvi_loan_detail", pk=form.instance.loan.pk)
            response["HX-Push-Url"] = reverse(
                "girvi:girvi_loan_detail", kwargs={"pk": form.instance.loan.pk}
            )
            return response
    else:
        loan = None
        if pk:
            loan = get_object_or_404(Loan, pk=pk)
            form = ReleaseForm(
                initial={
                    # "release_id": increlid,
                    "loan": loan,
                    "release_date": timezone.now(),
                    "released_by": loan.customer,
                }
            )
        else:
            form = ReleaseForm(
                initial={
                    # "release_id": increlid,
                    "release_date": datetime.now(),
                }
            )
    return TemplateResponse(
        request, "girvi/release/release_form.html", context={"form": form}
    )


@login_required
@for_htmx(use_block="content")
def release_detail(request, pk):
    release = get_object_or_404(Release, pk=pk)
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


from django.db import IntegrityError

# @for_htmx(use_block="content")
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


@for_htmx(use_block="content")
def bulk_release(request):
    # if this is a POST request we need to process the form data
    if request.method == "POST":
        # create a form instance and populate it with data from the request:
        form = BulkReleaseForm(request.POST)
        # check whether it's valid:
        if form.is_valid():
            date = form.cleaned_data["date"]
            loans = form.cleaned_data["loans"]

            if not date:
                date = timezone.now().date()

            formset_initial_data = [
                {
                    "loan": loan,
                    "release_date": date,
                    "released_by": loan.customer,
                    "release_amount": loan.due(),
                }
                for loan in loans
            ]
            ReleaseFormSet = forms.modelformset_factory(
                Release, form=ReleaseForm, extra=len(formset_initial_data)
            )
            formset = ReleaseFormSet(
                queryset=Release.objects.none(), initial=formset_initial_data
            )

            total_principal = sum(loan.loan_amount for loan in loans)
            total_interest = sum(loan.interestdue() for loan in loans)
            total_amount = sum(loan.due() for loan in loans)
            summary = {
                "total_loans": len(loans),
                "total_principal": total_principal,
                "total_interest": total_interest,
                "total_amount": total_amount,
            }
            return TemplateResponse(
                request,
                "girvi/release/release_formset.html",
                {"formset": formset, "summary": summary},
            )
        else:
            # If the form is invalid, return the form with errors
            return TemplateResponse(
                request, "girvi/release/bulk_release.html", {"form": form}
            )
    # if a GET (or any other method) we'll create a blank form
    else:
        selected_loans = request.GET.getlist("selection", "")
        qs = Loan.unreleased.filter(id__in=selected_loans).values_list("id", flat=True)
        form = BulkReleaseForm(
            initial={"loans": qs, "date": timezone.now().strftime("%Y-%m-%dT%H:%M")}
        )

    return TemplateResponse(request, "girvi/release/bulk_release.html", {"form": form})


def submit_release_formset(request):
    if request.method == "POST":
        formset = ReleaseFormSet(request.POST)
        if formset.is_valid():
            instances = formset.save()
            return render(
                request, "girvi/release/release_success.html", {"instances": instances}
            )
        return render(
            request, "girvi/release/release_formset.html", {"formset": formset}
        )
    return HttpResponseNotAllowed(["POST"])


@require_POST
def get_release_details(request):
    # get the loans from request
    loan_ids = request.POST.getlist("loans")  # list of loan ids
    date = request.POST.get("date")

    loans = Loan.objects.filter(id__in=loan_ids).with_details(None, None)
    return render(request, "girvi/release/bulk_release_details.html", {"loans": loans})
