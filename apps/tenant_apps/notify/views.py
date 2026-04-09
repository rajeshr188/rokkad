from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render, reverse
from django.template.response import TemplateResponse
from django.views.decorators.http import require_http_methods

from apps.tenant_apps.girvi.models import GivenLoan
from apps.tenant_apps.utils.htmx_utils import for_htmx

from .forms import NoticeGroupForm, NotificationForm
from .models import NoticeGroup, Notification

# Create your views here.


@login_required
def noticegroup_list(request):
    ng = NoticeGroup.objects.all().prefetch_related("notifications")
    return render(request, "notify/noticegroup_list.html", context={"objects": ng})


@login_required
def noticegroup_create(request):
    form = NoticeGroupForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            object = form.save()
            return render(
                request, "notify/noticegroup_detail.html", context={"object": object}
            )
    return render(request, "notify/noticegroup_form.html", context={"form": form})


@login_required
@for_htmx(use_block="content")
def noticegroup_detail(request, pk):
    ng = get_object_or_404(NoticeGroup, pk=pk)
    # loans = Loan.objects.unreleased().filter(
    #     created__gt=ng.date_range.lower, created__lt=ng.date_range.upper
    # )
    items = (
        ng.notifications.all()
        .prefetch_related(
            "loans",
            "loans__borrower",
        )
        .select_related("group", "customer")
    )
    printable_items = items.filter(
        medium_type__in=(
            Notification.MediumType.Post,
            Notification.MediumType.Letter,
        )
    )
    loans = (
        GivenLoan.objects.filter(release__isnull=True)
        .filter(notifications__in=printable_items)
        .distinct()
        .count()
    )
    uniquie_customers = (
        GivenLoan.objects.filter(release__isnull=True)
        .filter(notifications__in=printable_items)
        .values("borrower")
        .distinct()
        .count()
    )

    return TemplateResponse(
        request,
        "notify/noticegroup_detail.html",
        context={
            "object": ng,
            "items": items,
            "customers": uniquie_customers,
            "loans": loans,
        },
    )


# view to delete a noticegroup
@login_required
@require_http_methods(["DELETE"])
def noticegroup_delete(request, pk):
    ng = get_object_or_404(NoticeGroup, pk=pk)
    ng.delete()
    return HttpResponse(
        status=204, headers={"Hx-Redirect": reverse("notify_noticegroup_list")}
    )


# views for Notifications
@login_required
@require_http_methods(["DELETE"])
def notification_delete(request, pk):
    ng = get_object_or_404(Notification, pk=pk)
    ng.delete()
    return HttpResponse(
        status=204, headers={"Hx-Redirect": reverse("notify_notification_list")}
    )


@login_required
def notification_list(request):
    ng = (
        Notification.objects.all()
        .select_related("group", "customer")
        .prefetch_related("loans", "customer__address", "customer__contactno")
    )
    return render(request, "notify/notification_list.html", context={"objects": ng})


@login_required
def notification_create(request):
    form = NotificationForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            object = form.save()
            return render(
                request, "notify/notification_detail.html", context={"object": object}
            )
    return render(request, "notify/notification_form.html", context={"form": form})


@login_required
def notification_detail(request, pk):
    ng = get_object_or_404(
        Notification.objects.select_related(
            "group", "customer", "notice_type_config"
        ).prefetch_related("items__content_type", "loans"),
        pk=pk,
    )
    return render(request, "notify/notification_detail.html", context={"object": ng})


# this looks heavy on frontend with items > 100: optimise it
@login_required
def noticegroup_print(request, pk):
    ng = get_object_or_404(NoticeGroup, pk=pk)
    pdf = ng.print_notice()
    if not pdf:
        return HttpResponse("No printable content available for this notice group.", status=400)

    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="noticegroup_{ng.pk}.pdf"'
    return response


@login_required
def notification_print(request, pk):
    notification = get_object_or_404(Notification, pk=pk)
    pdf = notification.print_letter()
    if not pdf:
        return HttpResponse("No printable content available for this notification.", status=400)

    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="notification_{notification.pk}.pdf"'
    return response


def notify_group_msg(request, pk):
    pass


def notify_msg(request, pk):
    pass
