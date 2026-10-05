"""Correction review inside ordinary Loans, using canonical collection services."""
from uuid import uuid4
from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache

from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.access import LOANS_ADMIN_ACTION, loans_action_required
from apps.tenant_apps.loans.services.recorded_corrections import preview_correction, record_correction, dependencies


class CorrectionForm(forms.Form):
    operation = forms.ChoiceField(choices=(("ADD", "Add a missing paper receipt"), ("REPLACE", "Correct a mistaken receipt entry"), ("VOID", "Void a mistaken receipt entry (no refund)")))
    target = forms.TypedChoiceField(coerce=int, empty_value=None, required=False, label="Receipt to replace or void")
    date = forms.DateField(required=False, label="Actual receipt date", widget=forms.DateInput(attrs={"type": "date"}))
    amount = forms.DecimalField(required=False, max_digits=14, decimal_places=2, min_value=0.01, label="Actual total received")
    reference = forms.CharField(required=False, max_length=255, label="Paper receipt or book/page reference")
    before = forms.TypedChoiceField(coerce=int, empty_value=None, required=False, label="Place before this receipt on the same date",
        help_text="Leave blank to keep a replacement's position on its existing date, or append a new/moved receipt after that day's receipts.")
    reason = forms.CharField(max_length=500, widget=forms.Textarea(attrs={"rows": 3}), label="Why this history needs correction")
    settlement_cash_received = forms.DecimalField(required=False, max_digits=14, decimal_places=2, min_value=0, label="Actual cash received at renewal / closure")
    settlement_cash_paid = forms.DecimalField(required=False, max_digits=14, decimal_places=2, min_value=0, label="Actual cash paid out at renewal (zero for closure)")
    settlement_interest_offset = forms.DecimalField(required=False, max_digits=14, decimal_places=2, min_value=0, label="Old interest offset from renewal advance (zero for closure)")
    settlement_reference = forms.CharField(required=False, max_length=255, label="Source confirming the settlement cash")
    settlement_confirmed_unchanged = forms.BooleanField(required=False,
        label="The original settlement date, loan numbers, successor principal and terms, and collateral handover remain correct. I checked the actual settlement cash above.")
    request_key = forms.CharField(max_length=80, widget=forms.HiddenInput())
    review_token = forms.CharField(required=False, widget=forms.HiddenInput())
    confirmed = forms.BooleanField(required=False, label="I checked the original paper facts and every affected allocation. This records a correction, not another cash collection or refund.")

    def __init__(self, *args, receipts, settlement=None, collateral_items=(), replay_receipts=None, **kwargs):
        super().__init__(*args, **kwargs)
        if len(collateral_items) > 1:
            for item in collateral_items:
                self.fields[f"item_principal_{item.pk}"] = forms.DecimalField(required=False,
                    max_digits=14, decimal_places=2, min_value=0, label=f"Corrected receipt principal: {item.description}")
            for receipt in (receipts if replay_receipts is None else replay_receipts):
                if hasattr(receipt, "reversed_by_event"):
                    continue
                split = receipt.payload["repayment"].get("recording", {}).get("item_principal_split", {})
                for item in collateral_items:
                    name = f"replay_{receipt.pk}_{item.pk}"
                    self.fields[name] = forms.DecimalField(required=False, max_digits=14, decimal_places=2, min_value=0,
                        label=f"Retained receipt #{receipt.pk} ({receipt.effective_date}): principal for {item.description}",
                        help_text="Keep the actual split, or enter its corrected allocation if this review changes the principal portion.")
                    self.initial[name] = split.get(str(item.pk))
        if settlement is None:
            for key in list(self.fields):
                if key.startswith("settlement_"):
                    del self.fields[key]
        else:
            if settlement.payload.get("release", {}).get("paper_closure", {}).get("closure_basis") == "PAPER_SETTLEMENT":
                self.fields["settlement_cash_received"].label = "Paper closing settlement amount (physical cash remains unconfirmed)"
                self.fields["settlement_reference"].label = "Source confirming the paper closing settlement"
                self.fields["settlement_confirmed_unchanged"].label = "The original closing date and paper settlement basis remain correct. Customer handover remains unconfirmed. I checked the settlement amount above."
            from apps.tenant_apps.loans.services.recorded_settlement_corrections import renewal_cash
            cash = renewal_cash(settlement) if settlement.event_kind == "RENEWAL_SETTLEMENT" else None
            from decimal import Decimal
            values = settlement.payload["values"]
            received = cash["cash_received"] if cash else sum((Decimal(values.get(k, "0")) for k in ("principal", "interest", "fees")), Decimal("0"))
            for key, value in dict(cash_received=received, cash_paid=cash["cash_paid"] if cash else "0",
                                   interest_offset=cash["interest_offset"] if cash else "0").items():
                self.initial["settlement_" + key] = format(Decimal(value), ".2f")
        choices = [("", "No receipt selected")] + [(e.pk, f"#{e.pk} — {e.effective_date} — {e.payload['repayment']['amount_received']}" +
            (" (retained; already corrected)" if hasattr(e, "reversed_by_event") else "")) for e in receipts]
        self.fields["target"].choices = choices
        self.fields["before"].choices = choices
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-check-input" if isinstance(field.widget, forms.CheckboxInput) else "form-select" if isinstance(field.widget, forms.Select) else "form-control"


@loans_action_required(LOANS_ADMIN_ACTION)
@never_cache
def correction(request, pk):
    loan = get_object_or_404(m.PawnLoan, pk=pk, workspace=request.loans_workspace)
    batch_line = m.PawnReleaseBatchLine.objects.filter(release__loan=loan).order_by("-pk").first()
    if request.method == "GET" and batch_line:
        return redirect("workspace_loans:release_batch_correct_history", workspace_slug=request.workspace.slug, batch_pk=batch_line.batch_id)
    events, active, blockers = dependencies(loan)
    form = CorrectionForm(request.POST if request.method == "POST" else None,
        initial={"request_key": uuid4().hex}, receipts=[e for e in events if e.event_kind == "REPAYMENT"],
        settlement=next((e for e in active if e.event_kind in ("RELEASE_RECEIPT", "RENEWAL_SETTLEMENT")), None),
        collateral_items=list(loan.collateral_items.order_by("pk")))
    review = None
    if request.method == "POST" and form.is_valid():
        values = {key: value for key, value in form.cleaned_data.items() if key not in ("review_token", "confirmed")}
        _item_splits(values)
        values["date"] = values["date"].isoformat() if values["date"] else None
        values["amount"] = str(values["amount"]) if values["amount"] is not None else None
        settlement = {key.removeprefix("settlement_"): values.pop(key) for key in list(values) if key.startswith("settlement_")}
        if settlement:
            for key in ("cash_received", "cash_paid", "interest_offset"):
                settlement[key] = str(settlement[key]) if settlement[key] is not None else None
            values["settlement"] = settlement
        try:
            if request.POST.get("action") == "confirm":
                created = record_correction(loan.pk, actor=request.user, data=values,
                    review_token=form.cleaned_data["review_token"], confirmed=form.cleaned_data["confirmed"])
                messages.success(request, "History correction recorded." if created else "This correction was already recorded; no duplicate was created.")
                return redirect("workspace_loans:pawn_loan_detail", workspace_slug=request.workspace.slug, pk=loan.pk)
            review, token = preview_correction(loan.pk, actor=request.user, data=values)
            form.data = form.data.copy()
            form.data["review_token"] = token
        except (ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
    return render(request, "loans/pawn/correction.html", dict(loan=loan, form=form, review=review, blockers=blockers, dependencies=active))


class ContractCorrectionForm(CorrectionForm):
    principal = forms.DecimalField(max_digits=14, decimal_places=2, min_value=0.01, label="Correct original agreed principal")
    rate = forms.DecimalField(max_digits=9, decimal_places=6, min_value=0, label="Correct original monthly interest (%)")
    cash_paid = forms.DecimalField(max_digits=14, decimal_places=2, min_value=0.01, label="Correct original proceeds after deductions")

    def __init__(self, *args, predecessor=None, collateral_items=(), **kwargs):
        self.collateral_items = collateral_items
        kwargs["collateral_items"] = collateral_items
        super().__init__(*args, receipts=[], **kwargs)
        for key in list(self.fields):
            if key.startswith("item_principal_"):
                del self.fields[key]
        if len(collateral_items) > 1:
            for item in collateral_items:
                for name, value in (("principal", item.allocated_principal), ("rate", item.monthly_interest_rate)):
                    key = f"contract_item_{item.pk}_{name}"
                    self.fields[key] = forms.DecimalField(required=True, max_digits=14 if name == "principal" else 9,
                        decimal_places=2 if name == "principal" else 6, min_value=0.01 if name == "principal" else 0,
                        max_value=None if name == "principal" else 100, label=f"Correct original {name}: {item.description}")
                    self.initial[key] = value
                    self.fields[key].widget.attrs["class"] = "form-control"
            for name in ("principal", "rate"):
                self.fields[name].required = False
                self.fields[name].widget = forms.HiddenInput()
        for key in ("operation", "target", "amount", "before"):
            del self.fields[key]
        self.fields["date"].required = True
        self.fields["date"].label = "Correct original loan date"
        self.fields["reference"].required = True
        self.fields["reference"].max_length = 160
        self.fields["reference"].label = "Supporting original book / page reference"
        if predecessor:
            from apps.tenant_apps.loans.services.recorded_settlement_corrections import renewal_cash
            cash = renewal_cash(predecessor)
            for name, label in (("cash_received", "Actual net cash received for the predecessor renewal"),
                ("cash_paid", "Actual net cash paid for the predecessor renewal"),
                ("interest_offset", "Predecessor interest offset from the new advance")):
                self.fields["predecessor_" + name] = forms.DecimalField(max_digits=14, decimal_places=2, min_value=0, label=label)
                self.initial["predecessor_" + name] = cash[name]
            self.fields["predecessor_reference"] = forms.CharField(max_length=255, label="Source confirming the paired renewal cash")
            self.fields["predecessor_confirmed_custody"] = forms.BooleanField(
                label="The predecessor renewal date, loan numbers and actual collateral handover remain correct. I checked the corrected paired cash.")
            for field in self.fields.values():
                field.widget.attrs["class"] = "form-check-input" if isinstance(field.widget, forms.CheckboxInput) else "form-select" if isinstance(field.widget, forms.Select) else "form-control"


    def clean(self):
        values = super().clean()
        if len(self.collateral_items) > 1:
            rows = [dict(principal=values.get(f"contract_item_{item.pk}_principal"),
                         rate=values.get(f"contract_item_{item.pk}_rate")) for item in self.collateral_items]
            if all(row["principal"] is not None and row["rate"] is not None for row in rows):
                from decimal import Decimal
                from apps.tenant_apps.loans.services.recorded_items import effective_rate
                values["principal"] = sum((row["principal"] for row in rows), Decimal("0"))
                values["rate"] = effective_rate(rows)
        return values


def _item_splits(values):
    split, replay = {}, {}
    for name in list(values):
        if name.startswith("item_principal_"):
            amount = values.pop(name)
            if amount is not None:
                split[name.removeprefix("item_principal_")] = str(amount)
        elif name.startswith("replay_"):
            _, event, item = name.split("_")
            amount = values.pop(name)
            if amount is not None:
                replay.setdefault(event, {})[item] = str(amount)
    if split:
        values["item_principal_split"] = split
    if replay:
        values["replay_item_splits"] = replay


@loans_action_required(LOANS_ADMIN_ACTION)
@never_cache
def contract_correction(request, pk):
    from apps.tenant_apps.loans.services.recorded_contract_corrections import preview_contract_correction, record_contract_correction
    loan = get_object_or_404(m.PawnLoan, pk=pk, workspace=request.loans_workspace)
    _, active, blockers = dependencies(loan)
    from apps.tenant_apps.loans.selectors.recorded_settlements import current_settlement
    relation = m.PawnLoanRenewal.objects.filter(successor_loan=loan).first()
    predecessor = current_settlement(relation.settlement_event) if relation else None
    from decimal import Decimal
    origin = next((event for event in active if event.event_kind in ("DISBURSAL", "RENEWAL_OPENING")), None)
    economics = origin.payload.get("renewal", {}).get("successor_economics", {}) if origin else {}
    proceeds = (loan.disbursal_snapshot.net_disbursed if loan.disbursal_snapshot_id else
        Decimal(origin.payload["values"]["principal"]) - Decimal(economics["advance_interest"]) - Decimal(economics["deducted_fees"]) if economics else None)
    form = ContractCorrectionForm(request.POST if request.method == "POST" else None,
        initial=dict(request_key=uuid4().hex, date=loan.loan_date, principal=loan.principal_amount,
            rate=loan.monthly_interest_rate, cash_paid=proceeds),
        settlement=next((event for event in active if event.event_kind in ("RELEASE_RECEIPT", "RENEWAL_SETTLEMENT")), None),
        predecessor=predecessor, collateral_items=list(loan.collateral_items.order_by("pk")),
        replay_receipts=[event for event in active if event.event_kind == "REPAYMENT"])
    review = None
    if request.method == "POST" and form.is_valid():
        values = {key: value for key, value in form.cleaned_data.items() if key not in ("review_token", "confirmed")}
        _item_splits(values)
        if len(form.collateral_items) > 1:
            values["items"] = [dict(item_id=item.pk,
                principal=str(values.pop(f"contract_item_{item.pk}_principal")),
                rate=str(values.pop(f"contract_item_{item.pk}_rate"))) for item in form.collateral_items]
        values["date"] = values["date"].isoformat()
        for key in ("principal", "rate", "cash_paid"):
            values[key] = str(values[key])
        settlement = {key.removeprefix("settlement_"): values.pop(key) for key in list(values) if key.startswith("settlement_")}
        if settlement:
            for key in ("cash_received", "cash_paid", "interest_offset"):
                settlement[key] = str(settlement[key]) if settlement[key] is not None else None
            values["settlement"] = settlement
        predecessor = {key.removeprefix("predecessor_"): values.pop(key) for key in list(values) if key.startswith("predecessor_")}
        if predecessor:
            for key in ("cash_received", "cash_paid", "interest_offset"):
                predecessor[key] = str(predecessor[key])
            values["predecessor"] = predecessor
        try:
            if request.POST.get("action") == "confirm":
                _, created = record_contract_correction(loan.pk, actor=request.user, data=values,
                    review_token=form.cleaned_data["review_token"], confirmed=form.cleaned_data["confirmed"])
                messages.success(request, "Contract correction recorded." if created else "This contract correction was already recorded.")
                return redirect("workspace_loans:pawn_loan_detail", workspace_slug=request.workspace.slug, pk=loan.pk)
            review, token = preview_contract_correction(loan.pk, actor=request.user, data=values)
            form.data = form.data.copy()
            form.data["review_token"] = token
        except (ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
    return render(request, "loans/pawn/contract_correction.html", dict(loan=loan, form=form, review=review, blockers=blockers))


class SettlementFactsForm(forms.Form):
    date = forms.DateField(label="Correct actual closing date", widget=forms.DateInput(attrs={"type": "date"}))
    amount = forms.DecimalField(max_digits=14, decimal_places=2, min_value=0, label="Correct closing settlement amount")
    recipient = forms.CharField(required=False, max_length=255, label="Correct customer return recipient",
        help_text="Leave blank if the original closing record did not confirm customer handover.")
    reference = forms.CharField(max_length=255, label="Source confirming the corrected closing facts")
    reason = forms.CharField(max_length=500, widget=forms.Textarea(attrs={"rows":3}), label="Why this entry needs correction")
    request_key = forms.CharField(max_length=80, widget=forms.HiddenInput)
    review_token = forms.CharField(required=False, widget=forms.HiddenInput)
    confirmed = forms.BooleanField(required=False, label="I checked the corrected closing date, amount and custody facts. No new physical movement occurred.")


@loans_action_required(LOANS_ADMIN_ACTION)
@never_cache
def settlement_facts(request, pk):
    from apps.tenant_apps.loans.services.recorded_settlement_facts import preview_settlement_facts, record_settlement_facts
    from apps.tenant_apps.loans.selectors.recorded_settlements import restated_release
    loan = get_object_or_404(m.PawnLoan, pk=pk, workspace=request.loans_workspace)
    release = loan.releases.order_by("pk").first()
    current = restated_release(release) if release else None
    paper = current.loan_event.payload.get("release", {}).get("paper_closure", {}) if current else {}
    form = SettlementFactsForm(request.POST if request.method == "POST" else None,
        initial=dict(date=current.effective_date if current else None, amount=current.settlement_amount if current else None,
            recipient=paper.get("collector_name", ""), request_key=uuid4().hex))
    from .recorded_history import _style
    _style(form)
    review = None
    if request.method == "POST" and form.is_valid():
        data = {k:v for k,v in form.cleaned_data.items() if k not in ("review_token","confirmed")}
        data.update(date=data["date"].isoformat(), amount=str(data["amount"]))
        try:
            if request.POST.get("action") == "confirm":
                _, created = record_settlement_facts(loan.pk, actor=request.user, data=data,
                    review_token=form.cleaned_data["review_token"], confirmed=form.cleaned_data["confirmed"])
                messages.success(request, "Closing facts corrected." if created else "Closing correction already recorded.")
                return redirect("workspace_loans:pawn_loan_detail", workspace_slug=request.workspace.slug, pk=loan.pk)
            review, token = preview_settlement_facts(loan.pk, actor=request.user, data=data)
            form.data = form.data.copy()
            form.data["review_token"] = token
        except (ValueError, ValidationError) as exc:
            form.add_error(None, str(exc))
    return render(request, "loans/pawn/settlement_facts.html", dict(loan=loan, form=form, review=review))
