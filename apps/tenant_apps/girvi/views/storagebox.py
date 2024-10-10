from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string

from ..forms import LoanItemStorageBoxForm
from ..models import LoanItemStorageBox


def list_storage_boxes(request):
    storage_boxes = LoanItemStorageBox.objects.all()
    return render(
        request,
        "girvi/storagebox/storagebox_list.html",
        {"storage_boxes": storage_boxes},
    )


def add_storage_box(request):
    if request.method == "POST":
        form = LoanItemStorageBoxForm(request.POST)
        if form.is_valid():
            storage_box = form.save()
            return JsonResponse(
                {
                    "success": True,
                    "html": render_to_string(
                        "girvi/storagebox/storagebox_item.html",
                        {"storage_box": storage_box},
                    ),
                }
            )
        else:
            return JsonResponse({"success": False, "html": form.errors})
    else:
        form = LoanItemStorageBoxForm()
    return render(request, "girvi/storagebox/storagebox_form.html", {"form": form})


def update_storage_box(request, pk):
    storage_box = get_object_or_404(LoanItemStorageBox, pk=pk)
    if request.method == "POST":
        form = LoanItemStorageBoxForm(request.POST, instance=storage_box)
        if form.is_valid():
            storage_box = form.save()
            return JsonResponse(
                {
                    "success": True,
                    "html": render_to_string(
                        "girvi/storagebox/storagebox_item.html",
                        {"storage_box": storage_box},
                    ),
                }
            )
    else:
        form = LoanItemStorageBoxForm(instance=storage_box)
    return render(request, "girvi/storagebox/storagebox_form.html", {"form": form})


def delete_storage_box(request, pk):
    storage_box = get_object_or_404(LoanItemStorageBox, pk=pk)
    if request.method == "POST":
        storage_box.delete()
        return JsonResponse({"success": True})
    return render(
        request,
        "girvi/storagebox/storagebox_confirm_delete.html",
        {"storage_box": storage_box},
    )


def storage_box_detail(request, pk):
    storage_box = get_object_or_404(LoanItemStorageBox, pk=pk)
    return render(
        request,
        "girvi/storagebox/storagebox_detail.html",
        {"storage_box": storage_box},
    )
