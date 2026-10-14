from django.urls import path
from . import views, announcement_views, diagnostic_views

urlpatterns = [
    path("app/platform/whatsapp/", diagnostic_views.platform, name="platform_whatsapp_dashboard"),
    path("app/account/whatsapp/<slug:workspace_slug>/history/", diagnostic_views.history, name="platform_whatsapp_history"),
    path("app/account/whatsapp/<slug:workspace_slug>/deliveries/<int:delivery_id>/<str:action>/", diagnostic_views.operation, name="platform_whatsapp_operation"),
    path("app/platform/whatsapp/announcements/", announcement_views.announcements, name="platform_whatsapp_announcements"),
    path("app/account/whatsapp/", views.preferences, name="platform_whatsapp_preferences"),
    path("app/integrations/whatsapp/webhook/", views.webhook, name="platform_whatsapp_webhook"),
]
