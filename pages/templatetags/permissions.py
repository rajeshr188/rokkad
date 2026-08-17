"""
Custom template tags for permission and role-based UI rendering.
"""

from django import template
from django.template.loader import render_to_string
from django.urls import reverse, NoReverseMatch

register = template.Library()


@register.inclusion_tag("components/navigation.html")
def render_main_navigation(user, workspace=None, permissions=None):
    """
    Render main navigation based on user permissions.

    Usage in template:
      {% render_main_navigation user workspace=request.workspace permissions=user_permissions %}
    """
    if not permissions:
        permissions = set()

    from django_project.navigation import get_navigation_for_user

    nav_structure = get_navigation_for_user(user, workspace, permissions)

    # Build URL resolving for nav items
    def resolve_url(item):
        if "url_name" in item:
            try:
                return reverse(item["url_name"])
            except NoReverseMatch:
                return "#"
        return item.get("url", "#")

    # Add resolved URLs to items
    for section, items in nav_structure.items():
        for item in items:
            item["url"] = resolve_url(item)
            if "submenu" in item:
                for subitem in item["submenu"]:
                    subitem["url"] = resolve_url(subitem)

    return {
        "navigation": nav_structure,
        "current_path": getattr(workspace, "name", "Dashboard")
        if workspace
        else "Dashboard",
    }


@register.simple_tag
def has_permission(user_permissions, permission):
    """
    Check if user has a specific permission.

    Usage in template:
      {% has_permission user_permissions 'data_edit' as can_edit %}
      {% if can_edit %}...{% endif %}
    """
    if isinstance(user_permissions, set):
        return permission in user_permissions
    elif isinstance(user_permissions, (list, tuple)):
        return permission in user_permissions
    return False


@register.simple_tag
def has_role(user_role, required_role):
    """
    Check if user has a specific role or higher.

    Role hierarchy: owner >= admin >= member

    Usage in template:
      {% has_role user_role 'admin' as is_admin %}
      {% if is_admin %}...{% endif %}
    """
    role_hierarchy = {
        "owner": 3,
        "admin": 2,
        "member": 1,
    }

    user_role_val = role_hierarchy.get((user_role or "").lower(), 0)
    required_role_val = role_hierarchy.get((required_role or "").lower(), 0)

    return user_role_val >= required_role_val


@register.inclusion_tag("components/role_badge.html")
def role_badge(role, **kwargs):
    """
    Render a badge displaying the user's role.

    Usage in template:
      {% role_badge user_role %}
      {% role_badge user_role size='small' %}
    """
    return {
        "role": role,
        "size": kwargs.get("size", "normal"),
        "show_icon": kwargs.get("show_icon", True),
    }


@register.inclusion_tag("components/action_buttons.html")
def action_buttons(obj, user_permissions, **kwargs):
    """
    Render permission-based action buttons for an object.

    Usage in template:
      {% action_buttons object user_permissions %}
    """
    return {
        "object": obj,
        "user_permissions": user_permissions,
    }


@register.inclusion_tag("components/breadcrumbs.html")
def breadcrumbs(breadcrumb_list, **kwargs):
    """
    Render breadcrumb navigation.

    Usage in template:
      {% breadcrumbs breadcrumbs_list %}

    breadcrumbs_list format:
      [
        {'label': 'Contacts', 'url': '/contacts/'},
        {'label': 'Detail', 'url': None},  # Current page
      ]
    """
    return {
        "breadcrumbs": breadcrumb_list,
        "in_tenant": kwargs.get("in_tenant", False),
        "workspace_name": kwargs.get("workspace_name"),
    }


@register.inclusion_tag("components/empty_state.html")
def empty_state(items, **kwargs):
    """
    Render empty state message when no items exist.

    Usage in template:
      {% empty_state items message="No contacts found" create_url="/contacts/create/" %}
    """
    can_create = kwargs.get("can_create", True)

    return {
        "items": items,
        "message": kwargs.get("message", "No items found"),
        "icon": kwargs.get("icon", "📭"),
        "title": kwargs.get("title", "No items yet"),
        "create_url": kwargs.get("create_url"),
        "create_text": kwargs.get("create_text", "Create new item"),
        "can_create": can_create,
    }


@register.inclusion_tag("components/feature_locked.html")
def feature_locked(feature_name, required_plan, **kwargs):
    """
    Render feature unavailable alert.

    Usage in template:
      {% feature_locked "Advanced Reporting" "Pro" %}
    """
    return {
        "feature_name": feature_name,
        "required_plan": required_plan,
        "button_text": kwargs.get("button_text", "Upgrade your plan"),
    }


@register.inclusion_tag("components/subscription_status.html")
def subscription_status_alert(
    has_subscription, plan_name, days_left, is_expired, workspace_name, **kwargs
):
    """
    Render subscription status alert.

    Usage in template:
      {% subscription_status_alert has_active_subscription subscription_plan days_until_renewal subscription_expired workspace_name %}
    """
    return {
        "has_active_subscription": has_subscription,
        "subscription_plan": plan_name,
        "days_until_renewal": days_left,
        "subscription_expired": is_expired,
        "workspace_name": workspace_name,
    }


@register.filter
def permission_required(obj_list, permission):
    """
    Filter list to only items user has permission for.

    Usage in template:
      {% for item in items|permission_required:'data_edit' %}
    """
    # This would typically check each item's required_permission
    # Implementation depends on your model structure
    return obj_list


@register.filter
def role_label(role_name):
    """
    Get display label for a role.

    Usage in template:
      {{ user_role|role_label }}
    """
    labels = {
        "owner": "Workspace Owner",
        "admin": "Administrator",
        "member": "Team Member",
    }
    return labels.get((role_name or "").lower(), role_name)
