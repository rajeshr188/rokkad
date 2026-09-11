"""Compatibility imports for orgs URLs and existing Python callers.

Request handlers live in web/; keep decorated exports and route names stable.
"""

from apps.orgs.models import Company, CompanyInvitation, Membership

from apps.orgs.web.workspace_settings import (
    workspace_create,
    workspace_list,
    workspace_detail,
    workspace_setup,
    workspace_setup_state,
    workspace_modules,
    workspace_security,
    workspace_update,
    _workspace_module_statuses,
    WORKSPACE_MODULE_REGISTRY,
)

from apps.orgs.web.role_settings import (
    workspace_role_permissions,
)

from apps.orgs.web.access_helpers import (
    _assert_workspace_access,
    _assert_owner_access,
)

from apps.orgs.web.team_members import (
    team_remove_member,
    team_change_role,
    membership_list,
    my_memberships,
    workspace_leave,
    _is_owner_membership,
    _owner_membership_count,
)

from apps.orgs.web.invitations import (
    companyinvitations_list,
    team_invite,
    invite_success,
    team_accept_invitation,
    invitation_delete,
    team_invitations,
    _get_workspace_from_query,
)

from apps.orgs.web.workspace_lifecycle import (
    workspace_delete,
    archived_workspaces,
    workspace_restore,
    workspace_lifecycle_transition,
)

from apps.orgs.web.workspace_navigation import (
    workspace_selector,
    workspace_select,
    workspace_dashboard,
)

from apps.orgs.web.account_preferences import (
    CompanyPreferenceBuilder,
    profile,
    account_settings,
)

from apps.orgs.web.slug_routes import (
    workspace_slug_dashboard,
    workspace_slug_settings_home,
    workspace_slug_settings_setup,
    workspace_slug_settings_setup_state,
    workspace_slug_settings_preferences,
    workspace_slug_settings_team,
    workspace_slug_settings_invitations,
    workspace_slug_settings_invite,
    workspace_slug_settings_profile,
    workspace_slug_settings_billing,
    workspace_slug_settings_roles,
    workspace_slug_settings_numbering,
    workspace_slug_settings_modules,
    workspace_slug_settings_security,
    workspace_slug_settings_archive,
    workspace_slug_parties,
    workspace_slug_party_create,
    workspace_slug_party_detail,
    workspace_slug_party_update,
    workspace_slug_party_merge,
    workspace_slug_loans,
    workspace_slug_loans_dispatch,
    workspace_slug_loan_list,
    workspace_slug_loan_create,
    workspace_slug_loan_table,
    workspace_slug_loan_detail,
    workspace_slug_loan_detail_items,
    workspace_slug_loan_detail_payments,
    workspace_slug_loan_detail_transactions,
    workspace_slug_loan_detail_statement,
    workspace_slug_loan_detail_notices,
    workspace_slug_loan_detail_release,
    workspace_slug_loan_pdf,
    workspace_slug_loan_report,
    workspace_slug_loan_by_customer_report,
    workspace_slug_loan_crosstab_report,
    workspace_slug_loan_list_report,
    workspace_slug_loan_reconciliation_report,
    workspace_slug_loan_operational_controls_report,
    workspace_slug_inventory,
    workspace_slug_inventory_products,
    workspace_slug_inventory_product_detail,
    workspace_slug_inventory_stock,
    workspace_slug_inventory_stock_detail,
    workspace_slug_inventory_stock_audit,
    workspace_slug_inventory_transactions,
    workspace_slug_inventory_statements,
    workspace_slug_rates,
    workspace_slug_rate_detail,
    workspace_slug_rate_sources,
    workspace_slug_rate_source_detail,
    workspace_slug_notifications,
    workspace_slug_notification_detail,
    workspace_slug_notice_groups,
    workspace_slug_notice_group_detail,
    workspace_slug_data_tools_export,
    workspace_slug_data_tools_import,
    workspace_slug_data_tools_export_data,
    _get_workspace_from_slug,
    retired_accounting_surface,
    workspace_slug_settings_accounting,
    workspace_slug_accounting,
    workspace_slug_accounting_chart_of_accounts,
    workspace_slug_accounting_accounts,
    workspace_slug_accounting_account_detail,
    workspace_slug_accounting_ledgers,
    workspace_slug_accounting_ledger_detail,
    workspace_slug_accounting_transactions,
    workspace_slug_accounting_trial_balance,
    workspace_slug_accounting_balance_sheet,
    workspace_slug_accounting_profit_loss,
    workspace_slug_accounting_income_statement,
    workspace_slug_accounting_cash_flow,
    workspace_slug_accounting_ar_aging,
    workspace_slug_accounting_ap_aging,
    workspace_slug_accounting_financial_ratios,
    workspace_slug_accounting_vouchers,
    workspace_slug_accounting_voucher_detail,
    workspace_slug_accounting_payments,
    workspace_slug_accounting_payment_detail,
    workspace_slug_accounting_expenses,
    workspace_slug_accounting_expense_detail,
    workspace_slug_accounting_journal_entry_vouchers,
    workspace_slug_accounting_journal_entry_voucher_detail,
    workspace_slug_accounting_periods,
    workspace_slug_accounting_period_detail,
    workspace_slug_accounting_reconciliation,
    workspace_slug_accounting_reconciliation_detail,
    workspace_slug_operations,
    workspace_slug_sales,
    workspace_slug_purchase,
    workspace_slug_commodity,
    workspace_slug_commodity_detail,
    workspace_slug_commodity_metal_balance_report,
    workspace_slug_commodity_exposure_report,
    workspace_slug_commodity_valuation_report,
    workspace_slug_reports,
)

from apps.orgs.web.compatibility import (
    has_permission,
    has_role,
    subscription_required,
)
