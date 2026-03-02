"""
Navigation structure and menu configuration.
Defines all available navigation items with their properties.
"""

# Navigation structure for authenticated users
NAVIGATION_STRUCTURE = {
    "main": [
        {
            "id": "dashboard",
            "label": "Dashboard",
            "url_name": "dashboard",
            "icon": "house-fill",
            "section": "core",
            "required_permission": "workspace_view",
        },
        {
            "id": "workspace",
            "label": "Workspace",
            "icon": "diagram-3-fill",
            "section": "core",
            "required_permission": "workspace_view",
            "submenu": [
                {
                    "id": "workspace-dashboard",
                    "label": "Overview",
                    "url_name": "company_dashboard",
                    "required_permission": "workspace_view",
                },
                {
                    "id": "workspace-team",
                    "label": "Team",
                    "url_name": "orgs_membership_list",
                    "required_permission": "team_view",
                },
                {
                    "id": "workspace-settings",
                    "label": "Settings",
                    "url_name": "company_update",
                    "required_permission": "workspace_edit",
                },
            ],
        },
    ],
    "data": [
        {
            "id": "data-header",
            "label": "Data",
            "section": "data",
            "is_header": True,
        },
        {
            "id": "girvi",
            "label": "Loans (गिरवी)",
            "url_name": "girvi:loan_list",
            "icon": "cash-coin",
            "section": "data",
            "required_permission": "data_view",
        },
        {
            "id": "sales",
            "label": "Sales",
            "url_name": "sales:invoice_list",
            "icon": "graph-up-arrow",
            "section": "data",
            "required_permission": "data_view",
        },
        {
            "id": "purchase",
            "label": "Purchase",
            "url_name": "purchase:invoice_list",
            "icon": "cart-fill",
            "section": "data",
            "required_permission": "data_view",
        },
        {
            "id": "accounting",
            "label": "Accounting (DEA)",
            "url_name": "dea_home",
            "icon": "calculator",
            "section": "data",
            "required_permission": "data_view",
        },
        {
            "id": "contacts",
            "label": "Contacts",
            "url_name": "contact:contact_list",
            "icon": "people-fill",
            "section": "data",
            "required_permission": "data_view",
        },
    ],
    "admin": [
        {
            "id": "admin-header",
            "label": "Administration",
            "section": "admin",
            "is_header": True,
        },
        {
            "id": "billing",
            "label": "Billing & Subscription",
            "url_name": "subscriptions:dashboard",
            "icon": "credit-card",
            "section": "admin",
            "required_permission": "billing_view",
        },
        {
            "id": "rates",
            "label": "Rates & Settings",
            "url_name": "rates_list",
            "icon": "sliders",
            "section": "admin",
            "required_permission": "workspace_edit",
        },
    ],
}

# Navigation items for unauthenticated users
PUBLIC_NAVIGATION = [
    {
        "id": "pricing",
        "label": "Pricing",
        "url": "/pricing/",
        "icon": "tag-fill",
    },
    {
        "id": "docs",
        "label": "Documentation",
        "url": "/docs/",
        "icon": "book-fill",
    },
    {
        "id": "contact",
        "label": "Contact",
        "url": "/contact/",
        "icon": "envelope-fill",
    },
]

# User menu items (top right dropdown)
USER_MENU_ITEMS = [
    {
        "id": "profile",
        "label": "My Profile",
        "url_name": "profile",
        "icon": "person-circle",
    },
    {
        "id": "preferences",
        "label": "Preferences",
        "url_name": "preferences",
        "icon": "gear-fill",
    },
    {
        "id": "workspaces",
        "label": "My Workspaces",
        "url_name": "orgs_company_list",
        "icon": "diagram-3-fill",
    },
    {
        "id": "logout",
        "label": "Logout",
        "url_name": "account_logout",
        "icon": "box-arrow-right",
        "divider_above": True,
    },
]


def get_navigation_for_user(user, workspace=None, permissions=None):
    """
    Filter navigation structure based on user permissions.

    Args:
        user: Django user object
        workspace: Current workspace
        permissions: Set of permission codenames user has

    Returns:
        Filtered navigation structure
    """
    if not permissions:
        permissions = set()

    def is_item_visible(item):
        """Check if navigation item should be visible to user"""
        # Header items always visible
        if item.get("is_header"):
            return True

        # Check required permission
        required_perm = item.get("required_permission")
        if required_perm and required_perm not in permissions:
            return False

        return True

    def filter_submenu(submenu):
        """Filter submenu items"""
        return [item for item in submenu if is_item_visible(item)]

    filtered_nav = {}

    for section, items in NAVIGATION_STRUCTURE.items():
        visible_items = []

        for item in items:
            if is_item_visible(item):
                # Filter submenu if exists
                if "submenu" in item:
                    item_copy = item.copy()
                    item_copy["submenu"] = filter_submenu(item["submenu"])
                    # Only include item if it has submenu items or no subitems
                    if item_copy["submenu"] or not item.get("submenu"):
                        visible_items.append(item_copy)
                else:
                    visible_items.append(item)

        if visible_items:
            filtered_nav[section] = visible_items

    return filtered_nav
