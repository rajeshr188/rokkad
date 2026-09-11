from django import forms
from django.contrib import messages
from django.shortcuts import redirect, render

from apps.tenant_apps.loans.access import loans_setup_required
from apps.tenant_apps.loans.models import LoanRiskAlert
from apps.tenant_apps.loans.services.risk_borrower_notices import (
    RiskBorrowerNoticeError,
    create_risk_borrower_notice,
    preview_risk_borrower_notice,
)
from apps.tenant_apps.loans.services.communication_policy import get_pawn_loan_communication_policy


class RiskBorrowerNoticeConfirmationForm(forms.Form):
    channel = forms.CharField(widget=forms.HiddenInput)
    preview_fingerprint = forms.CharField(widget=forms.HiddenInput)
    confirm = forms.BooleanField(
        label="I confirm the borrower, destination, amounts, template, and exact message shown above."
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["confirm"].widget.attrs["class"] = "form-check-input"


@loans_setup_required
def pawn_risk_borrower_notice_create(request, pk):
    requested_channel = request.POST.get("channel") or request.GET.get("channel")
    policy = get_pawn_loan_communication_policy()
    channel = (requested_channel or getattr(policy, "preferred_channel", "EMAIL")).strip().upper()
    try:
        preview = preview_risk_borrower_notice(pk, channel=channel)
    except (RiskBorrowerNoticeError, ValueError) as exc:
        alert = LoanRiskAlert.objects.filter(
            pk=pk, workspace=request.loans_workspace
        ).select_related("loan__borrower").first()
        return render(request, "loans/setup/risk_borrower_notice_blocked.html", {
            "reason": str(exc),
            "alert": alert,
            "return_url": request.path,
        }, status=409)
    form = RiskBorrowerNoticeConfirmationForm(
        request.POST or None,
        initial={"preview_fingerprint": preview.fingerprint, "channel": channel},
    )
    if request.method == "POST" and form.is_valid():
        try:
            notice = create_risk_borrower_notice(
                pk,
                actor=request.user,
                expected_fingerprint=form.cleaned_data["preview_fingerprint"],
                channel=form.cleaned_data["channel"],
            )
        except (RiskBorrowerNoticeError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, f"{notice.get_notice_kind_display()} created and queued through Notify.")
            return redirect('workspace_loans:pawn_loan_detail', pk=notice.loan_id, workspace_slug=request.workspace.slug)
    return render(request, "loans/setup/risk_borrower_notice.html", {
        "form": form, "preview": preview, "alert": preview.readiness.alert,
    })


__all__ = ["pawn_risk_borrower_notice_create"]
