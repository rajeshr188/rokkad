"""Role settings; existing control-plane policy remains authoritative."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
)
from django.http import Http404
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)

from apps.orgs.models import Company
from apps.orgs.web.access_helpers import _assert_workspace_access


@login_required
def workspace_role_permissions(request, workspace_id, role_id=None):
    """Owner-only editing of one business's stored role grants."""
    from django import forms
    from apps.orgs.access import normalize_action, resolve_workspace_access
    from apps.orgs.models import WorkspaceRole
    from apps.orgs.permissions import ALL_PERMISSIONS
    from apps.orgs.services.workspace_roles import stored_role_codes, update_workspace_role
    from apps.tenancy.context import workspace_context

    workspace = get_object_or_404(Company, pk=workspace_id)
    _assert_workspace_access(request, workspace, required_permissions=set(), allow_platform_admin=True)
    access = resolve_workspace_access(actor=request.user, workspace=workspace)
    if not access.platform_override and workspace.owner_id != request.user.pk:
        raise PermissionDenied("Only the workspace Owner can edit role permissions.")
    with workspace_context(workspace.pk):
        roles = list(WorkspaceRole.objects.filter(workspace=workspace).select_related("role").order_by("role__name"))
        selected = next((row for row in roles if row.role_id == role_id), None)
        if role_id is not None and selected is None:
            raise Http404("Role not found in this workspace.")
        editable = selected is not None and selected.role.name.casefold() != "owner"
        editable_codes = {"workspace_view", "workspace_edit", "workspace_settings",
            "team_view", "team_list", "team_invite", "data_view", "data_create", "data_edit",
            "data_delete", "data_export", "contact_view", "contact_create", "contact_edit",
            "contact_delete", "contact_export", "report_export", "loan_approve", "loan_disburse",
            "loan_repay", "loan_release", "loan_accrue", "loan_capitalize"}
        choices = {}
        for code, label, description in ALL_PERMISSIONS:
            if code not in editable_codes:
                continue
            action = normalize_action(code)
            if action != "workspace.transfer":
                choices.setdefault(action, (label.removeprefix("Can ").capitalize(), description))

        class PermissionForm(forms.Form):
            revision = forms.IntegerField(widget=forms.HiddenInput)
            actions = forms.MultipleChoiceField(required=False,
                choices=[(a, label) for a, (label, _) in choices.items()],
                widget=forms.CheckboxSelectMultiple)

        form = None
        if selected:
            form = PermissionForm(request.POST if request.method == "POST" else None,
                initial={"revision": selected.revision,
                         "actions": sorted({normalize_action(c) for c in stored_role_codes(workspace.pk, role_id) if c in editable_codes})})
        if request.method == "POST":
            if not editable:
                raise PermissionDenied("Select an editable role. Owner permissions are protected.")
            if form.is_valid():
                codes = {c for c in editable_codes if normalize_action(c) in form.cleaned_data["actions"]}
                codes.update(stored_role_codes(workspace.pk, role_id) - editable_codes - {"workspace_transfer"})
                try:
                    update_workspace_role(workspace=workspace, role_id=role_id, permission_codes=codes,
                        revision=form.cleaned_data["revision"], actor=request.user, request=request)
                except ValidationError as exc:
                    form.add_error(None, exc)
                else:
                    messages.success(request, "Role permissions updated for this workspace.")
                    return redirect("workspace_role_permissions_edit", workspace_id=workspace.pk, role_id=role_id)
        return render(request, "company/role_permissions.html", {"workspace": workspace,
            "roles": roles, "selected_role": selected, "form": form, "editable": editable})
