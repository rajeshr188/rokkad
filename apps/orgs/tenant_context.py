from django.core.exceptions import ObjectDoesNotExist


def resolve_request_workspace(
    request,
    include_public=False,
):
    """Return only the Workspace explicitly established for this request.

    ``include_public`` remains as a compatibility keyword while public
    Workspace sentinels are retired. Profile preference and ``request.tenant``
    are deliberately not fallback sources.
    """
    workspace = getattr(request, "workspace", None)
    if workspace is None:
        return None
    if not include_public and is_public_workspace(workspace):
        return None
    return workspace


def resolve_preferred_workspace(user):
    """Return a valid navigation preference, never request authority."""
    if not user or not getattr(user, "is_authenticated", False):
        return None
    try:
        workspace = user.profile.workspace
    except (AttributeError, ObjectDoesNotExist):
        return None
    if workspace is None or getattr(workspace, "lifecycle_state", None) != "ACTIVE":
        return None

    from apps.orgs.models import Membership
    from apps.orgs.permissions import is_platform_admin

    if is_platform_admin(user) or Membership.objects.filter(
        user=user,
        company=workspace,
    ).exists():
        return workspace
    return None


def is_public_workspace(workspace):
    if workspace is None:
        return False
    return getattr(workspace, "schema_name", None) == "public"
