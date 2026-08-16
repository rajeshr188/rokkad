def resolve_request_workspace(
    request,
    include_public=False,
    allow_profile_fallback=False,
):
    """Resolve Workspace with request.workspace as source-of-truth.

    Profile fallback is opt-in and intended only for non-authoritative UX flows
    on public pages (for example: showing a previously selected workspace name).
    """
    workspace = getattr(request, "workspace", None)
    if workspace is not None:
        return workspace

    if not allow_profile_fallback:
        return None

    user = getattr(request, "user", None)
    if not user or not user.is_authenticated or not hasattr(user, "profile"):
        return None

    return getattr(user.profile, "workspace", None)


def is_public_workspace(workspace):
    if workspace is None:
        return False
    return getattr(workspace, "schema_name", None) == "public"
