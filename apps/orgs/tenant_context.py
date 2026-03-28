from django_tenants.utils import get_public_schema_name


def resolve_request_workspace(
    request,
    include_public=False,
    allow_profile_fallback=False,
):
    """Resolve workspace with request.tenant as source-of-truth.

    Profile fallback is opt-in and intended only for non-authoritative UX flows
    on public pages (for example: showing a previously selected workspace name).
    """
    public_schema = get_public_schema_name()

    tenant = getattr(request, "tenant", None)
    if tenant is not None:
        if include_public or tenant.schema_name != public_schema:
            return tenant

    if not allow_profile_fallback:
        return None

    user = getattr(request, "user", None)
    if not user or not user.is_authenticated or not hasattr(user, "profile"):
        return None

    workspace = getattr(user.profile, "workspace", None)
    if workspace is None:
        return None

    if include_public or workspace.schema_name != public_schema:
        return workspace

    return None


def is_public_workspace(workspace):
    if workspace is None:
        return False
    return workspace.schema_name == get_public_schema_name()