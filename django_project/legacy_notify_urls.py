"""Temporary bookmark redirects for the retired legacy Notify application."""

from django.shortcuts import redirect
from django.urls import path


def notify_v2_batch_list_redirect(request, *args, **kwargs):
    """Discard incompatible legacy IDs and open canonical Notify v2 history."""
    return redirect("notify_v2_batch_list")


urlpatterns = (
    path("noticegroup/", notify_v2_batch_list_redirect, name="notify_noticegroup_list"),
    path("noticegroup/<int:pk>/", notify_v2_batch_list_redirect, name="notify_noticegroup_detail"),
    path("noticegroup/create/", notify_v2_batch_list_redirect, name="notify_noticegroup_create"),
    path("noticegroup/<int:pk>/delete/", notify_v2_batch_list_redirect, name="notify_noticegroup_delete"),
    path("noticegroup/<int:pk>/print", notify_v2_batch_list_redirect, name="notify_noticegroup_print"),
    path("notification/", notify_v2_batch_list_redirect, name="notify_notification_list"),
    path("notification/<int:pk>/", notify_v2_batch_list_redirect, name="notify_notification_detail"),
    path("notification/create/", notify_v2_batch_list_redirect, name="notify_notification_create"),
    path("notification/<int:pk>/print", notify_v2_batch_list_redirect, name="notify_notification_print"),
    path("notification/<int:pk>/delete/", notify_v2_batch_list_redirect, name="notify_notification_delete"),
)
