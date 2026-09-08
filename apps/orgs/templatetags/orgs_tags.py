"""
Custom template tags for workspace/organization management.

Provides permission checking, role badge rendering, and sidebar generation.
"""

from django import template
from django.utils.safestring import mark_safe
from django.contrib.auth.models import Permission
from django.core.cache import cache

register = template.Library()


@register.filter
def has_permission(user, permission_string):
    """
    Check if user has a specific permission.

    Usage: {% if request.user|has_permission:"app.permission_name" %}

    Args:
        user: User object
        permission_string: Format "app_label.permission_codename" (e.g., "company.manage_members")

    Returns:
        bool: True if user has permission, False otherwise
    """
    if not user or not user.is_authenticated:
        return False

    # Superusers have all permissions
    if user.is_superuser:
        return True

    # For authenticated users, check the permission
    try:
        if "." in permission_string:
            app_label, codename = permission_string.rsplit(".", 1)
        else:
            # If no dot, assume it's just the codename and check against all apps
            return user.has_perm(permission_string)

        # Check if user has this specific permission
        return user.has_perm(f"{app_label}.{codename}")
    except Exception:
        # If any error occurs, deny access
        return False


@register.filter
def user_workspace_role(user, workspace):
    """
    Get user's role in a specific workspace.

    Usage: {% for workspace in workspaces %}{{ user|user_workspace_role:workspace }}{% endfor %}

    Args:
        user: User object
        workspace: Workspace/Company object

    Returns:
        str: Role name (e.g., "admin", "manager", "member") or None
    """
    if not user or not workspace:
        return None

    # Try to get user's membership in this workspace
    try:
        from apps.orgs.models import Membership

        membership = Membership.objects.get(user=user, company=workspace)
        return membership.role
    except Exception:
        return None


@register.filter
def workspace_member_count(workspace):
    """
    Get count of active members in a workspace.

    Usage: {{ workspace|workspace_member_count }}

    Args:
        workspace: Workspace/Company object

    Returns:
        int: Number of members
    """
    if not workspace:
        return 0

    cache_key = f"workspace_members_{workspace.id}"
    count = cache.get(cache_key)

    if count is None:
        try:
            from apps.orgs.models import Membership

            count = Membership.objects.filter(
                company=workspace, status="active"
            ).count()
            cache.set(cache_key, count, 300)  # Cache for 5 minutes
        except Exception:
            count = 0

    return count


@register.filter
def pending_invite_count(workspace, user):
    """
    Get count of pending invitations in a workspace for a user.

    Usage: {{ workspace|pending_invite_count:user }}

    Args:
        workspace: Workspace/Company object
        user: User object

    Returns:
        int: Number of pending invitations
    """
    if not workspace or not user:
        return 0

    try:
        from apps.orgs.models import Membership

        count = Membership.objects.filter(company=workspace, status="pending").count()
        return count
    except Exception:
        return 0


@register.inclusion_tag("components/team/role_badge.html")
def render_role_badge(role, size="normal"):
    """
    Render a role badge with appropriate color and icon.

    Usage: {% render_role_badge role='admin' %}

    Args:
        role: Role name (admin, manager, member, guest)
        size: Badge size (normal, sm, lg)

    Returns:
        dict: Context for role_badge.html template
    """
    return {
        "role": role,
        "size": size,
    }


@register.inclusion_tag("components/common/empty_state.html")
def empty_state(
    title=None,
    message=None,
    icon=None,
    action_label=None,
    action_url=None,
    action_icon=None,
):
    """
    Render an empty state placeholder.

    Usage: {% empty_state title='No members' message='Add your first team member' action_label='Invite' action_url='...' %}

    Args:
        title: Empty state title
        message: Empty state message
        icon: Bootstrap icon name (without 'bi-' prefix)
        action_label: Button text
        action_url: Button link
        action_icon: Button icon (without 'bi-' prefix)

    Returns:
        dict: Context for empty_state.html template
    """
    return {
        "title": title or "No items",
        "message": message,
        "icon": icon or "inbox",
        "action_label": action_label,
        "action_url": action_url,
        "action_icon": action_icon,
    }


@register.inclusion_tag("components/common/alert.html")
def alert(content=None, message=None, type="info", details=None):
    """
    Render an alert message.

    Usage: {% alert content='Success!' type='success' %}

    Args:
        content: Alert message text
        message: Alternative to content
        type: Alert type (success, danger, warning, info)
        details: Optional additional details

    Returns:
        dict: Context for alert.html template
    """
    return {
        "content": content or message,
        "type": type,
        "details": details,
    }


@register.inclusion_tag("components/common/loading.html")
def loading_spinner(text="Loading..."):
    """
    Render a loading spinner.

    Usage: {% loading_spinner %}

    Args:
        text: Loading text to display

    Returns:
        dict: Context for loading.html template
    """
    return {
        "text": text,
    }


@register.inclusion_tag("components/common/card.html")
def card(title=None, header=None, content=None, footer=None, class_names=None):
    """
    Render a card component.

    Usage: {% card title='Card Title' %}Content here{% endcard %}

    Args:
        title: Card title
        header: Custom header content
        content: Card body content (use as block if not specified)
        footer: Card footer content
        class_names: Additional CSS classes

    Returns:
        dict: Context for card.html template
    """
    return {
        "title": title,
        "header": header,
        "content": content,
        "footer": footer,
        "class": class_names,
    }


@register.inclusion_tag(
    "components/permissions/action_buttons.html", takes_context=True
)
def action_buttons(context, object=None, actions=None):
    """
    Render permission-gated action buttons.

    Usage: {% action_buttons object=member actions='edit,delete' %}

    Args:
        context: Template context
        object: Optional target object for button context
        actions: List/tuple of action dicts OR comma-separated names (edit,delete,...)

    Returns:
        dict: Context for action_buttons.html template
    """
    request = context.get("request")

    # If explicit action dicts are provided, pass through unchanged.
    if isinstance(actions, (list, tuple)):
        normalized_actions = actions
    elif isinstance(actions, str):
        action_names = [item.strip() for item in actions.split(",") if item.strip()]

        model_name = ""
        app_label = "orgs"
        if object is not None and getattr(object, "_meta", None):
            model_name = object._meta.model_name
            app_label = object._meta.app_label

        normalized_actions = []
        for action_name in action_names:
            permission_codename = (
                f"change_{model_name}"
                if action_name == "edit" and model_name
                else action_name
            )
            if action_name == "delete" and model_name:
                permission_codename = f"delete_{model_name}"
            elif action_name == "view" and model_name:
                permission_codename = f"view_{model_name}"
            elif action_name == "add" and model_name:
                permission_codename = f"add_{model_name}"

            normalized_actions.append(
                {
                    "label": action_name.replace("_", " ").title(),
                    "style": "primary"
                    if action_name in ("edit", "view")
                    else "secondary",
                    "icon": "pencil" if action_name == "edit" else "gear",
                    "url": "#",
                    "title": action_name.replace("_", " ").title(),
                    "permission": f"{app_label}.{permission_codename}",
                }
            )
    else:
        normalized_actions = []

    return {
        "request": request,
        "object": object,
        "actions": normalized_actions,
    }


@register.inclusion_tag("components/permissions/feature_gate.html")
def feature_gate(
    feature_name=None, required_plan="Pro", button_text="Upgrade your plan"
):
    """
    Render a feature-gate banner when a feature is unavailable.

    Usage: {% feature_gate feature_name='Advanced Reports' required_plan='Pro' %}

    Args:
        feature_name: Display name of the blocked feature
        required_plan: Minimum required plan name
        button_text: CTA label

    Returns:
        dict: Context for feature_gate.html template
    """
    return {
        "feature_name": feature_name or "This feature",
        "required_plan": required_plan,
        "button_text": button_text,
    }


@register.simple_tag(takes_context=True)
def render_sidebar(context):
    """
    Render workspace sidebar with permission-filtered navigation.

    Usage: {% render_sidebar %}

    Args:
        context: Template context (for current user and workspace)

    Returns:
        str: Rendered sidebar HTML
    """
    request = context.get("request")
    user = request.user if request else None

    if not user or not user.is_authenticated:
        return ""

    # Return a simple sidebar without trying to render templates
    # This avoids circular template loading
    workspace = (
        getattr(user.profile, "workspace", None) if hasattr(user, "profile") else None
    )

    if not workspace:
        return '<div class="sidebar-wrapper"><p class="text-muted">No workspace selected</p></div>'

    # Build navigation HTML directly to avoid template rendering issues
    nav_html = """
    <div class="sidebar-wrapper">
        <div class="sidebar-sticky">
            <div class="mb-4 p-3 bg-light rounded border-bottom">
                <h6 class="mb-2 text-uppercase small text-muted">Current Workspace</h6>
                <h5 class="mb-0">
                    <i class="bi bi-briefcase-fill text-primary"></i>
                    {workspace_name}
                </h5>
            </div>
            <nav class="nav flex-column gap-2">
                <a class="nav-link" href="/workspace/list/">
                    <i class="bi bi-speedometer2"></i> Dashboard
                </a>
            </nav>
        </div>
    </div>
    """.format(
        workspace_name=workspace.name
    )

    return mark_safe(nav_html)


@register.simple_tag(takes_context=True)
def render_breadcrumbs(context, breadcrumbs=None):
    """
    Render breadcrumb navigation.

    Usage: {% render_breadcrumbs breadcrumbs %}

    Breadcrumbs should be a list of tuples: [(label, url), (label, url), (active_label, None)]

    Args:
        context: Template context
        breadcrumbs: List of (label, url) tuples or (label, None) for active item

    Returns:
        str: Rendered breadcrumbs HTML
    """
    if not breadcrumbs:
        return ""

    # Build breadcrumbs HTML directly to avoid template rendering issues
    html_parts = ['<nav aria-label="breadcrumb"><ol class="breadcrumb mb-0">']
    html_parts.append(
        '<li class="breadcrumb-item"><a href="/"><i class="bi bi-house-door"></i> Home</a></li>'
    )

    for label, url in breadcrumbs:
        if url:
            html_parts.append(
                f'<li class="breadcrumb-item"><a href="{url}">{label}</a></li>'
            )
        else:
            html_parts.append(
                f'<li class="breadcrumb-item active" aria-current="page">{label}</li>'
            )

    html_parts.append("</ol></nav>")

    return mark_safe("".join(html_parts))


@register.filter
def is_admin(user, workspace):
    """
    Check if user is admin in workspace.

    Usage: {% if user|is_admin:workspace %}...{% endif %}

    Args:
        user: User object
        workspace: Workspace/Company object

    Returns:
        bool: True if user is admin in workspace
    """
    return user_workspace_role(user, workspace) == "admin"


@register.filter
def is_manager(user, workspace):
    """
    Check if user is manager (or admin) in workspace.

    Usage: {% if user|is_manager:workspace %}...{% endif %}

    Args:
        user: User object
        workspace: Workspace/Company object

    Returns:
        bool: True if user is manager or admin in workspace
    """
    role = user_workspace_role(user, workspace)
    return role in ("admin", "manager")


@register.filter
def date_since(value):
    """
    Format a date as time since (e.g., "3 days ago").

    Usage: {{ timestamp|date_since }}

    Args:
        value: datetime object

    Returns:
        str: Formatted time since string
    """
    from django.utils.timesince import timesince

    if value:
        return timesince(value) + " ago"
    return ""


# Template context processors
def workspace_context(request):
    """
    Add workspace-related context to all templates.

    Adds:
    - current_workspace: User's selected workspace
    - user_workspaces: All workspaces user belongs to
    - user_permissions: Set of user's permissions in current workspace
    """
    user = request.user if hasattr(request, "user") else None

    if not user or not user.is_authenticated:
        return {}

    try:
        from apps.orgs.models import Company, Membership

        # Get current workspace from user profile or session
        current_workspace = getattr(user.profile, "workspace", None)
        if not current_workspace and "workspace_id" in request.session:
            current_workspace = Company.objects.get(id=request.session["workspace_id"])

        # Get all user's workspaces
        user_workspaces = Company.objects.filter(
            membership__user=user, membership__status="active"
        ).distinct()

        # Get user's permissions in current workspace
        user_permissions = set()
        if current_workspace:
            user_permissions = set(
                user.user_permissions.filter(
                    content_type__app_label="orgs"
                ).values_list("codename", flat=True)
            )

        return {
            "current_workspace": current_workspace,
            "user_workspaces": user_workspaces,
            "user_permissions": user_permissions,
        }
    except Exception:
        return {}


@register.simple_tag(takes_context=True)
def navigation_actions(context):
    """Normalize the request-scoped permission context for navigation only."""
    from apps.orgs.access import normalize_action

    request = context.get("request")
    if not getattr(request, "workspace", None):
        return frozenset()
    return frozenset(normalize_action(code) for code in context.get("user_permissions", ()))
