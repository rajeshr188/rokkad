from django.conf.urls import i18n
from django.urls import include, path
from django.views.generic import RedirectView

from apps.orgs import views as org_views


# Cross-plane service routes used by both public and tenant URLConfs.
SERVICE_URLPATTERNS = [
    path("i18n/", include(i18n)),
    path("dynamic_preferences/", include("dynamic_preferences.urls")),
    path("select2/", include("django_select2.urls")),
]

# Public/platform pages. The dashboard routes inside pages.urls still redirect
# authenticated users through the current compatibility flow.
PUBLIC_PLATFORM_URLPATTERNS = [
    path("", include("pages.urls")),
]

# Authentication and invitation entrypoints. These remain shared during the
# transition because users can arrive from public and tenant domains.
AUTH_URLPATTERNS = [
    path(
        "login/",
        RedirectView.as_view(
            pattern_name="account_login",
            permanent=False,
            query_string=True,
        ),
        name="login",
    ),
    path(
        "signup/",
        RedirectView.as_view(
            pattern_name="account_signup",
            permanent=False,
            query_string=True,
        ),
        name="signup",
    ),
    path(
        "password/reset/",
        RedirectView.as_view(
            pattern_name="account_reset_password",
            permanent=False,
            query_string=True,
        ),
        name="password_reset",
    ),
    path(
        "invitations/accept/<str:key>/",
        org_views.team_accept_invitation,
        name="public_invitation_accept",
    ),
    path("accounts/", include("allauth.urls")),
    path("accounts/", include("allauth.socialaccount.urls")),
    path("invitations/", include("invitations.urls")),
]

# Canonical SaaS control-plane aliases. These are additive aliases for the
# current orgs routes; old /orgs/... paths remain the compatibility surface.
CANONICAL_CONTROL_PLANE_URLPATTERNS = [
    path("app/", org_views.workspace_selector, name="app_dashboard"),
    path("app/workspaces/", org_views.workspace_selector, name="app_workspaces"),
    path("app/workspaces/new/", org_views.workspace_create, name="app_workspace_create"),
    path("app/invitations/", org_views.team_invitations, name="app_invitations"),
    path("app/memberships/", org_views.my_memberships, name="app_memberships"),
    path(
        "workspace/<int:workspace_id>/settings/",
        org_views.workspace_detail,
        name="workspace_settings_home",
    ),
    path(
        "workspace/<int:workspace_id>/settings/setup/",
        org_views.workspace_setup,
        name="workspace_settings_setup",
    ),
    path(
        "workspace/<int:workspace_id>/settings/setup/state/",
        org_views.workspace_setup_state,
        name="workspace_settings_setup_state",
    ),
    path(
        "workspace/<int:workspace_id>/settings/preferences/",
        org_views.CompanyPreferenceBuilder.as_view(),
        name="workspace_settings_preferences",
    ),
    path(
        "workspace/<int:workspace_id>/settings/team/",
        org_views.membership_list,
        name="workspace_settings_team",
    ),
    path(
        "workspace/<int:workspace_id>/settings/invitations/",
        org_views.companyinvitations_list,
        name="workspace_settings_invitations",
    ),
    path(
        "workspace/<int:workspace_id>/settings/invitations/new/",
        org_views.team_invite,
        name="workspace_settings_invite",
    ),
    path(
        "workspace/<int:workspace_id>/settings/modules/",
        org_views.workspace_modules,
        name="workspace_settings_modules",
    ),
    path(
        "workspace/<int:workspace_id>/settings/security/",
        org_views.workspace_security,
        name="workspace_settings_security",
    ),
    path(
        "workspace/<int:workspace_id>/settings/leave/",
        org_views.workspace_leave,
        name="workspace_settings_leave",
    ),
]

CANONICAL_WORKSPACE_SLUG_URLPATTERNS = [
    path(
        "w/<str:workspace_slug>/",
        org_views.workspace_slug_dashboard,
        name="workspace_slug_dashboard",
    ),
    path(
        "w/<str:workspace_slug>/settings/",
        org_views.workspace_slug_settings_home,
        name="workspace_slug_settings",
    ),
    path(
        "w/<str:workspace_slug>/settings/preferences/",
        org_views.workspace_slug_settings_preferences,
        name="workspace_slug_settings_preferences",
    ),
    path(
        "w/<str:workspace_slug>/settings/team/",
        org_views.workspace_slug_settings_team,
        name="workspace_slug_settings_team",
    ),
    path(
        "w/<str:workspace_slug>/settings/invitations/",
        org_views.workspace_slug_settings_invitations,
        name="workspace_slug_settings_invitations",
    ),
    path(
        "w/<str:workspace_slug>/settings/profile/",
        org_views.workspace_slug_settings_profile,
        name="workspace_slug_settings_profile",
    ),
    path(
        "w/<str:workspace_slug>/settings/billing/",
        org_views.workspace_slug_settings_billing,
        name="workspace_slug_settings_billing",
    ),
    path(
        "w/<str:workspace_slug>/settings/roles/",
        org_views.workspace_slug_settings_roles,
        name="workspace_slug_settings_roles",
    ),
    path(
        "w/<str:workspace_slug>/settings/numbering/",
        org_views.workspace_slug_settings_numbering,
        name="workspace_slug_settings_numbering",
    ),
    path(
        "w/<str:workspace_slug>/settings/modules/",
        org_views.workspace_slug_settings_modules,
        name="workspace_slug_settings_modules",
    ),
    path(
        "w/<str:workspace_slug>/settings/security/",
        org_views.workspace_slug_settings_security,
        name="workspace_slug_settings_security",
    ),
    path(
        "w/<str:workspace_slug>/settings/accounting/",
        org_views.workspace_slug_settings_accounting,
        name="workspace_slug_settings_accounting",
    ),
    path(
        "w/<str:workspace_slug>/operations/",
        org_views.workspace_slug_operations,
        name="workspace_slug_operations",
    ),
    path(
        "w/<str:workspace_slug>/parties/",
        org_views.workspace_slug_parties,
        name="workspace_slug_parties",
    ),
    path(
        "w/<str:workspace_slug>/parties/new/",
        org_views.workspace_slug_party_create,
        name="workspace_slug_party_create",
    ),
    path(
        "w/<str:workspace_slug>/parties/<int:pk>/",
        org_views.workspace_slug_party_detail,
        name="workspace_slug_party_detail",
    ),
    path(
        "w/<str:workspace_slug>/parties/<int:pk>/edit/",
        org_views.workspace_slug_party_update,
        name="workspace_slug_party_update",
    ),
    path(
        "w/<str:workspace_slug>/parties/<int:pk>/merge/",
        org_views.workspace_slug_party_merge,
        name="workspace_slug_party_merge",
    ),
    path(
        "w/<str:workspace_slug>/sales/",
        org_views.workspace_slug_sales,
        name="workspace_slug_sales",
    ),
    path(
        "w/<str:workspace_slug>/purchase/",
        org_views.workspace_slug_purchase,
        name="workspace_slug_purchase",
    ),
    path(
        "w/<str:workspace_slug>/loans/",
        org_views.workspace_slug_loans,
        name="workspace_slug_loans",
    ),
    path(
        "w/<str:workspace_slug>/loans/list/",
        org_views.workspace_slug_loan_list,
        name="workspace_slug_loan_list",
    ),
    path(
        "w/<str:workspace_slug>/loans/table/",
        org_views.workspace_slug_loan_table,
        name="workspace_slug_loan_table",
    ),
    path(
        "w/<str:workspace_slug>/loans/<int:pk>/",
        org_views.workspace_slug_loan_detail,
        name="workspace_slug_loan_detail",
    ),
    path(
        "w/<str:workspace_slug>/loans/<int:pk>/items/",
        org_views.workspace_slug_loan_detail_items,
        name="workspace_slug_loan_detail_items",
    ),
    path(
        "w/<str:workspace_slug>/loans/<int:pk>/payments/",
        org_views.workspace_slug_loan_detail_payments,
        name="workspace_slug_loan_detail_payments",
    ),
    path(
        "w/<str:workspace_slug>/loans/<int:pk>/transactions/",
        org_views.workspace_slug_loan_detail_transactions,
        name="workspace_slug_loan_detail_transactions",
    ),
    path(
        "w/<str:workspace_slug>/loans/<int:pk>/statement/",
        org_views.workspace_slug_loan_detail_statement,
        name="workspace_slug_loan_detail_statement",
    ),
    path(
        "w/<str:workspace_slug>/loans/<int:pk>/notices/",
        org_views.workspace_slug_loan_detail_notices,
        name="workspace_slug_loan_detail_notices",
    ),
    path(
        "w/<str:workspace_slug>/loans/<int:pk>/release/",
        org_views.workspace_slug_loan_detail_release,
        name="workspace_slug_loan_detail_release",
    ),
    path(
        "w/<str:workspace_slug>/loans/<int:pk>/pdf/",
        org_views.workspace_slug_loan_pdf,
        name="workspace_slug_loan_pdf",
    ),
    path(
        "w/<str:workspace_slug>/loans/reports/time-series/",
        org_views.workspace_slug_loan_report,
        name="workspace_slug_loan_report",
    ),
    path(
        "w/<str:workspace_slug>/loans/reports/by-customer/",
        org_views.workspace_slug_loan_by_customer_report,
        name="workspace_slug_loan_by_customer_report",
    ),
    path(
        "w/<str:workspace_slug>/loans/reports/crosstab/",
        org_views.workspace_slug_loan_crosstab_report,
        name="workspace_slug_loan_crosstab_report",
    ),
    path(
        "w/<str:workspace_slug>/loans/reports/list/",
        org_views.workspace_slug_loan_list_report,
        name="workspace_slug_loan_list_report",
    ),
    path(
        "w/<str:workspace_slug>/loans/reports/reconciliation/",
        org_views.workspace_slug_loan_reconciliation_report,
        name="workspace_slug_loan_reconciliation_report",
    ),
    path(
        "w/<str:workspace_slug>/loans/reports/operational-controls/",
        org_views.workspace_slug_loan_operational_controls_report,
        name="workspace_slug_loan_operational_controls_report",
    ),
    path(
        "w/<str:workspace_slug>/inventory/",
        org_views.workspace_slug_inventory,
        name="workspace_slug_inventory",
    ),
    path(
        "w/<str:workspace_slug>/inventory/products/",
        org_views.workspace_slug_inventory_products,
        name="workspace_slug_inventory_products",
    ),
    path(
        "w/<str:workspace_slug>/inventory/products/<int:pk>/",
        org_views.workspace_slug_inventory_product_detail,
        name="workspace_slug_inventory_product_detail",
    ),
    path(
        "w/<str:workspace_slug>/inventory/stock/",
        org_views.workspace_slug_inventory_stock,
        name="workspace_slug_inventory_stock",
    ),
    path(
        "w/<str:workspace_slug>/inventory/stock/<int:pk>/",
        org_views.workspace_slug_inventory_stock_detail,
        name="workspace_slug_inventory_stock_detail",
    ),
    path(
        "w/<str:workspace_slug>/inventory/stock/audit/",
        org_views.workspace_slug_inventory_stock_audit,
        name="workspace_slug_inventory_stock_audit",
    ),
    path(
        "w/<str:workspace_slug>/inventory/transactions/",
        org_views.workspace_slug_inventory_transactions,
        name="workspace_slug_inventory_transactions",
    ),
    path(
        "w/<str:workspace_slug>/inventory/statements/",
        org_views.workspace_slug_inventory_statements,
        name="workspace_slug_inventory_statements",
    ),
    path(
        "w/<str:workspace_slug>/rates/",
        org_views.workspace_slug_rates,
        name="workspace_slug_rates",
    ),
    path(
        "w/<str:workspace_slug>/rates/<int:pk>/",
        org_views.workspace_slug_rate_detail,
        name="workspace_slug_rate_detail",
    ),
    path(
        "w/<str:workspace_slug>/rates/sources/",
        org_views.workspace_slug_rate_sources,
        name="workspace_slug_rate_sources",
    ),
    path(
        "w/<str:workspace_slug>/rates/sources/<int:pk>/",
        org_views.workspace_slug_rate_source_detail,
        name="workspace_slug_rate_source_detail",
    ),
    path(
        "w/<str:workspace_slug>/notifications/",
        org_views.workspace_slug_notifications,
        name="workspace_slug_notifications",
    ),
    path(
        "w/<str:workspace_slug>/notifications/<int:pk>/",
        org_views.workspace_slug_notification_detail,
        name="workspace_slug_notification_detail",
    ),
    path(
        "w/<str:workspace_slug>/notifications/notice-groups/",
        org_views.workspace_slug_notice_groups,
        name="workspace_slug_notice_groups",
    ),
    path(
        "w/<str:workspace_slug>/notifications/notice-groups/<int:pk>/",
        org_views.workspace_slug_notice_group_detail,
        name="workspace_slug_notice_group_detail",
    ),
    path(
        "w/<str:workspace_slug>/data-tools/export/",
        org_views.workspace_slug_data_tools_export,
        name="workspace_slug_data_tools_export",
    ),
    path(
        "w/<str:workspace_slug>/data-tools/export/<str:model_name>/<str:export_format>/",
        org_views.workspace_slug_data_tools_export_data,
        name="workspace_slug_data_tools_export_data",
    ),
    path(
        "w/<str:workspace_slug>/accounting/",
        org_views.workspace_slug_accounting,
        name="workspace_slug_accounting",
    ),
    path(
        "w/<str:workspace_slug>/commodity/",
        org_views.workspace_slug_commodity,
        name="workspace_slug_commodity",
    ),
    path(
        "w/<str:workspace_slug>/reports/",
        org_views.workspace_slug_reports,
        name="workspace_slug_reports",
    ),
]

# Authenticated global/control-plane routes. These are still included in tenant
# URLConf for compatibility until Phase 2 route separation is completed.
GLOBAL_AUTHENTICATED_URLPATTERNS = [
    *CANONICAL_CONTROL_PLANE_URLPATTERNS,
    *CANONICAL_WORKSPACE_SLUG_URLPATTERNS,
    path("onboarding/", include("apps.onboarding.urls")),
    path("orgs/", include("apps.orgs.urls")),
    path("profile/", include("accounts.urls")),
    path("subscriptions/", include("apps.subscriptions.urls")),
]

# Backward-compatible aggregate used by current public and tenant URLConfs.
shared_urlpatterns = (
    SERVICE_URLPATTERNS
    + PUBLIC_PLATFORM_URLPATTERNS
    + AUTH_URLPATTERNS
    + GLOBAL_AUTHENTICATED_URLPATTERNS
)
