"""CSRF-protected, signed review for setup-authorized series status controls."""
import uuid

from django import forms
from django.core import signing
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from apps.tenant_apps.loans.access import loans_workspace_required
from apps.tenant_apps.loans.models import KhataSeries
from apps.tenant_apps.loans.services.action_access import require_setup_administration
from apps.tenant_apps.loans.services import khata_series as service
from .khata_views import _private

SALT = "loans.khata.series-status.1"


class StatusForm(forms.Form):
    request_key = forms.UUIDField(widget=forms.HiddenInput())
    to_status = forms.ChoiceField(label="New lending status", widget=forms.Select(attrs={"class": "form-select"}))
    reason = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}))

    def __init__(self, *args, series, replaying=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["to_status"].choices = (("ACTIVE", "Resume"), ("PAUSED", "Pause"), ("RETIRED", "Retire")) if replaying else service.available_transitions(series)


@loans_workspace_required
@never_cache
@require_http_methods(["GET", "POST"])
def status(request, pk):
    workspace = request.loans_workspace
    require_setup_administration(workspace.pk, request.user)
    series = get_object_or_404(KhataSeries, workspace=workspace, pk=pk)
    confirming = request.method == "POST" and "review_token" in request.POST
    review = None
    source = request.POST if request.method == "POST" else None
    error = None
    if confirming:
        try:
            review = signing.loads(request.POST["review_token"], salt=SALT, max_age=1800)
            if (review["workspace"] != workspace.pk or review["actor"] != request.user.pk
                    or review["series"] != series.pk or review["date"] != timezone.localdate().isoformat()):
                raise signing.BadSignature()
            source = review["instructions"]
        except (signing.BadSignature, KeyError, TypeError):
            error = "The review expired or changed; refresh and review again."
            source = None
            confirming = False
    form = StatusForm(source, series=series, replaying=confirming, initial=dict(request_key=uuid.uuid4()))
    if source is not None and form.is_valid():
        try:
            if confirming and request.POST.get("edit") != "1":
                service.change_status(workspace=workspace, actor=request.user, series_id=series.pk,
                    review_hash=review["review_hash"], **form.cleaned_data)
                return redirect("workspace_loans:khata_setup", workspace_slug=workspace.slug)
            if not confirming:
                preview = service.preview(workspace=workspace, actor=request.user, series_id=series.pk)
                instructions = {k: str(v) for k, v in form.cleaned_data.items()}
                token = signing.dumps(dict(workspace=workspace.pk, actor=request.user.pk, series=series.pk,
                    date=timezone.localdate().isoformat(), instructions=instructions, review_hash=preview["review_hash"]), salt=SALT, compress=True)
                return _private(render(request, "loans/khata/series_status.html", dict(series=series, form=form,
                    review_token=token, new_status=dict(form.fields["to_status"].choices)[form.cleaned_data["to_status"]],
                    reason=form.cleaned_data["reason"])))
        except (ValueError, ValidationError) as exc:
            form.add_error(None, str(exc))
    return _private(render(request, "loans/khata/series_status.html", dict(series=series, form=form, form_error=error)))
