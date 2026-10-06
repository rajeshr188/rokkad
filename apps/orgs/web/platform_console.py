"""Global platform oversight and explicitly reviewed lifecycle operations."""
from django import forms
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.shortcuts import render, redirect
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from apps.orgs.models import Company
from apps.orgs.services.platform_console import (
    ATTENTION, console_directory, console_overview, console_workspace, require_console_access,
)
from apps.orgs.services.platform_lifecycle import ACTIONS, confirm_lifecycle, review_lifecycle


class DirectoryFilters(forms.Form):
    query = forms.CharField(required=False, max_length=200, label="Workspace or owner email",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Name, slug or owner email"}))
    lifecycle = forms.ChoiceField(required=False, choices=[("", "All lifecycle states"), *Company.LifecycleState.choices],
        widget=forms.Select(attrs={"class": "form-select"}))
    attention = forms.ChoiceField(required=False, choices=ATTENTION, label="Focus",
        widget=forms.Select(attrs={"class": "form-select"}))
    page = forms.IntegerField(required=False, min_value=1, widget=forms.HiddenInput)


def _authorize(request):
    require_console_access(request.user)
    if getattr(request, "workspace", None) is not None:
        raise PermissionDenied("Open the platform console outside a Workspace.")


@never_cache
@login_required
@require_GET
def overview(request):
    _authorize(request)
    return render(request, "platform_console/overview.html", {
        "section": "overview", **console_overview(actor=request.user)})


@never_cache
@login_required
@require_GET
def directory(request):
    _authorize(request)
    filters = DirectoryFilters(request.GET)
    context = {"section": "directory", "filters": filters}
    if filters.is_valid():
        context.update(console_directory(actor=request.user, **filters.cleaned_data))
    return render(request, "platform_console/directory.html", context, status=200 if filters.is_valid() else 400)


@never_cache
@login_required
@require_GET
def workspace(request, slug):
    _authorize(request)
    from apps.orgs.web.storage import platform_workspace_usage
    context = console_workspace(actor=request.user, slug=slug, invitation_page=request.GET.get("page", 1))
    return render(request, "platform_console/workspace.html", {"section": "directory",
        **context, **platform_workspace_usage(actor=request.user, workspace=context["workspace"])})


@never_cache
@login_required
@require_GET
def guide(request):
    _authorize(request)
    return render(request, "platform_console/guide.html", {"section": "guide"})


class LifecycleConfirmation(forms.Form):
    reason = forms.CharField(max_length=1000, widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        help_text="Explain the operational reason. Do not include customer records or secrets.")
    confirmation = forms.CharField(max_length=200, label="Type the workspace slug to confirm",
        widget=forms.TextInput(attrs={"class": "form-control", "autocomplete": "off"}))
    acknowledged = forms.BooleanField(label="I have reviewed the workspace, owner and access impact.",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}))
    token = forms.CharField(widget=forms.HiddenInput)


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def lifecycle(request, slug, action):
    _authorize(request)
    if action not in ACTIONS:
        raise Http404
    status, error = 200, None
    try:
        review = review_lifecycle(actor=request.user, slug=slug, action=action)
    except ValidationError as exc:
        return render(request, "platform_console/lifecycle.html", {
            "section": "directory", "slug": slug, "unavailable": exc.messages}, status=409)
    form = LifecycleConfirmation(request.POST if request.method == "POST" else None,
                                 initial={"token": review["review_token"]})
    if request.method == "POST":
        if form.is_valid():
            try:
                confirm_lifecycle(actor=request.user, slug=slug, action=action,
                    token=form.cleaned_data["token"], reason=form.cleaned_data["reason"],
                    confirmation=form.cleaned_data["confirmation"], request=request)
            except ValidationError as exc:
                # Renew the review, retain the reason, but require fresh confirmation.
                error, status = exc.messages, 409
                try:
                    review = review_lifecycle(actor=request.user, slug=slug, action=action)
                except ValidationError as changed:
                    return render(request, "platform_console/lifecycle.html", {
                        "section": "directory", "slug": slug, "unavailable": changed.messages}, status=409)
                form = LifecycleConfirmation(initial={"token": review["review_token"],
                                                       "reason": form.cleaned_data["reason"]})
            else:
                messages.success(request, "Workspace suspended." if action == "suspend" else
                    "Workspace restored. Its existing subscription access applies; no trial or paid period was extended.")
                return redirect("platform_workspace", slug=slug)
        else:
            status = 400
    return render(request, "platform_console/lifecycle.html", {
        "section": "directory", **review, "form": form, "review_errors": error}, status=status)
