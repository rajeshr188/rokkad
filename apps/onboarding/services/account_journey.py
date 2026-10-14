"""Account-to-business navigation hints; never establish Workspace authority."""
from allauth.account.models import EmailAddress
from django.urls import reverse

from apps.orgs.models import Company, Membership
from apps.orgs.tenant_context import resolve_preferred_workspace


def owner_setup_workspace(user, *, slug=None, remembered=None):
    if not user or not user.is_authenticated:
        return None
    if slug and len(slug) <= 63:
        workspace = Company.all_objects.filter(slug=slug, owner=user,
            lifecycle_state=Company.LifecycleState.ACTIVE).first()
    elif isinstance(remembered, dict) and remembered.get("user_id") == user.pk and isinstance(remembered.get("workspace_id"), int):
        workspace = Company.all_objects.filter(pk=remembered.get("workspace_id"), owner=user,
            lifecycle_state=Company.LifecycleState.ACTIVE).first()
    else:
        workspace = resolve_preferred_workspace(user)
    if (workspace is None or workspace.owner_id != user.pk
            or not Membership.objects.filter(user=user, company=workspace).exists()):
        return None
    return workspace


def owner_business_setup_url(user, *, workspace=None):
    """A currently owned, active membership may supply a canonical return link."""
    workspace = workspace or owner_setup_workspace(user)
    if workspace is None:
        return None
    return reverse("workspace_slug_settings_setup", kwargs={"workspace_slug": workspace.slug})


def account_journey(user, *, request=None):
    if not user or not user.is_authenticated:
        return None
    values = request.POST if request and request.method == "POST" else request.GET if request else {}
    remembered = request.session.get("onboarding_verification_return") if request else None
    workspace = owner_setup_workspace(user, slug=values.get("setup_workspace"), remembered=remembered)
    return {
        "email": user.email,
        "verified": bool(user.email and EmailAddress.objects.filter(
            user=user, email__iexact=user.email, verified=True,
        ).exists()),
        "setup_url": owner_business_setup_url(user, workspace=workspace) if workspace else None,
        "workspace_slug": workspace.slug if workspace else "",
    }
