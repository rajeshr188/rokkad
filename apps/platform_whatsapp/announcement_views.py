from datetime import datetime
from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from apps.orgs.services.platform_console import require_console_access
from .announcements import review_announcement, confirm_announcement


class NoticeForm(forms.Form):
    purpose = forms.ChoiceField(choices=(("maintenance", "Planned maintenance"), ("incident", "Service incident")))
    text = forms.CharField(max_length=700, widget=forms.Textarea(attrs={"rows": 4}),
        help_text="Service information only. Use the existing Rokkad support link; exclude customer records and secrets.")
    revision = forms.CharField(max_length=64, label="Notice revision")
    impact_start = forms.DateTimeField(label="Impact starts (Asia/Kolkata)")
    impact_end = forms.DateTimeField(label="Impact ends (Asia/Kolkata)")
    expires_at = forms.DateTimeField(label="Message expires (Asia/Kolkata)")
    urgent = forms.BooleanField(required=False, label="Urgent incident: allow delivery outside 09:00–18:00")
    workspace_ids = forms.CharField(max_length=1200, label="Affected Workspace IDs", help_text="Comma-separated IDs, at most 100.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for key in ("impact_start", "impact_end", "expires_at"):
            self.fields[key].widget = forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"})
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-check-input" if isinstance(field, forms.BooleanField) else "form-control"

    def clean_workspace_ids(self):
        try:
            values = sorted(set(int(v.strip()) for v in self.cleaned_data["workspace_ids"].split(",")))
        except ValueError:
            raise forms.ValidationError("Enter comma-separated positive Workspace IDs.")
        if not 1 <= len(values) <= 100 or any(v <= 0 for v in values):
            raise forms.ValidationError("Enter 1 to 100 positive Workspace IDs.")
        return values

    def spec(self):
        return {k: v.isoformat() if hasattr(v, "isoformat") else v for k, v in self.cleaned_data.items()}


class ConfirmationForm(forms.Form):
    token = forms.CharField(widget=forms.HiddenInput, max_length=100000)
    acknowledged = forms.BooleanField(label="I reviewed the service text, affected Workspaces, recipients, expiry and estimated cost.")


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def announcements(request):
    require_console_access(request.user)
    if getattr(request, "workspace", None) is not None:
        raise PermissionDenied("Open the platform console outside a Workspace.")
    form, review, errors, saved, status = NoticeForm(), None, None, None, 200
    if request.method == "POST":
        try:
            if request.POST.get("action") == "review":
                form = NoticeForm(request.POST)
                if form.is_valid():
                    review = review_announcement(actor=request.user, spec=form.spec())
                else:
                    status = 400
            elif request.POST.get("action") == "confirm":
                confirmation = ConfirmationForm(request.POST)
                if not confirmation.is_valid():
                    raise ValidationError("Review and acknowledge the exact service notice first.")
                saved = confirm_announcement(actor=request.user, token=confirmation.cleaned_data["token"])
            else:
                raise ValidationError("Choose review or confirm.")
        except ValidationError as exc:
            errors, status = exc.messages, 409
    if review:
        for key in ("impact_start", "impact_end", "expires_at"):
            review[key] = datetime.fromisoformat(review["spec"][key])
    return render(request, "platform_whatsapp/announcements.html", {"section": "whatsapp", "form": form,
        "review": review, "review_errors": errors, "saved": saved}, status=status)
