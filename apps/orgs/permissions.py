"""
Permission definitions for the orgs app and multi-tenant system.
This file defines all permissions, their groupings, and role mappings.
"""

from typing import Dict, List, Tuple

# Permission format: (codename, name, description)
PermissionDef = Tuple[str, str, str]

# ============================================================================
# WORKSPACE-LEVEL PERMISSIONS
# ============================================================================

WORKSPACE_PERMISSIONS: List[PermissionDef] = [
    # View Permissions
    ("workspace_view", "Can view workspace", "View workspace details and settings"),
    ("workspace_list", "Can list workspaces", "View list of all accessible workspaces"),
    # Edit Permissions
    (
        "workspace_edit",
        "Can edit workspace",
        "Edit workspace settings and configuration",
    ),
    (
        "workspace_settings",
        "Can manage workspace settings",
        "Manage advanced workspace settings",
    ),
    # Delete Permissions
    ("workspace_delete", "Can delete workspace", "Permanently delete workspace"),
    ("workspace_archive", "Can archive workspace", "Soft delete/archive workspace"),
    # Transfer Permissions
    (
        "workspace_transfer",
        "Can transfer ownership",
        "Transfer workspace ownership to another user",
    ),
]

# ============================================================================
# TEAM MANAGEMENT PERMISSIONS
# ============================================================================

TEAM_PERMISSIONS: List[PermissionDef] = [
    # View Permissions
    ("team_view", "Can view team", "View team members and their roles"),
    ("team_list", "Can list team members", "View list of all team members"),
    # Invite Permissions
    ("team_invite", "Can invite members", "Send invitations to new team members"),
    ("team_invite_admin", "Can invite admins", "Send invitations with admin role"),
    # Manage Permissions
    ("team_edit", "Can edit team member", "Edit team member details"),
    ("team_remove", "Can remove members", "Remove members from workspace"),
    ("team_change_role", "Can change roles", "Change team member roles"),
    # Advanced Permissions
    ("team_view_activity", "Can view team activity", "View team member activity logs"),
]

# ============================================================================
# DATA & CONTENT PERMISSIONS
# ============================================================================

DATA_PERMISSIONS: List[PermissionDef] = [
    # View Permissions
    ("data_view", "Can view data", "View all data in workspace"),
    ("data_view_own", "Can view own data", "View only own created data"),
    # Create Permissions
    ("data_create", "Can create data", "Create new data entries"),
    # Edit Permissions
    ("data_edit", "Can edit data", "Edit any data entry"),
    ("data_edit_own", "Can edit own data", "Edit only own created data"),
    # Delete Permissions
    ("data_delete", "Can delete data", "Delete any data entry"),
    ("data_delete_own", "Can delete own data", "Delete only own created data"),
    # Export Permissions
    ("data_export", "Can export data", "Export data to CSV/Excel/PDF"),
    ("data_export_bulk", "Can bulk export", "Export large datasets"),
    # Import Permissions
    ("data_import", "Can import data", "Import data from CSV/Excel"),
]

# ============================================================================
# BILLING & SUBSCRIPTION PERMISSIONS
# ============================================================================

BILLING_PERMISSIONS: List[PermissionDef] = [
    # View Permissions
    ("billing_view", "Can view billing", "View billing information and invoices"),
    ("billing_history", "Can view billing history", "View payment history"),
    # Edit Permissions
    ("billing_edit", "Can edit billing", "Update payment methods and billing info"),
    ("billing_manage", "Can manage subscription", "Change subscription plans"),
    # Cancel Permissions
    ("billing_cancel", "Can cancel subscription", "Cancel workspace subscription"),
]

# ============================================================================
# REPORTING PERMISSIONS
# ============================================================================

REPORT_PERMISSIONS: List[PermissionDef] = [
    # View Permissions
    ("report_view", "Can view reports", "View all reports"),
    ("report_view_basic", "Can view basic reports", "View basic reports only"),
    # Create Permissions
    ("report_create", "Can create reports", "Create custom reports"),
    # Export Permissions
    ("report_export", "Can export reports", "Export reports to various formats"),
    ("report_schedule", "Can schedule reports", "Schedule automated report generation"),
]

# ============================================================================
# FEATURE-SPECIFIC PERMISSIONS (GIRVI MODULE)
# ============================================================================

GIRVI_PERMISSIONS: List[PermissionDef] = [
    # Loan Management
    ("girvi_loan_view", "Can view loans", "View loan details"),
    ("girvi_loan_create", "Can create loans", "Create new loan entries"),
    ("girvi_loan_edit", "Can edit loans", "Edit loan details"),
    ("girvi_loan_delete", "Can delete loans", "Delete loan entries"),
    # Loan Operations
    ("girvi_loan_approve", "Can approve loans", "Approve loan applications"),
    ("girvi_loan_release", "Can release loans", "Release completed loans"),
    ("girvi_loan_payment", "Can record payments", "Record loan payments"),
    # Advanced Features
    ("girvi_loan_bulk", "Can bulk operations", "Perform bulk loan operations"),
    ("girvi_report_view", "Can view loan reports", "View loan reports and analytics"),
]

# ============================================================================
# FEATURE-SPECIFIC PERMISSIONS (DEA MODULE - Accounting)
# ============================================================================

DEA_PERMISSIONS: List[PermissionDef] = [
    # Journal Entries
    ("dea_entry_view", "Can view entries", "View accounting entries"),
    ("dea_entry_create", "Can create entries", "Create journal entries"),
    ("dea_entry_edit", "Can edit entries", "Edit accounting entries"),
    ("dea_entry_delete", "Can delete entries", "Delete accounting entries"),
    # Financial Operations
    ("dea_reconciliation", "Can reconcile accounts", "Perform account reconciliation"),
    ("dea_close_period", "Can close periods", "Close accounting periods"),
    # Reports
    ("dea_report_view", "Can view financial reports", "View financial reports"),
    ("dea_report_export", "Can export financial reports", "Export financial reports"),
]

# FEATURE-SPECIFIC PERMISSIONS (STANDALONE ACCOUNTING)
STANDALONE_ACCOUNTING_PERMISSIONS: List[PermissionDef] = [
    ("accounting_voucher_create", "Can create accounting vouchers", "Create draft vouchers and their transactions"),
    ("accounting_voucher_authorize", "Can authorize accounting vouchers", "Authorize complete draft vouchers"),
    ("accounting_voucher_post", "Can post accounting vouchers", "Post authorized vouchers to the accounting book"),
    ("accounting_voucher_reverse", "Can reverse accounting vouchers", "Create an append-only reversal of a posted voucher"),
    ("accounting_period_manage", "Can manage accounting periods", "Transition accounting periods and bootstrap the MVP book"),
]

# FEATURE-SPECIFIC PERMISSIONS (CONTACT MODULE)
# ============================================================================

CONTACT_PERMISSIONS: List[PermissionDef] = [
    # Contact Management
    ("contact_view", "Can view contacts", "View contact details"),
    ("contact_create", "Can create contacts", "Create new contacts"),
    ("contact_edit", "Can edit contacts", "Edit contact details"),
    ("contact_delete", "Can delete contacts", "Delete contacts"),
    # Bulk Operations
    ("contact_import", "Can import contacts", "Import contacts from files"),
    ("contact_export", "Can export contacts", "Export contacts to files"),
]

# ============================================================================
# ALL PERMISSIONS COMBINED
# ============================================================================

LOAN_PERMISSIONS: List[PermissionDef] = [
    ("loan_approve", "Can approve loans", "Review and approve loan terms"),
    ("loan_disburse", "Can disburse loans", "Record loan disbursal"),
]

ALL_PERMISSIONS: List[PermissionDef] = (
    WORKSPACE_PERMISSIONS
    + TEAM_PERMISSIONS
    + DATA_PERMISSIONS
    + BILLING_PERMISSIONS
    + REPORT_PERMISSIONS
    + GIRVI_PERMISSIONS
    + DEA_PERMISSIONS
    + STANDALONE_ACCOUNTING_PERMISSIONS
    + CONTACT_PERMISSIONS
    + LOAN_PERMISSIONS
)

# ============================================================================
# ROLE DEFINITIONS
# ============================================================================


class RolePermissions:
    """Maps roles to their default permissions"""

    OWNER = [
        "loan_approve", "loan_disburse",
        # Workspace - Full Access
        "workspace_view",
        "workspace_list",
        "workspace_edit",
        "workspace_settings",
        "workspace_delete",
        "workspace_archive",
        "workspace_transfer",
        # Team - Full Access
        "team_view",
        "team_list",
        "team_invite",
        "team_invite_admin",
        "team_edit",
        "team_remove",
        "team_change_role",
        "team_view_activity",
        # Data - Full Access
        "data_view",
        "data_view_own",
        "data_create",
        "data_edit",
        "data_edit_own",
        "data_delete",
        "data_delete_own",
        "data_export",
        "data_export_bulk",
        "data_import",
        # Billing - Full Access
        "billing_view",
        "billing_history",
        "billing_edit",
        "billing_manage",
        "billing_cancel",
        # Reports - Full Access
        "report_view",
        "report_view_basic",
        "report_create",
        "report_export",
        "report_schedule",
        # Girvi - Full Access
        "girvi_loan_view",
        "girvi_loan_create",
        "girvi_loan_edit",
        "girvi_loan_delete",
        "girvi_loan_approve",
        "girvi_loan_release",
        "girvi_loan_payment",
        "girvi_loan_bulk",
        "girvi_report_view",
        # DEA - Full Access
        "dea_entry_view",
        "dea_entry_create",
        "dea_entry_edit",
        "dea_entry_delete",
        "dea_reconciliation",
        "dea_close_period",
        "dea_report_view",
        "dea_report_export",
        # Standalone accounting - Full operational access
        "accounting_voucher_create",
        "accounting_voucher_authorize",
        "accounting_voucher_post",
        "accounting_voucher_reverse",
        "accounting_period_manage",
        # Contact - Full Access
        "contact_view",
        "contact_create",
        "contact_edit",
        "contact_delete",
        "contact_import",
        "contact_export",
    ]

    ADMIN = [
        "loan_approve", "loan_disburse",
        # Workspace - Edit only
        "workspace_view",
        "workspace_list",
        "workspace_edit",
        "workspace_settings",
        # Team - Manage but not remove admins
        "team_view",
        "team_list",
        "team_invite",
        "team_edit",
        "team_remove",
        "team_change_role",
        # Data - Full Access
        "data_view",
        "data_view_own",
        "data_create",
        "data_edit",
        "data_edit_own",
        "data_delete",
        "data_delete_own",
        "data_export",
        "data_export_bulk",
        "data_import",
        # Billing - View only
        "billing_view",
        "billing_history",
        # Reports - Full Access
        "report_view",
        "report_view_basic",
        "report_create",
        "report_export",
        "report_schedule",
        # Girvi - Full operational access
        "girvi_loan_view",
        "girvi_loan_create",
        "girvi_loan_edit",
        "girvi_loan_delete",
        "girvi_loan_approve",
        "girvi_loan_release",
        "girvi_loan_payment",
        "girvi_loan_bulk",
        "girvi_report_view",
        # DEA - Full operational access
        "dea_entry_view",
        "dea_entry_create",
        "dea_entry_edit",
        "dea_entry_delete",
        "dea_reconciliation",
        "dea_close_period",
        "dea_report_view",
        "dea_report_export",
        # Standalone accounting - Full operational access
        "accounting_voucher_create",
        "accounting_voucher_authorize",
        "accounting_voucher_post",
        "accounting_voucher_reverse",
        "accounting_period_manage",
        # Contact - Full Access
        "contact_view",
        "contact_create",
        "contact_edit",
        "contact_delete",
        "contact_import",
        "contact_export",
    ]

    MEMBER = [
        # Workspace - View only
        "workspace_view",
        "workspace_list",
        # Team - View only
        "team_view",
        "team_list",
        # Data - Standard access
        "data_view",
        "data_view_own",
        "data_create",
        "data_edit",
        "data_edit_own",
        "data_delete_own",
        # Reports - Basic access
        "report_view",
        "report_view_basic",
        "report_export",
        # Girvi - Basic operations
        "girvi_loan_view",
        "girvi_loan_create",
        "girvi_loan_edit",
        "girvi_loan_payment",
        "girvi_report_view",
        # DEA - Basic operations
        "dea_entry_view",
        "dea_entry_create",
        "dea_entry_edit",
        # Standalone accounting - Draft preparation only
        "accounting_voucher_create",
        # Contact - Full Access
        "contact_view",
        "contact_create",
        "contact_edit",
    ]

    VIEWER = [
        # Workspace - View only
        "workspace_view",
        "workspace_list",
        # Team - View only
        "team_view",
        "team_list",
        # Data - View only
        "data_view",
        "data_view_own",
        # Reports - View only
        "report_view",
        "report_view_basic",
        # All modules - View only
        "girvi_loan_view",
        "girvi_report_view",
        "dea_entry_view",
        "contact_view",
    ]


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def get_all_permission_codenames() -> List[str]:
    """Get list of all permission codenames"""
    return [perm[0] for perm in ALL_PERMISSIONS]


def get_permissions_for_role(role_name: str) -> List[str]:
    """Get list of permissions for a given role"""
    role_map = {
        "Owner": RolePermissions.OWNER,
        "Admin": RolePermissions.ADMIN,
        "Member": RolePermissions.MEMBER,
        "Viewer": RolePermissions.VIEWER,
    }
    return role_map.get(role_name, [])


def is_platform_admin(user) -> bool:
    """Return whether the user has platform-level override access."""
    return bool(user and getattr(user, "is_authenticated", False) and getattr(user, "is_superuser", False))


def get_effective_permissions(user, workspace) -> set[str]:
    """Return the effective permission set for a user in a workspace."""
    if not user or not getattr(user, "is_authenticated", False) or workspace is None:
        return set()

    if is_platform_admin(user):
        return set(get_all_permission_codenames()) | {"admin_access"}

    from apps.orgs.models import Membership

    try:
        membership = Membership.objects.select_related("role").get(
            user=user, company=workspace
        )
    except Membership.DoesNotExist:
        return set()

    perms = set(get_permissions_for_role(membership.role.name))
    if hasattr(membership.role, "permissions"):
        perms |= set(membership.role.permissions.values_list("codename", flat=True))

    return perms


def get_workspace_role_name(user, workspace) -> str | None:
    """Return the user's effective role label for the workspace."""
    if not user or not getattr(user, "is_authenticated", False) or workspace is None:
        return None

    if is_platform_admin(user):
        return "Superuser"

    from apps.orgs.models import Membership

    try:
        membership = Membership.objects.select_related("role").get(
            user=user, company=workspace
        )
    except Membership.DoesNotExist:
        return None

    return membership.role.name


def get_permission_display_name(codename: str) -> str:
    """Get display name for a permission codename"""
    for perm in ALL_PERMISSIONS:
        if perm[0] == codename:
            return perm[1]
    return codename


def get_permission_description(codename: str) -> str:
    """Get description for a permission codename"""
    for perm in ALL_PERMISSIONS:
        if perm[0] == codename:
            return perm[2]
    return ""


def get_permissions_by_category() -> Dict[str, List[PermissionDef]]:
    """Get permissions organized by category"""
    return {
        "Workspace": WORKSPACE_PERMISSIONS,
        "Team": TEAM_PERMISSIONS,
        "Data": DATA_PERMISSIONS,
        "Loans": LOAN_PERMISSIONS,
        "Billing": BILLING_PERMISSIONS,
        "Reports": REPORT_PERMISSIONS,
        "Girvi (Loans)": GIRVI_PERMISSIONS,
        "DEA (Accounting)": DEA_PERMISSIONS,
        "Standalone Accounting": STANDALONE_ACCOUNTING_PERMISSIONS,
        "Contacts": CONTACT_PERMISSIONS,
    }
