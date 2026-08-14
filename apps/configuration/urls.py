from django.urls import path

from . import views

app_name = "configuration"

urlpatterns = [
    path(
        "workspaces/<int:workspace_id>/preferences/",
        views.workspace_preferences_redirect,
        name="workspace_preferences",
    ),
]
