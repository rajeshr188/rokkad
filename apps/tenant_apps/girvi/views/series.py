from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from ..forms import LoanCreateForm, SeriesForm
from ..models import Series
from ..services import GirviNumberSequenceService, LoanIDGenerator

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
    """AJAX endpoint to preview next loan ID when series is selected."""
    try:
        series_id = request.GET.get("series", None)
        if series_id:
            series = get_object_or_404(Series, id=series_id)
            # Preview only; allocation happens when the document is saved.
            loan_id = LoanIDGenerator.preview(series)
        else:
            loan_id = ""

        form = LoanCreateForm(initial={"loan_id": loan_id})
        context = {
            "field": form["loan_id"],
        }
        return render(request, "girvi/partials/field.html", context)
    except Http404:
        return JsonResponse({"error": "Series not found"}, status=404)
    except Exception as e:
        return HttpResponse(f"Error generating loan ID: {str(e)}", status=500)


# create views to crud series
@login_required
def series_list(request):
    series = Series.objects.order_by("name")
    context = {"series_list": series}
    if request.htmx:
        return render(request, "girvi/series/series_list.html#series-list", context)
    return render(request, "girvi/series/series_list.html", context)


@login_required
def series_detail(request, pk):
    series = get_object_or_404(Series, pk=pk)
    context = {
        "series": series,
        "sequence_summaries": GirviNumberSequenceService.summaries_for_series(series),
    }
    return render(request, "girvi/series/series_detail.html", context)


@login_required
def series_sync_sequences(request, pk):
    if request.method != "POST":
        return HttpResponse(status=405)

    series = get_object_or_404(Series, pk=pk)
    summaries = GirviNumberSequenceService.sync_all_for_series(
        series,
        apply=True,
        updated_by=request.user,
    )
    created_count = sum(1 for summary in summaries if summary["created"])
    messages.success(
        request,
        (
            f"Number sequences synced for {series}. "
            f"{created_count} created, {len(summaries) - created_count} updated."
        ),
    )
    return redirect("girvi:girvi_series_detail", pk=series.pk)


@login_required
def series_new(request):
    if request.method == "POST":
        form = SeriesForm(request.POST)
        if form.is_valid():
            series = form.save()
            if request.htmx:
                return HttpResponse(
                    headers={
                        "HX-Redirect": redirect(
                            "girvi:girvi_series_detail", pk=series.pk
                        ).url
                    }
                )
            return redirect("girvi:girvi_series_detail", pk=series.pk)
    else:
        form = SeriesForm()
    return render(request, "girvi/series/series_edit.html", {"form": form})


@login_required
def series_edit(request, pk):
    series = get_object_or_404(Series, pk=pk)
    if request.method == "POST":
        form = SeriesForm(request.POST, instance=series)
        if form.is_valid():
            series = form.save()
            if request.htmx:
                return HttpResponse(
                    headers={
                        "HX-Redirect": redirect(
                            "girvi:girvi_series_detail", pk=series.pk
                        ).url
                    }
                )
            return redirect("girvi:girvi_series_detail", pk=series.pk)
    else:
        form = SeriesForm(instance=series)
    return render(request, "girvi/series/series_edit.html", {"form": form})


@login_required
def series_delete(request, pk):
    if request.method != "POST":
        return HttpResponse(status=405)
    series = get_object_or_404(Series, pk=pk)
    series.delete()
    if request.htmx:
        return HttpResponse(headers={"HX-Redirect": redirect("girvi:girvi_series_list").url})
    return redirect("girvi:girvi_series_list")
