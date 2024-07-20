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
]
