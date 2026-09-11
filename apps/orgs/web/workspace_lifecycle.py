"""Workspace lifecycle views; existing policy and services remain authoritative."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.orgs.forms import ArchiveWorkspaceForm
from apps.orgs.models import Company
from apps.orgs.permissions import is_platform_admin
from apps.orgs.services import control_plane
from apps.orgs.web.access_helpers import _assert_workspace_access, _assert_owner_access


@login_required
def workspace_delete(request, workspace_id=None, company_id=None):
    """
    Archive a workspace while preserving its tenant schema and all business data.

    The legacy route name is retained for compatibility. Requires the
    workspace_delete permission and Owner access.
    """
    workspace_id = workspace_id or company_id
    if workspace_id is None:
        raise Http404("Workspace ID is required")

    company = get_object_or_404(Company, id=workspace_id)
    _assert_workspace_access(
        request,
        company,
        required_permissions={"workspace_delete"},
        allow_platform_admin=True,
    )

    _assert_owner_access(request, company, allow_platform_admin=True)
    form = ArchiveWorkspaceForm(
        request.POST if request.method == "POST" else None,
        workspace=company,
    )
    if request.method == "POST" and form.is_valid():
        control_plane.archive_workspace(
            company=company,
            actor=request.user,
            request=request,
            reason=f"Owner confirmed archive of {company.name}",
        )

        # Do not leave the actor's profile pointing at an inaccessible tenant.
        if getattr(request.user.profile, "workspace", None) == company:
            request.user.profile.workspace = None
            request.user.profile.save(update_fields=["workspace"])

        messages.success(
            request,
            f"{company.name} was archived. Its schema and business records were preserved.",
        )
        return redirect("archived_workspaces")

    return render(
        request,
        "company/company_delete_confirm.html",
        {"company": company, "workspace": company, "form": form},
    )


@login_required
def archived_workspaces(request):
    """List archived workspaces that the actor is allowed to restore."""
    workspaces = Company.all_objects.filter(
        lifecycle_state=Company.LifecycleState.ARCHIVED
    ).exclude(
        schema_name="public"
    )
    if not is_platform_admin(request.user):
        workspaces = workspaces.filter(owner=request.user)
    workspaces = workspaces.select_related("owner").order_by("-updated_at", "name")
    return render(
        request,
        "company/archived_workspaces.html",
        {"archived_workspaces": workspaces},
    )


@require_POST
@login_required
def workspace_restore(request, workspace_id):
    """Restore one archived workspace; only its Owner or platform admin may act."""
    company = get_object_or_404(
        Company.all_objects,
        id=workspace_id,
        lifecycle_state=Company.LifecycleState.ARCHIVED,
    )
    if request.user != company.owner and not is_platform_admin(request.user):
        raise PermissionDenied("Only the workspace owner can restore this workspace")

    control_plane.restore_workspace(
        company=company,
        actor=request.user,
        request=request,
    )
    messages.success(request, f"{company.name} was restored.")
    return redirect("archived_workspaces")


@require_POST
@login_required
def workspace_lifecycle_transition(request, workspace_id, target_state):
    """Apply an explicitly authorized operational lifecycle transition."""
    company = get_object_or_404(Company.all_objects, id=workspace_id)
    reason = (request.POST.get("reason") or "").strip()
    try:
        updated = control_plane.transition_workspace_lifecycle(
            workspace=company,
            target_state=target_state.upper(),
            actor=request.user,
            reason=reason,
            request=request,
        )
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("archived_workspaces")

    messages.success(
        request,
        f"{updated.name} is now {updated.get_lifecycle_state_display().lower()}.",
    )
    return redirect("archived_workspaces")
