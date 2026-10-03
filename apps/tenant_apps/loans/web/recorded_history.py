"""Paper-first entry within the ordinary New loan route."""
from decimal import Decimal
from django import forms
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.shortcuts import redirect, render

from apps.tenant_apps.loans import models as m
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.loans.services.recorded_history import (
    new_recording_intent, preview_recorded_history, admit_recorded_history,
)

DAY = {"type": "date"}


class PaperHistoryForm(forms.Form):
    borrower_id = forms.ModelChoiceField(queryset=Party.objects.none(), label="Borrower")
    series_id = forms.ModelChoiceField(queryset=m.LoanSeries.objects.none(), label="Original loan series")
    product_version_id = forms.ModelChoiceField(queryset=m.LoanProductVersion.objects.none(), label="Matching contract")
    number = forms.CharField(max_length=64, label="Original loan number")
    date = forms.DateField(widget=forms.DateInput(attrs=DAY), label="Actual payout date")
    source_reference = forms.CharField(max_length=160, label="Paper book / page / loan reference")
    principal = forms.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"), label="Original principal")
    rate = forms.DecimalField(max_digits=9, decimal_places=6, min_value=0, label="Agreed monthly interest (%)")
    tenure = forms.IntegerField(min_value=1, max_value=600, label="Agreed tenure (months)")
    advance_months = forms.TypedChoiceField(choices=((0,"No advance interest deducted"),(1,"One month deducted")), coerce=int)
    document_charge = forms.DecimalField(max_digits=14, decimal_places=2, min_value=0, required=False,
        initial=0, label="Document charge deducted")
    payout_basis = forms.ChoiceField(initial="PROCEEDS", label="Meaning of the paper amount", choices=(
        ("PROCEEDS", "Loan proceeds after deductions; physical cash not confirmed"),
        ("CASH", "Confirmed cash paid to the customer")))
    cash_paid = forms.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"), required=False,
        label="Proceeds after interest and document charge", help_text="Leave blank to calculate. A paper renewal may use these proceeds to settle another loan; no predecessor is required.")
    description = forms.CharField(max_length=255, label="Collateral description")
    metal = forms.ChoiceField(choices=(("GOLD","Gold"),("SILVER","Silver")))
    quantity = forms.IntegerField(min_value=1, max_value=999)
    gross_weight = forms.DecimalField(max_digits=12, decimal_places=4, min_value=Decimal("0.0001"), label="Gross weight (g)")
    net_weight = forms.DecimalField(max_digits=12, decimal_places=4, min_value=Decimal("0.0001"), label="Net weight (g)")
    purity = forms.DecimalField(max_digits=7, decimal_places=4, min_value=Decimal("0.0001"), max_value=100, label="Purity (%)")
    monitoring_method = forms.ChoiceField(label="Current coverage assessment", choices=(
        ("CALCULATED_METAL_VALUE","Current metal price"), ("LATEST_APPRAISAL","Current approved appraisal"),
        ("LOWER_OF_CALCULATED_AND_APPRAISAL","Lower of current price and appraisal")))
    monitoring_ltv = forms.DecimalField(max_digits=5, decimal_places=4, min_value=Decimal("0.0001"), max_value=1,
        label="Monitoring LTV ratio", help_text="For example, 0.80 means 80%. This does not reapprove the original loan.")
    monitoring_reason = forms.CharField(max_length=255, label="Reason for monitoring choice")
    complete_through = forms.DateField(widget=forms.DateInput(attrs=DAY), label="All paper activity entered through")
    final_state = forms.ChoiceField(label="State after the final transaction", choices=(
        ("ACTIVE","This loan is outstanding"), ("CLOSED","This loan is closed according to its paper record")))
    confirmed_rule = forms.BooleanField(label="The agreed rule is simple monthly interest: a full month is charged from each loan-date anniversary; principal reductions apply from the following anniversary.")
    confirmed_history = forms.BooleanField(label="I checked this loan's paper record through the stated date and checked for duplicates. No earlier or later loan's renewal history is required.")

    def __init__(self, *args, workspace, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["borrower_id"].queryset = Party.objects.filter(workspace=workspace, status="ACTIVE")
        self.fields["series_id"].queryset = m.LoanSeries.objects.filter(workspace=workspace).select_related("license")
        self.fields["product_version_id"].queryset = m.LoanProductVersion.objects.filter(workspace=workspace,
            status="ACTIVE", repayment_structure__in=("SINGLE_PAYMENT_BULLET", "FLEXIBLE_PARTIAL_PAYMENT"), amortisation_method="NONE").select_related("product")
        _style(self)


class PaperTransactionForm(forms.Form):
    kind = forms.ChoiceField(choices=(("","Choose transaction"),("PAYMENT","Receipt"),("RENEW","Known linked renewal (optional)"),("CLOSE","Closure")))
    date = forms.DateField(widget=forms.DateInput(attrs=DAY), label="Actual date")
    amount = forms.DecimalField(max_digits=14, decimal_places=2, min_value=0, label="Receipt total or closing settlement amount")
    closure_basis = forms.ChoiceField(required=False, initial="PAPER_SETTLEMENT", label="Closure evidence", choices=(
        ("", "For closure only"), ("PAPER_SETTLEMENT", "Paper says settled; cash method and customer handover not confirmed"),
        ("RETURNED", "Cash received and collateral returned to the named customer")))
    reference = forms.CharField(max_length=160, label="Distinct paper receipt / page reference")
    number = forms.CharField(max_length=64, required=False, label="Successor loan number or release number")
    rate = forms.DecimalField(max_digits=9, decimal_places=6, min_value=0, required=False, label="Renewal monthly rate (%)")
    tenure = forms.IntegerField(min_value=1, max_value=600, required=False, label="Renewal tenure (months)")
    renewal_method = forms.ChoiceField(required=False, label="Renewal funding", choices=(
        ("", "For renewals only"), ("CARRY", "Carry remaining principal, with reduction or top-up"),
        ("REPAY_REDRAW", "Old principal fully repaid; new advance paid")))
    new_principal = forms.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"), required=False, label="Renewal: new agreed principal")
    cash_paid = forms.DecimalField(max_digits=14, decimal_places=2, min_value=0, required=False, label="Renewal: actual cash paid out (enter 0 if none)")
    interest_offset = forms.DecimalField(max_digits=14, decimal_places=2, min_value=0, required=False, label="Renewal: old interest deducted from advance (enter 0 if none)")
    custody = forms.ChoiceField(required=False, label="Renewal collateral handling", choices=(
        ("", "For renewals only"), ("HELD", "Stayed held throughout"), ("RETURNED_REPLEDGED", "Actually returned and repledged on this date")))
    recipient = forms.CharField(max_length=255, required=False, label="Who received the collateral (if actually returned)")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style(self)


def _style(form):
    for field in form.fields.values():
        field.widget.attrs["class"] = "form-check-input" if isinstance(field.widget, forms.CheckboxInput) else (
            "form-select" if isinstance(field.widget, forms.Select) else "form-control")


Transactions = forms.formset_factory(PaperTransactionForm, extra=1, max_num=30, validate_max=True, absolute_max=30, can_delete=True)


def _data(form, rows):
    value = dict(form.cleaned_data)
    value["document_charge"] = value["document_charge"] or Decimal("0")
    if value["cash_paid"] is None:
        from decimal import ROUND_HALF_UP
        advance = (value["principal"] * value["rate"] / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) * value["advance_months"]
        value["cash_paid"] = value["principal"] - advance - value["document_charge"]
    for name in ("borrower_id", "series_id", "product_version_id"):
        value[name] = value[name].pk
    value["events"] = [{key: val for key, val in row.cleaned_data.items() if key != "DELETE"}
                       for row in rows if row.cleaned_data and not row.cleaned_data.get("DELETE")]
    # Values crossing the signed review/storage boundary use canonical JSON types.
    for row in value["events"]:
        if row["kind"] == "CLOSE" and not row["closure_basis"]:
            row["closure_basis"] = "RETURNED"
    import json
    return json.loads(json.dumps(value, default=lambda obj: obj.isoformat() if hasattr(obj, "isoformat") else str(obj)))


def paper_history_entry(request):
    workspace, actor = request.loans_workspace, request.user
    post = request.POST.copy() if request.method == "POST" else None
    if post is not None and "payout_basis" not in post:
        post["payout_basis"] = "CASH"
    archive_id = post.get("archive_evidence_id") if post is not None else request.GET.get("archive")
    archive, initial, initial_rows, snapshots = None, {}, [], []
    if archive_id:
        from apps.tenant_apps.loans.services.archive import get_evidence
        from apps.tenant_apps.loans.services.history_setup import require_history_setup_access
        require_history_setup_access(workspace.pk, actor)
        archive = get_evidence(workspace_id=workspace.pk, actor=actor, evidence_id=archive_id)
        from apps.tenant_apps.loans.services.archive_admission import source_snapshots
        try:
            snapshots = source_snapshots(archive)
        except ValueError:
            snapshots = [archive]
        facts = archive.document["facts"]
        initial = dict(number=facts["loan_number"], date=facts["opened_on"], principal=facts["original_principal"],
            complete_through=facts["closed_on"], final_state="CLOSED",
            source_reference=f"Archive {archive.source_system} / {archive.source_id}"[:160])
        if facts["collateral"] and len(facts["collateral"]) == 1:
            initial.update(facts["collateral"][0])
        initial_rows = [dict(date=row["date"], amount=row["amount"], reference=row["id"])
                        for row in facts["payments"] or []]
    intent = post.get("intent_token", "") if post is not None else new_recording_intent(workspace=workspace, actor=actor)
    if post is not None and post.get("action") == "add":
        try:
            post["events-TOTAL_FORMS"] = str(min(30, int(post.get("events-TOTAL_FORMS", "3")) + 1))
        except ValueError:
            pass
    form = PaperHistoryForm(post, workspace=workspace, initial=initial)
    if archive:
        form.fields["final_state"].choices = (("CLOSED", "All debt settled; state the known handover facts below"),)
        form.fields["reconciliation"] = forms.CharField(max_length=1000, widget=forms.Textarea(attrs={"rows": 3}),
            label="Checked sources for original terms, missing facts and known custody",
            help_text="Identify supporting records for borrower, complete financial history and known handover facts. Leave handover unconfirmed when the source does not establish it.")
        form.fields["confirmed_history"].label = "I checked the archive and supporting records. This complete history has not already been admitted as an ordinary loan."
        form.fields["payout_basis"].initial = "CASH"
        _style(form)
    rows = Transactions(post, prefix="events", initial=initial_rows)
    if archive:
        for row in rows:
            row.fields["kind"].choices = (("", "Choose transaction"), ("PAYMENT", "Receipt"), ("CLOSE", "Full return / closure"))
            row.fields["number"].label = "Original release number, if recorded (for final closure)"
            row.fields["closure_basis"].choices = (("", "For receipts only"), ("RETURNED", "Confirmed cash collection and full collateral return"),
                ("PAPER_SETTLEMENT", "Financially settled; physical cash and customer handover unconfirmed"))
            row.fields["closure_basis"].initial = "PAPER_SETTLEMENT"
            for name in ("rate", "tenure", "renewal_method", "new_principal", "cash_paid", "interest_offset", "custody"):
                row.fields[name].widget = forms.HiddenInput()
    review, token = None, ""
    if post is not None and post.get("action") != "add" and form.is_valid() and rows.is_valid():
        try:
            data = _data(form, rows)
            reconciliation = data.pop("reconciliation", "")
            if archive:
                from apps.tenant_apps.loans.services.archive_admission import preview_archive_admission, admit_archive_history
                preview, admit = preview_archive_admission, admit_archive_history
                extra = dict(evidence_id=archive.public_id, reconciliation=reconciliation)
            else:
                preview, admit, extra = preview_recorded_history, admit_recorded_history, {}
            if post.get("action") == "confirm":
                loan, created = admit(workspace=workspace, actor=actor, data=data, intent_token=intent, **extra,
                    review_token=post.get("review_token"), confirmed=post.get("confirm_review") == "on")
                messages.success(request, "Paper history recorded." if created else "This history was already recorded; no duplicate was created.")
                return redirect("workspace_loans:pawn_loan_detail", workspace_slug=workspace.slug, pk=loan.pk)
            review, token = preview(workspace=workspace, actor=actor, data=data, intent_token=intent, **extra)
        except (ValueError, ValidationError, ObjectDoesNotExist) as exc:
            form.add_error(None, str(exc))
    sections = [("Original contract", ("borrower_id", "series_id", "product_version_id", "number", "date", "source_reference", "principal", "rate", "tenure", "advance_months", "document_charge", "payout_basis", "cash_paid")),
        ("Collateral", ("description", "metal", "quantity", "gross_weight", "net_weight", "purity")),
        ("Current monitoring", ("monitoring_method", "monitoring_ltv", "monitoring_reason")),
        ("Completeness and agreed calculation", ("complete_through", "final_state", "confirmed_rule", "confirmed_history"))]
    if archive:
        sections.append(("Archive reconciliation", ("reconciliation",)))
    return render(request, "loans/pawn/paper_history.html", dict(form=form, rows=rows, review=review,
        archive=archive, archive_snapshots=snapshots, review_token=token, intent_token=intent,
        sections=[(title, [form[name] for name in names]) for title, names in sections]))
