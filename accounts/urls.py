from django.urls import path

from . import views

urlpatterns = [
    # Workspace switching and management
    path(
        "switch/workspace/<int:workspace_id>/",
        views.switch_workspace,
        name="switch_workspace",
    ),
    path(
        "clear/workspace/",
        views.clear_workspace,
        name="clear_workspace",
    ),
    path(
        "reset/workspace/",
        views.reset_workspace,
        name="reset_workspace",
    ),
    path(
        "workspace/management/",
        views.workspace_management,
        name="workspace_management",
    ),
    # Profile management
    path(
        "profile/<int:pk>/",
        views.userprofile_detail,
        name="userprofile_detail",
    ),
    path(
        "profile/<int:pk>/edit/",
        views.userprofile_update,
        name="userprofile_update",
    ),
]
