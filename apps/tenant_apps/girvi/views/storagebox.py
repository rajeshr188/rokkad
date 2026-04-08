from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from ..forms import LoanItemStorageBoxForm
from ..models import LoanItemStorageBox


def _render_storagebox_list(request):
    storage_boxes = LoanItemStorageBox.objects.order_by("name")
    return render(
        request,
        "girvi/storagebox/storagebox_list.html#storagebox-list",
        {"storage_boxes": storage_boxes},
    )


@require_http_methods(["GET"])
@login_required
def list_storage_boxes(request):
    storage_boxes = LoanItemStorageBox.objects.order_by("name")
    context = {"storage_boxes": storage_boxes}
    if request.htmx:
        return render(request, "girvi/storagebox/storagebox_list.html#storagebox-list", context)
    return render(request, "girvi/storagebox/storagebox_list.html", context)


@require_http_methods(["GET", "POST"])
@login_required
def add_storage_box(request):
    if request.method == "POST":
        form = LoanItemStorageBoxForm(request.POST)
        if form.is_valid():
            form.save()
            return _render_storagebox_list(request)
        return render(
            request,
            "girvi/storagebox/storagebox_form.html",
            {"form": form},
            status=400,
        )
    else:
        form = LoanItemStorageBoxForm()
    return render(request, "girvi/storagebox/storagebox_form.html", {"form": form})


@require_http_methods(["GET", "POST"])
@login_required
def update_storage_box(request, pk):
    storage_box = get_object_or_404(LoanItemStorageBox, pk=pk)
    if request.method == "POST":
        form = LoanItemStorageBoxForm(request.POST, instance=storage_box)
        if form.is_valid():
            form.save()
            return _render_storagebox_list(request)
        return render(
            request,
            "girvi/storagebox/storagebox_form.html",
            {"form": form},
            status=400,
        )
    else:
        form = LoanItemStorageBoxForm(instance=storage_box)
    return render(request, "girvi/storagebox/storagebox_form.html", {"form": form})


@require_http_methods(["POST"])
@login_required
def delete_storage_box(request, pk):
    storage_box = get_object_or_404(LoanItemStorageBox, pk=pk)
    storage_box.delete()
    return _render_storagebox_list(request)


@require_http_methods(["GET"])
@login_required
def storage_box_detail(request, pk):
    storage_box = get_object_or_404(LoanItemStorageBox, pk=pk)
    return render(request, "girvi/storagebox/storagebox_item.html", {"storage_box": storage_box})
