"""Funding draft, settlement and correction inputs; workflows stay in services."""

from decimal import Decimal

from django import forms

from apps.tenant_apps.loans.models import FundingPledgeItem, PawnCollateralItem
from apps.tenant_apps.party.models import Party


class FundingLoanDraftForm(forms.Form):
    lender = forms.ModelChoiceField(queryset=Party.objects.none())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["lender"].queryset = Party.objects.filter(
            status=Party.PartyStatus.ACTIVE
        ).order_by("display_name", "party_code")
        self.fields["lender"].widget.attrs["class"] = "form-select"


class FundingLoanDraftInputsForm(forms.Form):
    principal_amount = forms.DecimalField(max_digits=18, decimal_places=4, min_value=Decimal("0.0001"))
    monthly_interest_rate = forms.DecimalField(max_digits=9, decimal_places=6, min_value=Decimal(0))
    activated_on = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    maturity_on = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    maximum_funding_ltv_ratio = forms.DecimalField(
        max_digits=7,
        decimal_places=6,
        min_value=Decimal("0.000001"),
        max_value=Decimal(1),
        initial=Decimal("0.800000"),
        label="Maximum funding LTV ratio",
    )
    currency_quantum = forms.DecimalField(
        max_digits=8,
        decimal_places=4,
        min_value=Decimal("0.0001"),
        initial=Decimal("0.0100"),
    )
    collateral = forms.ModelMultipleChoiceField(
        queryset=PawnCollateralItem.objects.none(),
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args, workspace, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["collateral"].queryset = (
            PawnCollateralItem.objects.filter(
                loan__workspace=workspace,
                loan__state="ACTIVE",
                custody_state="IN_VAULT",
                latest_appraised_value__isnull=False,
            )
            .exclude(
                pk__in=FundingPledgeItem.objects.filter(
                    released_at__isnull=True
                ).values("collateral_item_id")
            )
            .select_related("loan")
            .order_by("loan__loan_number", "pk")
        )
        self.fields["collateral"].label_from_instance = lambda item: (
            f"{item.loan.loan_number} - {item.description} "
            f"(appraised {item.latest_appraised_value})"
        )
        for name, field in self.fields.items():
            if name != "collateral":
                field.widget.attrs.setdefault("class", "form-control")

    def clean(self):
        cleaned = super().clean()
        activated_on = cleaned.get("activated_on")
        maturity_on = cleaned.get("maturity_on")
        if activated_on and maturity_on and maturity_on < activated_on:
            self.add_error("maturity_on", "Maturity cannot precede activation.")
        return cleaned


class FundingLoanCancellationForm(forms.Form):
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}))


class FundingLoanActivationForm(forms.Form):
    confirmation = forms.CharField(
        max_length=16,
        help_text="Enter ACTIVATE to confirm lender handoff.",
        widget=forms.TextInput(attrs={"class": "form-control", "autocomplete": "off"}),
    )

    def clean_confirmation(self):
        confirmation = self.cleaned_data["confirmation"].strip()
        if confirmation != "ACTIVATE":
            raise forms.ValidationError("Enter ACTIVATE exactly to confirm activation.")
        return confirmation


class FundingLoanClosureForm(forms.Form):
    confirmation = forms.CharField(
        max_length=16,
        help_text="Enter CLOSE to confirm permanent closure.",
        widget=forms.TextInput(attrs={"class": "form-control", "autocomplete": "off"}),
    )

    def clean_confirmation(self):
        confirmation = self.cleaned_data["confirmation"].strip()
        if confirmation != "CLOSE":
            raise forms.ValidationError("Enter CLOSE exactly to confirm closure.")
        return confirmation


class FundingCorrectionForm(forms.Form):
    effective_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"})
    )
    reason = forms.CharField(
        max_length=500,
        widget=forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
    )
    request_key = forms.UUIDField(widget=forms.HiddenInput())


class FundingLoanRepaymentForm(forms.Form):
    amount = forms.DecimalField(
        max_digits=18,
        decimal_places=4,
        min_value=Decimal("0.0001"),
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
    )
    effective_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"})
    )
    request_key = forms.UUIDField(widget=forms.HiddenInput())


class FundingCollateralReturnForm(forms.Form):
    collateral = forms.MultipleChoiceField(
        choices=(),
        widget=forms.CheckboxSelectMultiple(),
    )
    effective_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"})
    )
    request_key = forms.UUIDField(widget=forms.HiddenInput())

    def __init__(self, *args, collateral_rows=(), include_inactive=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["collateral"].choices = tuple(
            (
                str(row.collateral_item_id),
                f"{row.source_loan_number} - {row.description}",
            )
            for row in collateral_rows
            if row.active or include_inactive
        )
