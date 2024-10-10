from django.urls import path

from . import views

urlpatterns = [
    # other url patterns
    path(
        "switch/workspace/<int:workspace_id>/",
        views.switch_workspace,
        name="switch_workspace",
    ),
    path("clear/workspace/", views.clear_workspace, name="clear_workspace"),
    path("profile/<int:pk>/", views.userprofile_detail, name="userprofile_detail"),
    path("profile/<int:pk>/edit/", views.userprofile_update, name="userprofile_update"),
]
