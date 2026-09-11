"""Economic, fee and monitoring setup inputs; persistence stays in services."""

from decimal import Decimal

from django import forms

from apps.tenant_apps.loans.domain import (
    FeeCalculationType,
    InterestMethod,
    PartialMonthMethod,
    RoundingMethod,
    ValuationMethod,
)
from apps.tenant_apps.loans.models import LoanLicense, LoanMonitoringPolicy


class PawnEconomicConfigurationForm(forms.Form):
    license = forms.ModelChoiceField(
        queryset=LoanLicense.objects.none(),
        required=False,
        label="Policy scope",
        empty_label="Business default (all licenses)",
        help_text="Keep the business default unless this policy should apply only to a particular license.",
    )
    valuation_method = forms.ChoiceField(
        choices=[(item.value, item.name.replace("_", " ").title()) for item in ValuationMethod],
        initial=ValuationMethod.LOWER_OF_CALCULATED_AND_APPRAISAL.value,
    )
    maximum_ltv_ratio = forms.DecimalField(
        max_digits=7,
        decimal_places=6,
        min_value=0.000001,
        max_value=1,
        initial="0.80",
        help_text="Enter 0.80 for 80%.",
    )
    advance_interest_periods = forms.IntegerField(min_value=0, max_value=12, initial=1)
    interest_method = forms.ChoiceField(
        choices=[(item.value, item.name.title()) for item in InterestMethod],
        initial=InterestMethod.SIMPLE.value,
    )
    partial_month_method = forms.ChoiceField(
        choices=[
            (PartialMonthMethod.FULL_MONTH.value, "Always charge a full month"),
            (PartialMonthMethod.SLAB.value, "Use part-month slab"),
        ],
        initial=PartialMonthMethod.FULL_MONTH.value,
    )
    partial_month_cutoff_days = forms.IntegerField(
        min_value=1,
        max_value=30,
        initial=15,
        help_text="For slab mode, days up to this cutoff use the lower fraction.",
    )
    partial_month_lower_fraction = forms.DecimalField(
        max_digits=5,
        decimal_places=4,
        min_value=Decimal("0.0001"),
        max_value=Decimal("1"),
        initial=Decimal("0.5"),
        help_text="Enter 0.5 for half a month.",
    )
    capitalization_interval_periods = forms.IntegerField(
        min_value=1,
        max_value=120,
        initial=12,
        help_text="Compound loans may capitalize after this many monthly periods.",
    )
    rounding_method = forms.ChoiceField(
        choices=[
            (RoundingMethod.PER_ACCRUAL_PERIOD.value, "Round each monthly accrual row")
        ],
        initial=RoundingMethod.PER_ACCRUAL_PERIOD.value,
    )
    currency_quantum = forms.DecimalField(
        max_digits=8,
        decimal_places=4,
        min_value=Decimal("0.0001"),
        initial=Decimal("0.01"),
        help_text="Use 0.01 for paise-level currency rounding.",
    )
    gold_monthly_interest_rate = forms.DecimalField(
        max_digits=9, decimal_places=6, min_value=0, max_value=100,
        initial=Decimal("2"), help_text="Monthly percentage. Starts at 2%; change before saving if needed.",
    )
    silver_monthly_interest_rate = forms.DecimalField(
        max_digits=9, decimal_places=6, min_value=0, max_value=100,
        initial=Decimal("4"), help_text="Monthly percentage. Starts at 4%; change before saving if needed.",
    )
    effective_from = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, workspace, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["license"].queryset = LoanLicense.objects.filter(
            workspace=workspace
        ).order_by("license_number")
        for field in self.fields.values():
            field.widget.attrs.setdefault(
                "class",
                "form-select"
                if isinstance(field, (forms.ModelChoiceField, forms.ChoiceField))
                else "form-control",
            )


class LoanMonitoringPolicyForm(forms.ModelForm):
    class Meta:
        model = LoanMonitoringPolicy
        fields = (
            "license", "effective_from", "compliance_profile",
            "maturity_warning_days", "operational_grace_days",
            "dpd_watch_threshold", "dpd_substandard_threshold",
            "ltv_warning_ratio", "ltv_breach_ratio", "ltv_critical_ratio",
            "rate_freshness_days", "appraisal_freshness_days",
        )
        widgets = {"effective_from": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, workspace, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.workspace = workspace
        self.instance.eligible_custody_states = ["IN_VAULT", "WITH_FUNDING_LENDER"]
        self.instance.severity_mapping = {"strategy": "derived-v1"}
        self.fields["license"].required = False
        self.fields["license"].queryset = LoanLicense.objects.filter(
            workspace=workspace
        ).order_by("license_number")
        self.fields["license"].help_text = "Leave blank for the workspace default."
        for field in self.fields.values():
            field.widget.attrs.setdefault(
                "class",
                "form-select"
                if isinstance(field, (forms.ModelChoiceField, forms.ChoiceField))
                else "form-control",
            )


class PawnFeePolicyForm(forms.Form):
    license = forms.ModelChoiceField(
        queryset=LoanLicense.objects.none(),
        required=False,
        label="Policy scope",
        empty_label="Business default (all licenses)",
        help_text="Keep the business default unless this policy should apply only to a particular license.",
    )
    code = forms.CharField(max_length=32, initial="DOCUMENT_CHARGE")
    name = forms.CharField(max_length=100, initial="Document charge")
    calculation_type = forms.ChoiceField(
        initial=FeeCalculationType.FIXED.value,
        choices=[
            (item.value, item.name.replace("_", " ").title())
            for item in FeeCalculationType
        ]
    )
    value = forms.DecimalField(
        max_digits=18, decimal_places=6, min_value=0, initial=Decimal("10"),
        help_text="The starter document charge is a fixed INR 10 per loan. Change it before saving if needed.",
    )
    deducted_at_disbursal = forms.BooleanField(required=False, initial=True)
    effective_from = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, workspace, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["license"].queryset = LoanLicense.objects.filter(
            workspace=workspace
        ).order_by("license_number")
        for name, field in self.fields.items():
            field.widget.attrs.setdefault(
                "class",
                "form-check-input"
                if name == "deducted_at_disbursal"
                else (
                    "form-select"
                    if isinstance(field, (forms.ModelChoiceField, forms.ChoiceField))
                    else "form-control"
                ),
            )
