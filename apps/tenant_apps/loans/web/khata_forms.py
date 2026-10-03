"""Small, workspace-scoped forms for the separate khata workflows."""
from decimal import Decimal

from django import forms
from django.db.models import Q
from django.urls import reverse

from apps.tenant_apps.party.models import Party
from apps.tenant_apps.party.widgets import PartyAutocompleteWidget
from apps.tenant_apps.loans.models import KhataSeries, KhataAgreementRevision, LoanLicense, KhataCollateralSelection
from apps.tenant_apps.loans.selectors.khata import held_items, eligible_items
from apps.tenant_apps.loans.selectors.khata_items import collateral_items
from apps.tenant_apps.loans.selectors.khata_workflow import activation_approvals


def money(label, *, required=True, initial=None):
    return forms.DecimalField(label=label, max_digits=18, decimal_places=2,
        min_value=Decimal("0"), required=required, initial=initial)


class StyledForm(forms.Form):
    request_key = forms.UUIDField(widget=forms.HiddenInput())

    def style(self):
        for field in self.fields.values():
            if isinstance(field, forms.ModelChoiceField):
                field.label_from_instance = lambda obj: (
                    f"Item {obj.pk}: {obj.description}" if hasattr(obj, "description") else
                    f"Operation {obj.pk}: {obj.get_kind_display()} / {obj.business_date}" if hasattr(obj, "business_date") else str(obj))
            if not field.widget.is_hidden:
                field.widget.attrs["class"] = ("form-check-input" if isinstance(field.widget, forms.CheckboxInput)
                    else "form-select" if isinstance(field.widget, forms.Select) else "form-control")

    def clean(self):
        data = super().clean()
        if data.get("net_weight") is not None and data.get("gross_weight") is not None and data["net_weight"] > data["gross_weight"]:
            self.add_error("net_weight", "Net weight cannot exceed gross weight.")
        if "value" in data and data["value"] <= 0:
            self.add_error("value", "Enter a positive actual amount.")
        return data


class TermsForm(StyledForm):
    agreed_limit = money("Agreed borrowing limit (INR)")
    monthly_rate = forms.DecimalField(label="Interest rate (% per month)", max_digits=10,
        decimal_places=6, min_value=0, max_value=Decimal("9999.999999"),
        help_text="The rate is always monthly, including when interest is collected annually.")
    ltv_percent = forms.DecimalField(label="Agreed LTV (%)", max_digits=9, decimal_places=4,
        min_value=Decimal("0.0001"), max_value=100, initial=75)
    frequency = forms.ChoiceField(label="Interest payment frequency", choices=KhataAgreementRevision.Frequency.choices)
    lender_name = forms.CharField(max_length=255)
    lender_address = forms.CharField(max_length=1000, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, workspace, account=None, borrower_search=None, **kwargs):
        super().__init__(*args, **kwargs)
        if account:
            self.fields["expected_revision"] = forms.IntegerField(widget=forms.HiddenInput())
            self.fields["reason"] = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={"rows": 2}))
            if account.opened_on:
                for name in ("ltv_percent", "frequency", "lender_name", "lender_address"):
                    self.fields[name].disabled = True
        else:
            self.fields["series"] = forms.ModelChoiceField(queryset=KhataSeries.objects.filter(workspace=workspace, is_active=True).order_by("name"))
            self.fields["borrower"] = forms.ModelChoiceField(queryset=Party.objects.filter(workspace=workspace, status="ACTIVE").order_by("display_name"))
            if borrower_search is None:
                self.fields["borrower"].widget = PartyAutocompleteWidget(data_url=reverse("workspace_party:party_autocomplete", args=(workspace.slug,)),
                    attrs={"data-placeholder": "Search name, party code or phone"}, select2_options={"width": "100%"})
            else:
                parties = self.fields["borrower"].queryset
                if borrower_search:
                    parties = parties.filter(Q(display_name__icontains=borrower_search) | Q(party_code__icontains=borrower_search) | Q(primary_phone__icontains=borrower_search))
                ids = list(parties.values_list("pk", flat=True)[:25])
                value = self.data.get("borrower") if self.is_bound else self.initial.get("borrower")
                if str(value).isdecimal() and len(str(value)) <= 18:
                    ids.append(int(value))
                self.fields["borrower"].queryset = self.fields["borrower"].queryset.filter(pk__in=ids)
        self.order_fields(("series", "borrower", "agreed_limit", "monthly_rate", "ltv_percent", "frequency", "lender_name", "lender_address", "reason", "expected_revision", "request_key"))
        self.style()

    def clean_agreed_limit(self):
        value = self.cleaned_data["agreed_limit"]
        if value <= 0:
            raise forms.ValidationError("Enter a positive agreed limit.")
        return value


class SeriesForm(StyledForm):
    code = forms.CharField(max_length=32)
    name = forms.CharField(max_length=120)
    prefix = forms.RegexField(r"^[A-Z][A-Z-]{0,15}$", max_length=16, initial="KH")
    width = forms.IntegerField(min_value=1, max_value=12, initial=5)
    maximum_number = forms.IntegerField(min_value=1, max_value=999999999999, initial=99999)

    def __init__(self, *args, workspace, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop("request_key")
        self.fields["license"] = forms.ModelChoiceField(label="Associated licence (optional)", required=False,
            queryset=LoanLicense.objects.filter(workspace=workspace, is_active=True, is_legacy_reference=False),
            help_text="Leave blank for an independent khata series. The association freezes after its first number.")
        self.style()


class PolicyForm(StyledForm):
    exchange = forms.ChoiceField(label="Exchange shortfall or LTV breach", choices=(("WARN", "Allow with warning"), ("BLOCK", "Disallow")))
    overdue = forms.ChoiceField(label="Overdue interest before withdrawal or exchange", choices=(("WARN", "Allow with warning"), ("BLOCK", "Disallow")))
    reason = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style()


class ActionForm(StyledForm):
    """Explicit fields, with every item/source choice constrained to this account."""
    def __init__(self, *args, account, action, replaying=False, actor=None, **kwargs):
        super().__init__(*args, **kwargs)
        text = lambda label: forms.CharField(label=label, max_length=2000)
        held = account.collateral.all() if replaying else held_items(account)
        eligible = account.collateral.all() if replaying else eligible_items(account)
        items = lambda label, multiple=False: (forms.ModelMultipleChoiceField if multiple else forms.ModelChoiceField)(
            label=label, queryset=eligible if multiple else held)
        if action == "deposit":
            self.fields.update(description=forms.CharField(label="Collateral description", max_length=500),
                metal=forms.ChoiceField(choices=(("GOLD", "Gold"), ("SILVER", "Silver"))),
                quantity=forms.IntegerField(min_value=1),
                gross_weight=forms.DecimalField(label="Gross weight (g)", max_digits=12, decimal_places=3, min_value=Decimal("0.001")),
                net_weight=forms.DecimalField(label="Net weight (g)", max_digits=12, decimal_places=3, min_value=Decimal("0.001")),
                purity=forms.DecimalField(label="Purity (%)", max_digits=7, decimal_places=4, min_value=Decimal("0.0001"), max_value=100),
                storage_reference=forms.CharField(label="Storage reference", max_length=160), received_from=text("Received from"),
                upload=forms.FileField(label="Photograph (optional)", required=False,
                    widget=forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png"})),
                receipt_confirmed=forms.BooleanField(label="I confirm this collateral has actually been received."))
        elif action == "photo":
            self.fields.update(item=items("Held collateral item"), upload=forms.FileField(label="JPEG or PNG photo"))
        elif action in ("withdraw", "interest"):
            self.fields.update(value=money("Actual amount (INR)"), payment_reference=text("Actual payment reference"))
        elif action == "exchange":
            self.fields.update(outgoing=items("Collateral to return", True), incoming=items("Received collateral replacing these items", True), reason=text("Exchange reason"))
            if not replaying:
                self.fields["incoming"].queryset = eligible.exclude(pk__in=KhataCollateralSelection.objects.filter(
                    role="IN", operation__corrected_by__isnull=True).values("item_id"))
            for name in ("outgoing", "incoming"):
                self.fields[name].widget = forms.MultipleHiddenInput()
        elif action == "approve-change":
            self.fields.update(principal_repayment=money("Principal repayment at activation (INR)", initial=0),
                outgoing=forms.ModelMultipleChoiceField(label="Collateral to return on reduction (optional)", queryset=eligible, required=False),
                agreement_reference=text("Borrower's consent / agreement reference"))
        elif action == "activate-change":
            self.fields.update(approval=forms.ModelChoiceField(label="Approved terms", queryset=account.operations.filter(kind="TERMS_OK") if replaying else activation_approvals(account, actor),
                help_text="Only current, unused approvals for today are listed. Changes to source evidence require approval again."),
                payment_reference=forms.CharField(label="Actual principal payment reference (required when collecting principal)", max_length=2000, required=False))
        elif action == "handover":
            self.fields.update(item=items("Reserved collateral item"),
                parent=forms.ModelChoiceField(label="Return reservation source", queryset=account.operations.filter(
                    kind__in=("EXCHANGE", "REVISE", "SETTLE", "CORRECT"), corrected_by__isnull=True)),
                recipient=text("Actual recipient"), reference=text("Actual handover reference"))
            if not replaying:
                self.fields["item"].queryset = collateral_items(account, mode="pending")
        elif action == "return-unopened":
            self.fields.update(item=items("Held collateral item"), recipient=text("Actual recipient"), reason=text("Return reason"))
        elif action == "settle":
            self.fields["payment_reference"] = text("Actual settlement payment reference")
        elif action == "correct":
            sources = account.operations.filter(kind__in=("INTEREST", "EXCHANGE"))
            if not replaying:
                sources = sources.filter(corrected_by__isnull=True)
            self.fields.update(source=forms.ModelChoiceField(label="Source operation", queryset=sources),
                cash_resolution=forms.ChoiceField(label="Cash resolution (interest receipts only)", required=False,
                    choices=(("", "Exchange correction"), ("NOT_RECEIVED", "Cash was not received"), ("REFUNDED", "Full amount actually refunded"))),
                reason=text("Correction reason"), resolution_reference=text("Resolution / refund reference"))
        elif action == "cancel":
            self.fields["reason"] = text("Cancellation reason")
        elif action not in ("approve", "finalize"):
            raise ValueError("Unknown khata action.")
        self.style()

    def clean(self):
        data = super().clean()
        if set(data.get("outgoing", ())) & set(data.get("incoming", ())):
            self.add_error("incoming", "An item cannot be selected on both sides of an exchange.")
        return data
