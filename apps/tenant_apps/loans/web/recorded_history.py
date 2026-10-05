"""Paper-first entry within the ordinary New loan route."""
from decimal import Decimal
from django import forms
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist, ValidationError, PermissionDenied
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.tenant_apps.loans import models as m
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.loans.services.recorded_history import (
    new_recording_intent, preview_recorded_history, admit_recorded_history,
)

DAY = {"type": "date"}


class PaperCollateralForm(forms.Form):
    description = forms.CharField(max_length=255, label="Item description")
    quantity = forms.IntegerField(min_value=1, max_value=10000, initial=1)
    metal = forms.ChoiceField(choices=(("GOLD", "Gold"), ("SILVER", "Silver")), initial="GOLD")
    gross_weight = forms.DecimalField(max_digits=12, decimal_places=4, min_value=Decimal("0.0001"), label="Gross weight (g)")
    net_weight = forms.DecimalField(max_digits=12, decimal_places=4, min_value=Decimal("0.0001"), label="Net weight (g)")
    purity_percentage = forms.DecimalField(max_digits=7, decimal_places=4, min_value=Decimal("0.0001"), max_value=100, initial=75, label="Purity (%)")
    allocated_principal = forms.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"), label="Principal for this item (INR)")
    interest_rate_override = forms.DecimalField(max_digits=9, decimal_places=6, min_value=0, max_value=100,
        label="Agreed monthly interest (%)", help_text="Supplied from dated setup. Use Different paper terms to record an actual exception.")

    def __init__(self, *args, exceptions=False, **kwargs):
        super().__init__(*args, **kwargs)
        _style(self)
        if not exceptions:
            self.fields["interest_rate_override"].widget.attrs["readonly"] = True

    def clean(self):
        value = super().clean()
        if value.get("net_weight") and value.get("gross_weight") and value["net_weight"] > value["gross_weight"]:
            self.add_error("net_weight", "Net weight cannot exceed gross weight.")
        return value


PaperCollateralFormSet = forms.formset_factory(PaperCollateralForm, extra=0, min_num=1,
    validate_min=True, max_num=100, validate_max=True, absolute_max=100, can_delete=True)


class PaperHistoryForm(forms.Form):
    routine_entry = forms.BooleanField(required=False, initial=True, widget=forms.HiddenInput)
    exceptions = forms.BooleanField(required=False, label="Paper agreement differs from standard terms")
    exception_reason = forms.CharField(required=False, max_length=160, label="Source explanation for different terms")
    borrower_id = forms.ModelChoiceField(queryset=Party.objects.none(), label="Customer")
    series_id = forms.ModelChoiceField(queryset=m.LoanSeries.objects.none(), label="Series (license / register)")
    product_version_id = forms.ModelChoiceField(queryset=m.LoanProductVersion.objects.none(), label="Loan product")
    number = forms.CharField(max_length=64, label="Original loan number")
    date = forms.DateField(widget=forms.DateInput(attrs=DAY), label="Loan date")
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
    monitoring_ltv = forms.DecimalField(max_digits=7, decimal_places=6, min_value=Decimal("0.000001"), max_value=1,
        label="Monitoring LTV ratio", help_text="For example, 0.80 means 80%. This does not reapprove the original loan.")
    monitoring_reason = forms.CharField(max_length=255, label="Reason for monitoring choice")
    complete_through = forms.DateField(widget=forms.DateInput(attrs=DAY), label="All paper activity entered through")
    final_state = forms.ChoiceField(label="State after the final transaction", choices=(
        ("ACTIVE","This loan is outstanding"), ("CLOSED","This loan is closed according to its paper record")))
    currency_quantum = forms.ChoiceField(label="Agreement interest rounding", initial="0.01",
        choices=(("0.01", "Paise"), ("1", "Whole rupees")), required=False)
    confirmed_rule = forms.BooleanField(label="The agreed rule is simple monthly interest: the next month starts the day after the original loan anniversary; principal reductions apply from the next boundary.")
    confirmed_history = forms.BooleanField(label="I checked this loan's paper record through the stated date and checked for duplicates. No earlier or later loan's renewal history is required.")

    def __init__(self, *args, workspace, routine=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.routine = routine and (not self.is_bound or self.data.get("routine_entry") in ("on", "true", "True", "1"))
        self.terms = None
        item_sources, item_messages = [], []
        self.itemized = self.routine and (not self.is_bound or "collateral-TOTAL_FORMS" in self.data)
        self.fields["borrower_id"].queryset = Party.objects.filter(workspace=workspace, status="ACTIVE")
        self.fields["series_id"].queryset = m.LoanSeries.objects.filter(workspace=workspace).select_related("license")
        self.fields["product_version_id"].queryset = m.LoanProductVersion.objects.filter(workspace=workspace,
            status="ACTIVE", repayment_structure__in=("SINGLE_PAYMENT_BULLET", "FLEXIBLE_PARTIAL_PAYMENT"), amortisation_method="NONE").select_related("product")
        if self.routine:
            for name, value in dict(date=timezone.localdate(), metal="GOLD", quantity=1, final_state="ACTIVE").items():
                self.initial.setdefault(name, value)
            choices = list(self.fields["series_id"].queryset.values_list("pk", flat=True)[:2])
            if len(choices) == 1 and not self.initial.get("series_id"):
                self.initial["series_id"] = choices[0]
            self.fields["confirmed_history"].required = False
            self.fields["confirmed_history"].label = "All paper activity for this loan has been checked and entered through the date below (optional)"
            self.fields["complete_through"].required = False
            self.fields["confirmed_rule"].required = False
            if self.is_bound:
                from apps.tenant_apps.loans.services.paper_entry_terms import paper_entry_terms, preferred_paper_product
                data = self.data.copy()
                if self.itemized:
                    try:
                        count = min(100, int(data.get("collateral-TOTAL_FORMS", 0)))
                        actual = []
                        for index in range(count):
                            prefix = f"collateral-{index}-"
                            if data.get(prefix + "DELETE") in ("on", "1", "true"):
                                continue
                            item = {name: data.get(prefix + name) for name in ("description", "metal", "quantity", "gross_weight", "net_weight")}
                            item.update(purity=data.get(prefix + "purity_percentage"), principal=data.get(prefix + "allocated_principal"),
                                        rate=data.get(prefix + "interest_rate_override"))
                            if data.get("exceptions") not in ("on", "true", "True", "1"):
                                series = self.fields["series_id"].clean(data.get("series_id"))
                                day = self.fields["date"].clean(data.get("date"))
                                defaults = paper_entry_terms(workspace=workspace, series=series, day=day, metal=item["metal"])
                                item_sources.extend(defaults["sources"])
                                item_messages.extend(defaults["messages"])
                                item["rate"] = str(defaults["values"].get("rate", ""))
                                data[prefix + "interest_rate_override"] = item["rate"]
                            actual.append(item)
                        if actual:
                            from apps.tenant_apps.loans.services.recorded_items import effective_rate, monthly_interest
                            data.update({name: actual[0][name] for name in ("description", "metal", "quantity", "gross_weight", "net_weight", "purity")})
                            data["principal"] = str(sum((Decimal(row["principal"]) for row in actual), Decimal("0")))
                            data["rate"] = str(effective_rate(actual))
                            quantum = (defaults["values"].get("currency_quantum", "0.01")
                                if data.get("exceptions") not in ("on", "true", "True", "1") else data.get("currency_quantum") or "0.01")
                            self.item_monthly = monthly_interest(actual, Decimal(str(quantum)))
                    except (ValidationError, ValueError, TypeError, ArithmeticError, ObjectDoesNotExist):
                        pass
                self.data = data
                try:
                    series = self.fields["series_id"].clean(data.get("series_id"))
                    day = self.fields["date"].clean(data.get("date"))
                    metal = self.fields["metal"].clean(data.get("metal"))
                    try:
                        principal = self.fields["principal"].clean(data.get("principal")) if data.get("principal") else None
                    except ValidationError:
                        principal = None
                    self.terms = paper_entry_terms(workspace=workspace, series=series, day=day, metal=metal, principal=principal)
                    self.terms["sources"] = list(dict.fromkeys(self.terms["sources"] + item_sources))
                    self.terms["messages"] = list(dict.fromkeys(self.terms["messages"] + item_messages))
                    preferred = preferred_paper_product(workspace=workspace, day=day)
                    if not data.get("product_version_id") and preferred:
                        data["product_version_id"] = str(preferred.pk)
                    if data.get("exceptions") not in ("on", "true", "True", "1"):
                        for name, value in self.terms["values"].items():
                            if name == "rate" and self.itemized:
                                continue
                            data[name] = "" if value is None else str(value)
                        data["document_charge"] = str(self.terms["values"].get("document_charge", ""))
                        data["cash_paid"] = ""
                    data["payout_basis"] = data.get("payout_basis") or "PROCEEDS"
                    data["confirmed_rule"] = "on"
                    self.data = data
                except (ValidationError, ValueError, ObjectDoesNotExist):
                    pass
            if self.is_bound and self.data.get("action") == "terms":
                for name, field in self.fields.items():
                    field.required = name in ("series_id", "date", "metal")
        if self.itemized:
            for name in ("description", "metal", "quantity", "gross_weight", "net_weight", "purity"):
                self.fields[name].required = False
            self.fields["principal"].widget.attrs["readonly"] = True
            self.fields["rate"].widget = forms.HiddenInput()
        _style(self)

    def clean(self):
        data = super().clean()
        data["currency_quantum"] = data.get("currency_quantum") or "0.01"
        if not self.routine or self.data.get("action") == "terms":
            return data
        if data.get("exceptions") and not data.get("exception_reason", "").strip():
            self.add_error("exception_reason", "Identify why the actual paper terms differ.")
        if data.get("confirmed_history") and not data.get("complete_through"):
            self.add_error("complete_through", "Enter the actual date through which the paper activity was checked.")
        if not data.get("exceptions") and self.terms:
            missing = [name for name in ("rate", "tenure", "advance_months", "document_charge", "monitoring_method", "monitoring_ltv")
                       if self.terms["values"].get(name) is None]
            if missing:
                self.add_error(None, "Complete standing setup or select Paper agreement differs and enter the actual supported terms: " + ", ".join(missing) + ".")
        elif not data.get("exceptions"):
            self.add_error(None, "Choose a valid series, original date, metal and principal to resolve standing terms.")
        return data

    @property
    def deductions(self):
        from decimal import ROUND_HALF_UP, InvalidOperation
        try:
            principal, rate, fee = (Decimal(str(self[name].value())) for name in ("principal", "rate", "document_charge"))
            months = int(self["advance_months"].value())
            if not all(value.is_finite() and value >= 0 for value in (principal, rate, fee)) or months not in (0, 1):
                return None
            advance = getattr(self, "item_monthly", (principal * rate / 100).quantize(Decimal(str(self["currency_quantum"].value() or "0.01")), rounding=ROUND_HALF_UP)) * months
            return dict(advance=advance, proceeds=principal - advance - fee)
        except (InvalidOperation, TypeError, ValueError):
            return None


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

    def __init__(self, *args, collateral_labels=(), **kwargs):
        super().__init__(*args, **kwargs)
        if len(collateral_labels) > 1:
            for position, label in enumerate(collateral_labels, start=1):
                self.fields[f"item_principal_{position}"] = forms.DecimalField(required=False,
                    max_digits=14, decimal_places=2, min_value=0,
                    label=f"Principal paid: item {position} — {label}",
                    help_text="For receipts only. Enter the principal applied to this item after interest; leave blank for interest-only receipts.")
        _style(self)

    def has_changed(self):
        if self.is_bound and self.empty_permitted and all(self[name].value() in (
                (None, "", "PAPER_SETTLEMENT") if name == "closure_basis" else (None, "", False))
                for name in self.fields):
            return False
        return super().has_changed()


def _style(form):
    for field in form.fields.values():
        field.widget.attrs["class"] = "form-check-input" if isinstance(field.widget, forms.CheckboxInput) else (
            "form-select" if isinstance(field.widget, forms.Select) else "form-control")


Transactions = forms.formset_factory(PaperTransactionForm, extra=1, max_num=30, validate_max=True, absolute_max=30, can_delete=True)


def _data(form, rows, collateral=None):
    value = dict(form.cleaned_data)
    value.pop("routine_entry", None)
    exceptions = value.pop("exceptions", False)
    reason = value.pop("exception_reason", "")
    value["document_charge"] = value["document_charge"] or Decimal("0")
    if value["cash_paid"] is None:
        from decimal import ROUND_HALF_UP
        advance = getattr(form, "item_monthly", (value["principal"] * value["rate"] / 100).quantize(Decimal(value["currency_quantum"]), rounding=ROUND_HALF_UP)) * value["advance_months"]
        value["cash_paid"] = value["principal"] - advance - value["document_charge"]
    for name in ("borrower_id", "series_id", "product_version_id"):
        value[name] = value[name].pk
    value["events"] = [{key: val for key, val in row.cleaned_data.items() if key != "DELETE"}
                       for row in rows if row.cleaned_data and not row.cleaned_data.get("DELETE")]
    # Values crossing the signed review/storage boundary use canonical JSON types.
    for row in value["events"]:
        split = {name.removeprefix("item_principal_"): row.pop(name) for name in list(row) if name.startswith("item_principal_")}
        if any(amount is not None for amount in split.values()):
            row["item_principal_split"] = {key: str(amount or Decimal("0")) for key, amount in split.items()}
        if row["kind"] == "CLOSE" and not row["closure_basis"]:
            row["closure_basis"] = "RETURNED"
    if form.routine:
        value["recording_mode"] = "TRANSACTION_ENTRY"
        value["confirmed_rule"] = True
        if not value["confirmed_history"]:
            value["complete_through"] = timezone.localdate()
        sources = "; ".join((form.terms or {}).get("sources", []))
        value["entry_note"] = (("Actual exception: " + reason) if exceptions else ("Standing terms: " + sources))[:255]
    if collateral is not None:
        value["collateral"] = [dict(description=row.cleaned_data["description"], quantity=row.cleaned_data["quantity"],
            metal=row.cleaned_data["metal"], gross_weight=row.cleaned_data["gross_weight"], net_weight=row.cleaned_data["net_weight"],
            purity=row.cleaned_data["purity_percentage"], principal=row.cleaned_data["allocated_principal"],
            rate=row.cleaned_data["interest_rate_override"]) for row in collateral if row.cleaned_data and not row.cleaned_data.get("DELETE")]
    import json
    return json.loads(json.dumps(value, default=lambda obj: obj.isoformat() if hasattr(obj, "isoformat") else str(obj)))


def paper_history_entry(request, *, draft=None):
    workspace, actor = request.loans_workspace, request.user
    presentation = getattr(request, "loan_entry_presentation", {})
    post = request.POST.copy() if request.method == "POST" else None
    if post is not None and "payout_basis" not in post:
        post["payout_basis"] = "PROCEEDS" if post.get("routine_entry") else "CASH"
    archive_id = post.get("archive_evidence_id") if post is not None else request.GET.get("archive")
    archive, initial, initial_rows, snapshots = None, {}, [], []
    initial_collateral = []
    draft_items = []
    if draft:
        initial = dict(borrower_id=draft.borrower_id, series_id=draft.series_id,
            product_version_id=draft.product_version_id, number=draft.loan_number, date=draft.loan_date,
            principal=draft.principal_amount, rate=draft.monthly_interest_rate, tenure=draft.tenure_months)
        draft_items = list(draft.collateral_items.prefetch_related("photos").order_by("pk"))
        initial_collateral = [dict(description=item.description, quantity=item.quantity, metal=item.metal,
            gross_weight=item.gross_weight, net_weight=item.net_weight, purity_percentage=item.purity_percentage,
            allocated_principal=item.allocated_principal,
            interest_rate_override=item.monthly_interest_rate if item.monthly_interest_rate is not None else draft.monthly_interest_rate)
            for item in draft_items]
        if post is not None:
            for name in ("borrower_id", "series_id", "product_version_id", "number", "date"):
                value = initial[name]
                post[name] = value.isoformat() if hasattr(value, "isoformat") else str(value)
    if not draft and request.GET.get("series"):
        initial["series_id"] = request.GET["series"]
    if not draft and request.GET.get("party"):
        initial["borrower_id"] = request.GET["party"]
    if archive_id and draft:
        raise PermissionDenied("Archive admission and existing draft recording are separate source contexts.")
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
    intent = (post.get("intent_token", "") if post is not None else "") or new_recording_intent(
        workspace=workspace, actor=actor, draft_id=draft.pk if draft else None)
    if post is not None and post.get("action") == "add":
        try:
            post["events-TOTAL_FORMS"] = str(min(30, int(post.get("events-TOTAL_FORMS", "3")) + 1))
        except ValueError:
            pass
    if post is not None and post.get("action") == "add_collateral":
        try:
            post["collateral-TOTAL_FORMS"] = str(min(100, int(post.get("collateral-TOTAL_FORMS", "1")) + 1))
        except ValueError:
            pass
    form = PaperHistoryForm(post, workspace=workspace, initial=initial, routine=not archive)
    if draft:
        form.fields["borrower_id"].queryset = Party.objects.filter(workspace=workspace, pk=draft.borrower_id)
        form.fields["product_version_id"].queryset = m.LoanProductVersion.objects.filter(workspace=workspace, pk=draft.product_version_id)
        for name in ("borrower_id", "series_id", "product_version_id", "number", "date"):
            form.fields[name].disabled = True
    collateral = PaperCollateralFormSet(form.data if post is not None else None, prefix="collateral",
        initial=initial_collateral,
        form_kwargs={"exceptions": bool(form["exceptions"].value())}) if form.itemized else None
    if draft and collateral is not None:
        for row, item in zip(collateral, draft_items):
            row.existing_collateral_item = item
    if archive:
        form.fields["final_state"].choices = (("CLOSED", "All debt settled; state the known handover facts below"),)
        form.fields["reconciliation"] = forms.CharField(max_length=1000, widget=forms.Textarea(attrs={"rows": 3}),
            label="Checked sources for original terms, missing facts and known custody",
            help_text="Identify supporting records for borrower, complete financial history and known handover facts. Leave handover unconfirmed when the source does not establish it.")
        form.fields["confirmed_history"].label = "I checked the archive and supporting records. This complete history has not already been admitted as an ordinary loan."
        form.fields["payout_basis"].initial = "CASH"
        _style(form)
    labels = [row["description"].value() or "Collateral" for row in collateral if not row["DELETE"].value()] if collateral is not None else []
    rows = Transactions(post, prefix="events", initial=initial_rows, form_kwargs={"collateral_labels": labels})
    if presentation.get("entry_changing"):
        from .entry_presentation import presentation_errors
        presentation_errors(form, collateral)
        for row in rows:
            row._errors = forms.utils.ErrorDict()
        rows._errors = [forms.utils.ErrorDict() for row in rows]
        rows._non_form_errors = rows.error_class()
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
    if post is not None and post.get("action") not in ("add", "add_collateral", "terms", "entry_change") and form.is_valid() and rows.is_valid() and (collateral is None or collateral.is_valid()):
        try:
            data = _data(form, rows, collateral)
            reconciliation = data.pop("reconciliation", "")
            if archive:
                from apps.tenant_apps.loans.services.archive_admission import preview_archive_admission, admit_archive_history
                preview, admit = preview_archive_admission, admit_archive_history
                extra = dict(evidence_id=archive.public_id, reconciliation=reconciliation)
            else:
                preview, admit = preview_recorded_history, admit_recorded_history
                extra = dict(draft_id=draft.pk) if draft else {}
            if post.get("action") == "confirm":
                loan, created = admit(workspace=workspace, actor=actor, data=data, intent_token=intent, **extra,
                    review_token=post.get("review_token"), confirmed=post.get("confirm_review") == "on")
                messages.success(request, "Paper history recorded." if created else "This history was already recorded; no duplicate was created.")
                return redirect("workspace_loans:pawn_loan_detail", workspace_slug=workspace.slug, pk=loan.pk)
            review, token = preview(workspace=workspace, actor=actor, data=data, intent_token=intent, **extra)
        except (ValueError, ValidationError, ObjectDoesNotExist) as exc:
            form.add_error(None, str(exc))
    sections = [("Original contract", ("borrower_id", "series_id", "product_version_id", "number", "date", "source_reference", "principal", "rate", "tenure", "advance_months", "currency_quantum", "document_charge", "payout_basis", "cash_paid")),
        ("Collateral", ("description", "metal", "quantity", "gross_weight", "net_weight", "purity")),
        ("Current monitoring", ("monitoring_method", "monitoring_ltv", "monitoring_reason")),
        ("Completeness and agreed calculation", ("complete_through", "final_state", "confirmed_rule", "confirmed_history"))]
    if archive:
        sections.append(("Archive reconciliation", ("reconciliation",)))
    if form.routine:
        sections = [("Loan details", ("borrower_id", "series_id", "product_version_id", "number", "date", "source_reference", "principal")),
            ("Jewellery", ("description", "metal", "quantity", "gross_weight", "net_weight", "purity"))]
    if collateral is not None:
        sections = [section for section in sections if section[0] != "Jewellery"]
    return render(request, "loans/pawn/paper_history.html", dict(form=form, rows=rows, review=review,
        formset=collateral, entry_purpose="paper",
        archive=archive, archive_snapshots=snapshots, review_token=token, intent_token=intent,
        completed_draft=draft, loan=draft, form_action=request.path if draft else None,
        sections=[(title, [form[name] for name in names]) for title, names in sections], **presentation))
