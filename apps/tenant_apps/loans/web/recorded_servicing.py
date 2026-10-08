"""Ordinary forms for later paper closure and a known paper renewal."""
import json
from decimal import Decimal
from uuid import uuid4

from django import forms
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.tenant_apps.loans.access import loans_workspace_required
from apps.tenant_apps.loans.models import PawnLoan
from apps.tenant_apps.loans.services.recorded_closures import preview_recorded_closure, record_paper_closure
from apps.tenant_apps.loans.services.recorded_renewal_actions import preview_existing_paper_renewal, record_existing_paper_renewal
from .recorded_history import _style
from apps.tenant_apps.loans.services.paper_handover import preview_paper_handover, confirm_paper_handover


class PaperClosureForm(forms.Form):
    date = forms.DateField(label="Actual closing date", widget=forms.DateInput(attrs={"type": "date"}))
    amount = forms.DecimalField(max_digits=14, decimal_places=2, min_value=0, label="Settlement amount on paper")
    number = forms.CharField(max_length=64, required=False, label="Original release / closing number (if recorded)",
        help_text="Leave blank if paper has no closing number. Rokkad assigns a system recording number.")
    reference = forms.CharField(max_length=160, required=False, label="Source book / receipt reference")
    basis = forms.ChoiceField(initial="PAPER_SETTLEMENT", label="What the record confirms", choices=(
        ("PAPER_SETTLEMENT", "Loan settled; cash method and customer handover unspecified"),
        ("RETURNED", "Cash received and collateral returned to the named customer")))
    recipient = forms.CharField(max_length=255, required=False, label="Customer return recipient (for confirmed return only)")
    collector_is_borrower = forms.TypedChoiceField(required=False, label="Return recipient", empty_value=True,
        choices=(("yes", "Borrower"), ("no", "Another person")), coerce=lambda value: value == "yes")
    paid_by = forms.CharField(max_length=255, required=False, label="Paid by (for confirmed cash collection)")
    relationship = forms.CharField(max_length=100, required=False)
    authorization_note = forms.CharField(max_length=500, required=False, label="Authority to collect")
    interest_concession = forms.DecimalField(max_digits=16, decimal_places=2, min_value=0, required=False, initial=0)
    concession_reason = forms.CharField(max_length=255, required=False)
    exception_reason = forms.CharField(max_length=255, required=False, label="Administrator recording exception reason")
    request_key = forms.CharField(max_length=120, widget=forms.HiddenInput)

    def clean(self):
        data = super().clean()
        data["interest_concession"] = data.get("interest_concession") or 0
        if data["interest_concession"] and not data.get("concession_reason"):
            self.add_error("concession_reason", "Explain the agreed interest concession.")
        if data.get("basis") == "RETURNED":
            for name in (("recipient", "paid_by") if "paid_by" in self.data or "purpose" in self.data else ("recipient",)):
                if not data.get(name):
                    self.add_error(name, "Required for confirmed cash collection and return.")
            if data.get("collector_is_borrower") is False:
                for name in ("relationship", "authorization_note"):
                    if not data.get(name):
                        self.add_error(name, "Required for another recipient.")
        return data


class PaperRenewalForm(forms.Form):
    date = forms.DateField(label="Actual renewal date", widget=forms.DateInput(attrs={"type": "date"}))
    number = forms.CharField(max_length=64, label="New paper loan number")
    reference = forms.CharField(max_length=160, label="Paper book / page reference for this renewal")
    new_principal = forms.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"), label="New agreed principal")
    rate = forms.DecimalField(max_digits=9, decimal_places=6, min_value=0, label="New agreed monthly interest (%)")
    tenure = forms.IntegerField(min_value=1, max_value=600, label="New agreed tenure (months)")
    advance_months = forms.TypedChoiceField(coerce=int, label="New loan advance interest", choices=((0,"None"),(1,"One month deducted")))
    currency_quantum = forms.ChoiceField(label="New agreement interest rounding", required=False,
        choices=(("0.01", "Paise"), ("1", "Whole rupees")), initial="0.01")
    document_charge = forms.DecimalField(max_digits=14, decimal_places=2, min_value=0, label="New document charge deducted", initial=0)
    amount = forms.DecimalField(max_digits=14, decimal_places=2, min_value=0, label="Actual net cash received from customer (0 if none)", initial=0)
    cash_paid = forms.DecimalField(max_digits=14, decimal_places=2, min_value=0, label="Actual net cash paid to customer (0 if none)", initial=0)
    request_key = forms.CharField(max_length=120, widget=forms.HiddenInput)

    def __init__(self, *args, loan=None, **kwargs):
        super().__init__(*args, **kwargs)
        if loan and loan.policy_snapshot:
            self.initial.setdefault("currency_quantum", str(loan.policy_snapshot.currency_quantum.normalize()))
        if loan and loan.loan_events.filter(event_kind="MIGRATION_OPENING").exists():
            from apps.tenant_apps.loans.models import LoanProductVersion
            self.fields["product_version_id"] = forms.ModelChoiceField(
                queryset=LoanProductVersion.objects.filter(workspace=loan.workspace, status="ACTIVE",
                    repayment_structure__in=("SINGLE_PAYMENT_BULLET", "FLEXIBLE_PARTIAL_PAYMENT"), amortisation_method="NONE"),
                label="Contract version matching the new paper agreement")

    def clean_currency_quantum(self):
        return self.cleaned_data.get("currency_quantum") or "0.01"


class PaperHandoverForm(forms.Form):
    date = forms.DateField(label="Actual customer handover date", widget=forms.DateInput(attrs={"type": "date"}))
    recipient = forms.CharField(max_length=255, label="Who received the collateral")
    reference = forms.CharField(max_length=160, label="Supporting paper book / receipt reference")
    request_key = forms.CharField(max_length=120, widget=forms.HiddenInput)


@loans_workspace_required
@require_http_methods(["GET", "POST"])
def handover(request, pk):
    request.loans_workspace_access.require("loan.release")
    loan = get_object_or_404(PawnLoan, pk=pk, workspace=request.loans_workspace)
    form = PaperHandoverForm(request.POST or None, initial=dict(date=timezone.localdate(), request_key=str(uuid4())))
    _style(form)
    review, token = None, ""
    if request.method == "POST" and form.is_valid():
        data = dict(form.cleaned_data, date=form.cleaned_data["date"].isoformat())
        try:
            if request.POST.get("action") == "confirm":
                _, created = confirm_paper_handover(loan.pk, actor=request.user, data=data,
                    review_token=request.POST.get("review_token", ""), confirmed=request.POST.get("confirmed") == "on")
                messages.success(request, "Customer handover confirmed." if created else "Already confirmed; no duplicate created.")
                return redirect("workspace_loans:pawn_loan_detail", workspace_slug=request.workspace.slug, pk=loan.pk)
            review, token = preview_paper_handover(loan.pk, actor=request.user, data=data)
        except (ValueError, ValidationError, ObjectDoesNotExist) as exc:
            form.add_error(None, str(exc))
    return render(request, "loans/pawn/paper_handover.html", dict(loan=loan, form=form, review=review, review_token=token))


def _action(request, pk, *, renewal):
    loan = get_object_or_404(PawnLoan, pk=pk, workspace=request.loans_workspace)
    form_type, preview, commit = ((PaperRenewalForm, preview_existing_paper_renewal, record_existing_paper_renewal)
        if renewal else (PaperClosureForm, preview_recorded_closure, record_paper_closure))
    form = form_type(request.POST or None, **({"loan": loan} if renewal else {}), initial=dict(date=timezone.localdate(), request_key=str(uuid4()),
        new_principal=loan.principal_amount, rate=loan.monthly_interest_rate, tenure=loan.tenure_months,
        recipient=loan.borrower.display_name, paid_by=loan.borrower.display_name, collector_is_borrower="yes"))
    _style(form)
    review, token = None, ""
    if request.method == "POST" and form.is_valid():
        cleaned = dict(form.cleaned_data)
        if not renewal and "purpose" not in request.POST and not any(name in request.POST for name in (
                "interest_concession", "exception_reason", "paid_by", "collector_is_borrower")):
            # Already issued legacy forms keep their exact seven-fact review.
            cleaned = {name: value for name, value in cleaned.items() if name in (
                "date", "amount", "number", "reference", "basis", "recipient", "request_key")}
        if "product_version_id" in cleaned:
            cleaned["product_version_id"] = cleaned["product_version_id"].pk
        data = json.loads(json.dumps(cleaned, default=lambda value: value.isoformat() if hasattr(value, "isoformat") else str(value)))
        try:
            if request.POST.get("action") == "confirm":
                result, created = commit(loan_id=loan.pk, actor=request.user, data=data,
                    review_token=request.POST.get("review_token", ""), confirmed=request.POST.get("confirmed") == "on")
                messages.success(request, "Paper renewal recorded." if renewal and created else "Paper closure recorded." if created else "Already recorded; no duplicate created.")
                return redirect("workspace_loans:pawn_loan_detail", workspace_slug=request.workspace.slug,
                    pk=result.pk if renewal else loan.pk)
            review, token = preview(loan_id=loan.pk, actor=request.user, data=data)
        except (ValueError, ValidationError, ObjectDoesNotExist) as exc:
            form.add_error(None, str(exc))
    return render(request, "loans/pawn/paper_servicing.html" if renewal else "loans/pawn/full_release.html",
        dict(loan=loan, form=form, renewal=renewal, review=review, review_token=token,
             closure_purpose="PAPER", can_concede_interest=request.loans_workspace_access.can("workspace.settings.manage")))


@loans_workspace_required
@require_http_methods(["GET", "POST"])
def closure(request, pk):
    request.loans_workspace_access.require("loan.release")
    return _action(request, pk, renewal=False)


def renewal(request, pk):
    request.loans_workspace_access.require("data.create")
    request.loans_workspace_access.require("loan.release")
    request.loans_workspace_access.require("loan.disburse")
    return _action(request, pk, renewal=True)
