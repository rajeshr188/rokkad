from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from ..forms import LoanForm, SeriesForm
from ..models import Loan, Series
from ..services import generate_loan_id

# @login_required
# def next_loanid(request):
#     try:
#         series = request.GET.get("series")
#         s = get_object_or_404(Series, pk=series)

#         last_loan = s.loan_set.last()
#         if last_loan:
#             lid = last_loan.lid + 1
#         else:
#             lid = 1

#         form = LoanForm(initial={"lid": lid})
#         context = {
#             "field": form["lid"],
#         }
#         return render(request, "girvi/partials/field.html", context)
#     except (Series.DoesNotExist, Exception) as e:
#         # Handle exceptions here, you can log the error or return an error response
#         # For simplicity, here we are returning a basic error message
#         return render(
#             request,
#             "error.html",
#             {"error_message": "An error occurred in next_loanid."},
#         )


@login_required
def next_loanid(request):
    # def generate_loan_id(request):
    try:
        series_id = request.GET.get("series", None)
        if series_id:
            series = get_object_or_404(Series, id=series_id)
            loan_id = generate_loan_id(series_id=series_id)
            print(loan_id)
        else:
            loan_id = ""
        print(loan_id)
        form = LoanForm(initial={"loan_id": loan_id})
        context = {
            "field": form["loan_id"],
        }
        return render(request, "girvi/partials/field.html", context)
    except Http404:
        return JsonResponse({"error": "Series not found"}, status=404)
    except Exception as e:
        return HttpResponse(e, status=500)


# create views to crud series
def series_list(request):
    series = Series.objects.all()
    return render(request, "girvi/series/series_list.html", {"series": series})


def series_detail(request, pk):
    series = get_object_or_404(Series, pk=pk)
    return render(request, "girvi/series/series_detail.html", {"series": series})


def series_new(request):
    if request.method == "POST":
        form = SeriesForm(request.POST)
        if form.is_valid():
            series = form.save()
            return redirect("girvi:girvi_series_detail", pk=series.pk)
    else:
        form = SeriesForm()
    return render(request, "girvi/series/series_edit.html", {"form": form})


def series_edit(request, pk):
    series = get_object_or_404(Series, pk=pk)
    if request.method == "POST":
        form = SeriesForm(request.POST, instance=series)
        if form.is_valid():
            series = form.save()
            return redirect("girvi:girvi_series_detail", pk=series.pk)
    else:
        form = SeriesForm(instance=series)
    return render(request, "girvi/series/series_edit.html", {"form": form})


def series_delete(request, pk):
    series = get_object_or_404(Series, pk=pk)
    series.delete()
    return redirect("girvi:girvi_license_list")
