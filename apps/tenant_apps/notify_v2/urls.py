from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="notify_v2_index"),
    path("settings/", views.settings_overview, name="notify_v2_settings"),
    path("settings/whatsapp-cloud/", views.whatsapp_cloud_integration_setup, name="notify_v2_whatsapp_cloud_integration"),
    path("webhooks/whatsapp/cloud/", views.whatsapp_cloud_webhook, name="notify_v2_whatsapp_cloud_webhook"),
    path("batches/", views.batch_list, name="notify_v2_batch_list"),
    path("batches/<int:pk>/", views.batch_detail, name="notify_v2_batch_detail"),
    path("batches/<int:pk>/send/", views.batch_send_digital, name="notify_v2_batch_send_digital"),
    path("batches/<int:pk>/artifacts.zip/", views.batch_download_artifacts, name="notify_v2_batch_download_artifacts"),
    path("batches/<int:pk>/mark-printed/", views.batch_mark_printed, name="notify_v2_batch_mark_printed"),
    path("batches/<int:pk>/mark-posted/", views.batch_mark_posted, name="notify_v2_batch_mark_posted"),
]
