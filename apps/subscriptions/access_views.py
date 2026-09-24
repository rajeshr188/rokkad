from django import forms
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views import View

from apps.orgs.permissions import is_platform_admin
from apps.orgs.tenant_context import resolve_request_workspace
from .access_policy import record_access_decision, workspace_activity
from .models import Plan, WorkspaceAccessDecision


class AccessDecisionForm(forms.Form):
    mode = forms.ChoiceField(choices=WorkspaceAccessDecision.Mode.choices)
    expires_at = forms.DateTimeField(required=False, widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"))
    reason = forms.CharField(max_length=1000, widget=forms.Textarea(attrs={"rows": 3}))
    plan = forms.ModelChoiceField(queryset=Plan.objects.filter(is_active=True), required=False,
        help_text="Required only for normal access when the workspace has no subscription. Existing subscription entitlements are preserved.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-select" if isinstance(field.widget, forms.Select) else "form-control"


class WorkspaceAccessControlsView(LoginRequiredMixin, View):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not is_platform_admin(request.user):
            raise PermissionDenied("Only platform administrators can manage access extensions.")
        self.workspace = resolve_request_workspace(request)
        if self.workspace is None:
            raise PermissionDenied("Select an explicit workspace.")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        return self.page(request, AccessDecisionForm())

    def post(self, request, *args, **kwargs):
        form = AccessDecisionForm(request.POST)
        if form.is_valid():
            try:
                record_access_decision(workspace=self.workspace, actor=request.user, **form.cleaned_data)
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                messages.success(request, "Access decision recorded. Payment history and workspace lifecycle are unchanged.")
                return redirect("workspace_subscriptions:access-controls", workspace_slug=self.workspace.slug)
        return self.page(request, form)

    def page(self, request, form):
        return render(request, "subscriptions/access_controls.html", {
            "form": form, "activity": workspace_activity(self.workspace),
            "decisions": WorkspaceAccessDecision.objects.filter(workspace=self.workspace).select_related("actor")[:50],
            "access_timezone": timezone.get_current_timezone_name(),
        })
