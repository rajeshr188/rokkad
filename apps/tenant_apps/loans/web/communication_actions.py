from django import forms
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from apps.tenant_apps.loans.access import loans_setup_required
from apps.tenant_apps.loans.domain import PawnLoanNoticeChannel
from apps.tenant_apps.loans.models import PawnLoanCommunicationConsent
from apps.tenant_apps.loans.services.communication_consents import (
    CommunicationConsentError,
    set_pawn_loan_communication_consent,
)
from apps.tenant_apps.party.models import Party


class CommunicationConsentForm(forms.Form):
    channel = forms.ChoiceField(choices=[(row.value, row.name.title()) for row in PawnLoanNoticeChannel])
    decision = forms.ChoiceField(choices=(("ALLOW", "Allow service notices"), ("BLOCK", "Do not allow"), ("OPT_OUT", "Borrower opted out")))
    evidence = forms.CharField(max_length=255, widget=forms.Textarea(attrs={"rows": 2}), help_text="Record how consent or opt-out was obtained, or the reason for blocking.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["channel"].widget.attrs["class"] = "form-select"
        self.fields["decision"].widget.attrs["class"] = "form-select"
        self.fields["evidence"].widget.attrs["class"] = "form-control"


@loans_setup_required
def pawn_communication_consent(request, party_pk):
    party = get_object_or_404(Party, pk=party_pk)
    form = CommunicationConsentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            set_pawn_loan_communication_consent(
                party.pk, actor=request.user, **form.cleaned_data
            )
        except CommunicationConsentError as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "PawnLoan service-notice consent updated.")
            next_url = request.POST.get("next")
            if next_url and url_has_allowed_host_and_scheme(
                next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
            ):
                return redirect(next_url)
            return redirect("loans:pawn_risk_portfolio")
    consents = {
        row.channel: row
        for row in PawnLoanCommunicationConsent.objects.filter(
            workspace=request.loans_workspace, party=party
        ).select_related("updated_by")
    }
    return render(request, "loans/setup/communication_consent.html", {
        "party": party, "form": form,
        "next_url": request.GET.get("next", ""),
        "consent_rows": tuple(
            {"channel": channel, "consent": consents.get(channel.value)}
            for channel in PawnLoanNoticeChannel
        ),
    })


__all__ = ["pawn_communication_consent"]
