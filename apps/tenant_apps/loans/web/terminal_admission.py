"""The bounded closed-position adapter in the ordinary Loans interface."""
from decimal import Decimal
from django import forms
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.shortcuts import render, redirect
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from apps.tenant_apps.loans.services.history_setup import require_history_setup_access
from apps.tenant_apps.loans.services.recorded_history import new_recording_intent
from apps.tenant_apps.loans.services.terminal_admission import preview_terminal_admission, admit_terminal_position
from .recorded_history import PaperHistoryForm, PaperCollateralFormSet, _style


class TerminalForm(PaperHistoryForm):
    closed_on = forms.DateField(label="Verified closure date", widget=forms.DateInput(attrs={"type": "date"}))
    closure_reference = forms.CharField(max_length=1000, widget=forms.Textarea(attrs={"rows": 3}),
        label="Evidence establishing the agreement and fully settled closing position",
        help_text="Identify the checked sources. Earlier receipts may be incomplete. This requires verified zero principal, interest and fees.")
    custody = forms.ChoiceField(label="Handover established by the checked source", choices=(
        ("UNKNOWN", "Physical handover not established"), ("RETURNED", "Source confirms all collateral was returned")))
    confirmed_agreement = forms.BooleanField(label="I verified the original agreement, item principals/rates, tenure and interest rounding.")
    confirmed_closed = forms.BooleanField(label="I verified zero principal, interest and fees at closure. I am not claiming complete earlier receipts.")

    def __init__(self, *args, workspace, **kwargs):
        super().__init__(*args, workspace=workspace, routine=False, itemized_archive=True, **kwargs)
        for name in ("routine_entry", "exceptions", "exception_reason", "advance_months", "document_charge", "payout_basis", "cash_paid",
            "complete_through", "final_state", "confirmed_history", "confirmed_rule", "description", "metal", "quantity",
            "gross_weight", "net_weight", "purity", "principal", "rate"):
            self.fields.pop(name)
        self.fields["product_version_id"].queryset = self.fields["product_version_id"].queryset.model.objects.filter(
            workspace=workspace, status__in=("ACTIVE", "RETIRED"), repayment_structure__in=("FLEXIBLE_PARTIAL_PAYMENT", "SINGLE_PAYMENT_BULLET"),
            amortisation_method="NONE")
        self.fields["borrower_id"].queryset = self.fields["borrower_id"].queryset.model.objects.filter(workspace=workspace)
        _style(self)


@never_cache
@require_http_methods(["GET", "POST"])
def record(request):
    workspace, actor = request.workspace, request.user
    require_history_setup_access(workspace.pk, actor)
    post = request.POST.copy() if request.method == "POST" else None
    archive_id = post.get("archive_evidence_id") if post is not None else request.GET.get("archive")
    archive, initial, initial_items = None, {}, []
    if archive_id:
        from apps.tenant_apps.loans.services.archive import get_evidence
        archive = get_evidence(workspace_id=workspace.pk, actor=actor, evidence_id=archive_id)
        facts = archive.document["facts"]
        initial = dict(number=facts["loan_number"], date=facts["opened_on"], closed_on=facts["closed_on"],
            source_reference=f"Archive {archive.source_system} / {archive.source_id}"[:160])
        initial_items = facts["collateral"] or []
    intent = post.get("intent_token", "") if post is not None else ""
    intent = intent or new_recording_intent(workspace=workspace, actor=actor)
    if post is not None and post.get("action") == "add_collateral":
        try:
            post["collateral-TOTAL_FORMS"] = str(min(100, int(post.get("collateral-TOTAL_FORMS", "1")) + 1))
        except ValueError:
            pass
    form = TerminalForm(post, workspace=workspace, initial=initial)
    collateral = PaperCollateralFormSet(post, prefix="collateral", initial=initial_items, form_kwargs={"exceptions": True})
    review, token = None, post.get("review_token", "") if post is not None else ""
    if post is not None and post.get("action") in {"preview", "confirm"} and form.is_valid() and collateral.is_valid():
        values = {name: value.pk if name.endswith("_id") else value.isoformat() if hasattr(value, "isoformat") else str(value) if isinstance(value, Decimal) else value
            for name, value in form.cleaned_data.items() if value is not None}
        values["collateral"] = [dict(description=row.cleaned_data["description"], quantity=row.cleaned_data["quantity"],
            metal=row.cleaned_data["metal"], gross_weight=str(row.cleaned_data["gross_weight"]), net_weight=str(row.cleaned_data["net_weight"]),
            purity=str(row.cleaned_data["purity_percentage"]), principal=str(row.cleaned_data["allocated_principal"]),
            rate=str(row.cleaned_data["interest_rate_override"])) for row in collateral if not row.cleaned_data.get("DELETE")]
        args = dict(workspace=workspace, actor=actor, data=values, intent_token=intent, evidence_id=archive_id or None)
        try:
            if post["action"] == "preview":
                review, token = preview_terminal_admission(**args)
            else:
                loan, created = admit_terminal_position(**args, review_token=token, confirmed=post.get("confirmed") == "yes")
                messages.success(request, "Verified closed position recorded. Earlier receipts remain unavailable." if created else "This closed position is already recorded.")
                return redirect("workspace_loans:pawn_loan_detail", workspace_slug=workspace.slug, pk=loan.pk)
        except (ValueError, ValidationError, ObjectDoesNotExist) as exc:
            form.add_error(None, str(exc))
    return render(request, "loans/pawn/terminal_admission.html", dict(form=form, collateral=collateral,
        archive=archive, intent_token=intent, review=review, review_token=token))
