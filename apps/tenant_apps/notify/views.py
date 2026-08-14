from django.http import HttpResponse
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404, render, reverse
from django.template.response import TemplateResponse
from django.views.decorators.http import require_http_methods

from apps.tenant_apps.girvi.models import GivenLoan
from apps.tenant_apps.utils.htmx_utils import for_htmx

from .forms import NoticeGroupForm, NotificationForm
from .models import NoticeGroup, Notification
from .access import notify_action_required

# Create your views here.


@notify_action_required("view")
def noticegroup_list(request):
    ng = NoticeGroup.objects.all().prefetch_related("notifications")
    return render(request, "notify/noticegroup_list.html", context={"objects": ng})


@notify_action_required("create")
def noticegroup_create(request):
    form = NoticeGroupForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            object = form.save()
            return render(
                request, "notify/noticegroup_detail.html", context={"object": object}
            )
    return render(request, "notify/noticegroup_form.html", context={"form": form})


@notify_action_required("view")
@for_htmx(use_block="content")
def noticegroup_detail(request, pk):
    ng = get_object_or_404(NoticeGroup, pk=pk)
    # loans = Loan.objects.unreleased().filter(
    #     created__gt=ng.date_range.lower, created__lt=ng.date_range.upper
    # )
    items = (
        ng.notifications.all()
        .prefetch_related("items__content_type")
        .select_related("group", "customer")
    )
    printable_items = items.filter(
        medium_type__in=(
            Notification.MediumType.Post,
            Notification.MediumType.Letter,
        )
    )
    given_loan_content_type = ContentType.objects.get_for_model(GivenLoan)
    loan_ids = printable_items.filter(
        items__content_type=given_loan_content_type,
    ).values_list("items__object_id", flat=True)
    loans_queryset = GivenLoan.objects.filter(
        pk__in=loan_ids,
        release__isnull=True,
    ).distinct()
    loans = loans_queryset.count()
    uniquie_customers = loans_queryset.values("borrower").distinct().count()

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
@notify_action_required("delete")
@require_http_methods(["DELETE"])
def noticegroup_delete(request, pk):
    ng = get_object_or_404(NoticeGroup, pk=pk)
    ng.delete()
    return HttpResponse(
        status=204, headers={"Hx-Redirect": reverse("notify_noticegroup_list")}
    )


# views for Notifications
@notify_action_required("delete")
@require_http_methods(["DELETE"])
def notification_delete(request, pk):
    ng = get_object_or_404(Notification, pk=pk)
    ng.delete()
    return HttpResponse(
        status=204, headers={"Hx-Redirect": reverse("notify_notification_list")}
    )


@notify_action_required("view")
def notification_list(request):
    ng = (
        Notification.objects.all()
        .select_related("group", "customer")
        .select_related("party")
        .prefetch_related("items__content_type", "customer__address", "customer__contactno")
    )
    return render(request, "notify/notification_list.html", context={"objects": ng})


@notify_action_required("create")
def notification_create(request):
    form = NotificationForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            object = form.save()
            return render(
                request, "notify/notification_detail.html", context={"object": object}
            )
    return render(request, "notify/notification_form.html", context={"form": form})


@notify_action_required("view")
def notification_detail(request, pk):
    ng = get_object_or_404(
        Notification.objects.select_related(
            "group", "customer", "party", "notice_type_config"
        ).prefetch_related("items__content_type"),
        pk=pk,
    )
    return render(request, "notify/notification_detail.html", context={"object": ng})


# this looks heavy on frontend with items > 100: optimise it
@notify_action_required("print")
def noticegroup_print(request, pk):
    ng = get_object_or_404(NoticeGroup, pk=pk)
    pdf = ng.print_notice()
    if not pdf:
        return HttpResponse("No printable content available for this notice group.", status=400)

    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="noticegroup_{ng.pk}.pdf"'
    return response


@notify_action_required("print")
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
