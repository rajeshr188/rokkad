"""
URL patterns for custody tracking and repledge management.

Add these to apps/tenant_apps/girvi/urls.py
"""

from django.urls import path
from apps.tenant_apps.girvi.views import custody_views

app_name = "girvi"

urlpatterns = [
    # ... existing URL patterns ...
    # ========================================================================
    # Custody Status Views
    # ========================================================================
    path(
        "items/<int:item_id>/custody/",
        custody_views.item_custody_status,
        name="item_custody_status",
    ),
    path(
        "loans/<int:loan_id>/custody/",
        custody_views.loan_custody_summary,
        name="loan_custody_summary",
    ),
    # ========================================================================
    # Return from Lender Workflow
    # ========================================================================
    path(
        "items/<int:item_id>/return-from-lender/",
        custody_views.return_item_from_lender,
        name="return_item_from_lender",
    ),
    path(
        "loans/<int:loan_id>/return-from/<int:taken_loan_id>/",
        custody_views.return_all_items_from_lender,
        name="return_all_items_from_lender",
    ),
    # ========================================================================
    # Enhanced Release with Auto-Return
    # ========================================================================
    path(
        "loans/<int:loan_id>/release/check/",
        custody_views.release_loan_check_custody,
        name="release_loan_check_custody",
    ),
    path(
        "loans/<int:loan_id>/release/with-return/",
        custody_views.release_loan_with_return,
        name="release_loan_with_return",
    ),
    # ========================================================================
    # Repledge Creation (Multi-Item Collateral)
    # ========================================================================
    path(
        "repledge/create/",
        custody_views.create_repledge_select_items,
        name="create_repledge_select_items",
    ),
    path(
        "repledge/create/with-items/",
        custody_views.create_repledge_with_items,
        name="create_repledge_with_items",
    ),
    # ========================================================================
    # Collateral Management
    # ========================================================================
    path(
        "taken-loans/<int:loan_id>/collateral/",
        custody_views.taken_loan_collateral_detail,
        name="taken_loan_collateral_detail",
    ),
    path(
        "taken-loans/<int:loan_id>/return-collateral/",
        custody_views.return_taken_loan_collateral,
        name="return_taken_loan_collateral",
    ),
    # ========================================================================
    # History and Reporting
    # ========================================================================
    path(
        "reports/repledge-history/",
        custody_views.repledge_history_report,
        name="repledge_history_report",
    ),
    # ========================================================================
    # AJAX/API Endpoints
    # ========================================================================
    path(
        "api/loans/<int:loan_id>/check-custody/",
        custody_views.api_check_release_custody,
        name="api_check_release_custody",
    ),
    path(
        "api/items/<int:item_id>/custody/",
        custody_views.api_item_custody_status,
        name="api_item_custody_status",
    ),
]
