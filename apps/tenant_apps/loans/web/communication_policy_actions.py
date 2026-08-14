from django import forms
from django.contrib import messages
from django.shortcuts import redirect, render

from apps.tenant_apps.loans.access import loans_setup_required
from apps.tenant_apps.loans.services.communication_policy import (
    CommunicationPolicyError,
    get_pawn_loan_communication_policy,
    set_pawn_loan_communication_policy,
)


class PawnLoanCommunicationPolicyForm(forms.Form):
    preferred_channel = forms.ChoiceField(choices=(("EMAIL", "Email"), ("WHATSAPP", "WhatsApp")))
    quiet_hours_start = forms.TimeField(required=False, widget=forms.TimeInput(attrs={"type": "time"}))
    quiet_hours_end = forms.TimeField(required=False, widget=forms.TimeInput(attrs={"type": "time"}))
    cooldown_days = forms.IntegerField(min_value=0, max_value=90, help_text="Minimum days between the same notice kind on the same channel. Use 0 to disable.")
    escalation_dpd = forms.IntegerField(min_value=1, max_value=365, help_text="Display escalation guidance at this DPD. This never sends automatically.")

    def clean(self):
        cleaned = super().clean()
        if bool(cleaned.get("quiet_hours_start")) != bool(cleaned.get("quiet_hours_end")):
            raise forms.ValidationError("Quiet hours require both start and end times.")
        if cleaned.get("quiet_hours_start") and cleaned["quiet_hours_start"] == cleaned["quiet_hours_end"]:
            raise forms.ValidationError("Quiet-hours start and end must differ.")
        return cleaned

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-select" if isinstance(field.widget, forms.Select) else "form-control"


@loans_setup_required
def pawn_communication_policy(request):
    policy = get_pawn_loan_communication_policy()
    initial = {
        "preferred_channel": getattr(policy, "preferred_channel", "EMAIL"),
        "quiet_hours_start": getattr(policy, "quiet_hours_start", None),
        "quiet_hours_end": getattr(policy, "quiet_hours_end", None),
        "cooldown_days": getattr(policy, "cooldown_days", 0),
        "escalation_dpd": getattr(policy, "escalation_dpd", 30),
    }
    form = PawnLoanCommunicationPolicyForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        try:
            set_pawn_loan_communication_policy(actor=request.user, **form.cleaned_data)
        except CommunicationPolicyError as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "PawnLoan communication policy updated. Automation remains disabled.")
            return redirect("loans:pawn_communication_policy")
    return render(request, "loans/setup/communication_policy.html", {"form": form, "policy": policy})


__all__ = ["pawn_communication_policy"]
