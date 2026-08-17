"""Deprecated import compatibility for the pre-RLS URLConf module name."""

from django_project.workspace_urls import (  # noqa: F401
    WORKSPACE_ADMIN_URLPATTERNS,
    WORKSPACE_APP_URLPATTERNS,
    urlpatterns,
)

# Temporary source compatibility for tests or extensions importing the old
# constants. Runtime settings use django_project.workspace_urls directly.
TENANT_ADMIN_URLPATTERNS = WORKSPACE_ADMIN_URLPATTERNS
TENANT_ERP_URLPATTERNS = WORKSPACE_APP_URLPATTERNS
