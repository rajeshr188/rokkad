def theme_processor(request):
    user = getattr(request, "user", None)
    workspace = getattr(request, "workspace", None) or getattr(
        request, "tenant", None
    )
    if user is not None and user.is_authenticated and workspace is not None:
        return {"theme": workspace.theme, "logo": workspace.logo}
    return {"theme": "", "logo": None}
