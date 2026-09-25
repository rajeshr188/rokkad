"""Economic, fee and monitoring setup inputs; persistence stays in services."""

from decimal import Decimal

from django import forms
from django.utils.translation import gettext_lazy as _

from apps.tenant_apps.loans.domain import (
    FeeCalculationType,
    InterestMethod,
    PartialMonthMethod,
    RoundingMethod,
    ValuationMethod,
)
from apps.tenant_apps.loans.models import LoanLicense, LoanMonitoringPolicy, LoanSeries


class GroupedPolicyForm:
    """Presentation only; existing field validation and service inputs are unchanged."""
    groups = ()

    @property
    def sections(self):
        return [{"title": title, "fields": [self[name] for name in names]} for title, names in self.groups]

    def localize(self):
        for name, field in self.fields.items():
            field.label = ECONOMIC_LABELS.get(name, _(field.label or name.replace("_", " ").capitalize()))
            if field.help_text:
                field.help_text = _(field.help_text)
            if isinstance(field, forms.ModelChoiceField):
                field.empty_label = _("Business default (all licenses)")
            elif isinstance(field, forms.ChoiceField):
                field.choices = [(key, _(label)) for key, label in field.choices]


ECONOMIC_LABELS = {
    "license": _("Policy scope"), "effective_from": _("Applies from"),
    "valuation_method": _("How collateral value is chosen"), "maximum_ltv_ratio": _("Maximum loan-to-value ratio"),
    "advance_interest_periods": _("Months of interest collected upfront"), "interest_method": _("Interest calculation"),
    "gold_monthly_interest_rate": _("Gold: monthly interest (%)"), "silver_monthly_interest_rate": _("Silver: monthly interest (%)"),
    "partial_month_method": _("Charging for part of a month"), "partial_month_cutoff_days": _("Part-month cutoff (days)"),
    "partial_month_lower_fraction": _("Month fraction below the cutoff"),
    "capitalization_interval_periods": _("Compound interest interval (months)"),
    "rounding_method": _("Rounding rule"), "currency_quantum": _("Smallest currency rounding unit"),
    "code": _("Fee code"), "name": _("Fee name"), "calculation_type": _("How the fee is calculated"),
    "value": _("Fee amount or percentage"), "deducted_at_disbursal": _("Deduct this fee when paying out the loan"),
    "compliance_profile": _("Monitoring profile name"), "amendment_reason": _("Reason for the new version"),
    "maturity_warning_days": _("Warn before maturity (days)"), "operational_grace_days": _("Operational grace (days)"),
    "dpd_watch_threshold": _("Days past due: watch threshold"), "dpd_substandard_threshold": _("Days past due: substandard threshold"),
    "ltv_warning_ratio": _("Loan-to-value: warning ratio"), "ltv_breach_ratio": _("Loan-to-value: breach ratio"),
    "ltv_critical_ratio": _("Loan-to-value: critical ratio"), "rate_freshness_days": _("Maximum metal-price age (days)"),
    "appraisal_freshness_days": _("Maximum appraisal age (days)"),
}


class PawnEconomicConfigurationForm(GroupedPolicyForm, forms.Form):
    groups = (
        (_("1. Scope and dates"), ("license", "effective_from", "effective_until")),
        (_("2. Monthly interest"), ("gold_monthly_interest_rate", "silver_monthly_interest_rate", "interest_method", "advance_interest_periods")),
        (_("3. Part-month and compound rules"), ("partial_month_method", "partial_month_cutoff_days", "partial_month_lower_fraction", "capitalization_interval_periods")),
        (_("4. Collateral value and rounding"), ("valuation_method", "maximum_ltv_ratio", "rounding_method", "currency_quantum")),
    )
    license = forms.ModelChoiceField(
        queryset=LoanLicense.objects.none(),
        required=False,
        label="Policy scope",
        empty_label="Business default (all licenses)",
        help_text=_("Keep the business default unless this policy should apply only to a particular license."),
    )
    valuation_method = forms.ChoiceField(
        choices=[(ValuationMethod.CALCULATED_METAL_VALUE.value, _("Calculated Metal Value")),
                 (ValuationMethod.LATEST_APPRAISAL.value, _("Latest Appraisal")),
                 (ValuationMethod.LOWER_OF_CALCULATED_AND_APPRAISAL.value, _("Lower Of Calculated And Appraisal"))],
        initial=ValuationMethod.LOWER_OF_CALCULATED_AND_APPRAISAL.value,
    )
    maximum_ltv_ratio = forms.DecimalField(
        max_digits=7,
        decimal_places=6,
        min_value=0.000001,
        max_value=1,
        initial="0.80",
        help_text=_("Enter 0.80 for 80%, or 0.95 for 95%."),
    )
    advance_interest_periods = forms.IntegerField(min_value=0, max_value=12, initial=1)
    interest_method = forms.ChoiceField(
        choices=[(InterestMethod.SIMPLE.value, _("Simple")), (InterestMethod.COMPOUND.value, _("Compound"))],
        initial=InterestMethod.SIMPLE.value,
    )
    partial_month_method = forms.ChoiceField(
        choices=[
            (PartialMonthMethod.FULL_MONTH.value, _("Always charge a full month")),
            (PartialMonthMethod.SLAB.value, _("Use part-month slab")),
        ],
        initial=PartialMonthMethod.FULL_MONTH.value,
    )
    partial_month_cutoff_days = forms.IntegerField(
        min_value=1,
        max_value=30,
        initial=15,
        help_text=_("For slab mode, days up to this cutoff use the lower fraction."),
    )
    partial_month_lower_fraction = forms.DecimalField(
        max_digits=5,
        decimal_places=4,
        min_value=Decimal("0.0001"),
        max_value=Decimal("1"),
        initial=Decimal("0.5"),
        help_text=_("Enter 0.5 for half a month."),
    )
    capitalization_interval_periods = forms.IntegerField(
        min_value=1,
        max_value=120,
        initial=12,
        help_text=_("Compound loans may capitalize after this many monthly periods."),
    )
    rounding_method = forms.ChoiceField(
        choices=[
            (RoundingMethod.PER_ACCRUAL_PERIOD.value, _("Round each monthly accrual row"))
        ],
        initial=RoundingMethod.PER_ACCRUAL_PERIOD.value,
    )
    currency_quantum = forms.DecimalField(
        max_digits=8,
        decimal_places=4,
        min_value=Decimal("0.0001"),
        initial=Decimal("0.01"),
        help_text=_("Use 0.01 for paise-level currency rounding."),
    )
    gold_monthly_interest_rate = forms.DecimalField(
        max_digits=9, decimal_places=6, min_value=0, max_value=100,
        initial=Decimal("2"), help_text=_("Monthly percentage. Starts at 2%; change before saving if needed."),
    )
    silver_monthly_interest_rate = forms.DecimalField(
        max_digits=9, decimal_places=6, min_value=0, max_value=100,
        initial=Decimal("4"), help_text=_("Monthly percentage. Starts at 4%; change before saving if needed."),
    )
    effective_from = forms.DateField(widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}))
    effective_until = forms.DateField(required=False, label=_("Applies through (optional)"),
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}))

    def __init__(self, *args, workspace, **kwargs):
        super().__init__(*args, **kwargs)
        self.localize()
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


class PawnSeriesInterestForm(GroupedPolicyForm, forms.Form):
    groups = ((_("Series and monthly interest"), ("series", "effective_from", "gold_monthly_interest_rate", "silver_monthly_interest_rate")),)
    series = forms.ModelChoiceField(queryset=LoanSeries.objects.none(), label=_("Series"))
    effective_from = forms.DateField(label=_("Applies from"), widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}))
    gold_monthly_interest_rate = forms.DecimalField(label=_("Gold: monthly interest (%)"), max_digits=9, decimal_places=6, min_value=0, max_value=100)
    silver_monthly_interest_rate = forms.DecimalField(label=_("Silver: monthly interest (%)"), max_digits=9, decimal_places=6, min_value=0, max_value=100)

    def __init__(self, *args, workspace, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["series"].queryset = LoanSeries.objects.filter(workspace=workspace).select_related("license").prefetch_related("number_sequences")
        self.fields["series"].label_from_instance = lambda row: f"{row.license.license_number} / {row.pawn_display_name}"
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-select" if isinstance(field, forms.ModelChoiceField) else "form-control"


class LoanMonitoringPolicyForm(GroupedPolicyForm, forms.ModelForm):
    groups = (
        (_("1. Scope and version"), ("license", "effective_from", "compliance_profile", "amendment_reason")),
        (_("2. Maturity and overdue warnings"), ("maturity_warning_days", "operational_grace_days", "dpd_watch_threshold", "dpd_substandard_threshold")),
        (_("3. Collateral risk and evidence age"), ("ltv_warning_ratio", "ltv_breach_ratio", "ltv_critical_ratio", "rate_freshness_days", "appraisal_freshness_days")),
    )
    class Meta:
        model = LoanMonitoringPolicy
        fields = (
            "license", "effective_from", "compliance_profile", "supersedes", "amendment_reason",
            "maturity_warning_days", "operational_grace_days",
            "dpd_watch_threshold", "dpd_substandard_threshold",
            "ltv_warning_ratio", "ltv_breach_ratio", "ltv_critical_ratio",
            "rate_freshness_days", "appraisal_freshness_days",
        )
        widgets = {"effective_from": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
                   "supersedes": forms.HiddenInput(), "amendment_reason": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, workspace, actor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.workspace = workspace
        self.instance.created_by = actor
        self.fields["supersedes"].queryset = LoanMonitoringPolicy.objects.filter(workspace=workspace)
        self.fields["amendment_reason"].help_text = _("Required when amending an existing policy. Previous versions remain in history.")
        self.instance.eligible_custody_states = ["IN_VAULT", "WITH_FUNDING_LENDER"]
        self.instance.severity_mapping = {"strategy": "derived-v1"}
        self.fields["rate_freshness_days"].help_text = _("Maximum quote age for current collateral monitoring, inclusive in calendar days. Zero requires same-day prices.")
        self.fields["appraisal_freshness_days"].help_text = _("Maximum approved appraisal age for current collateral monitoring. Zero requires same-day appraisal evidence.")
        self.fields["license"].required = False
        self.fields["license"].queryset = LoanLicense.objects.filter(
            workspace=workspace
        ).order_by("license_number")
        self.fields["license"].help_text = _("Leave blank for the workspace default.")
        self.localize()
        for field in self.fields.values():
            field.widget.attrs.setdefault(
                "class",
                "form-select"
                if isinstance(field, (forms.ModelChoiceField, forms.ChoiceField))
                else "form-control",
            )


class PawnFeePolicyForm(GroupedPolicyForm, forms.Form):
    groups = (
        (_("1. Scope and start date"), ("license", "effective_from")),
        (_("2. Fee details"), ("name", "code", "calculation_type", "value", "deducted_at_disbursal")),
    )
    license = forms.ModelChoiceField(
        queryset=LoanLicense.objects.none(),
        required=False,
        label="Policy scope",
        empty_label="Business default (all licenses)",
        help_text=_("Keep the business default unless this policy should apply only to a particular license."),
    )
    code = forms.CharField(max_length=32, initial="DOCUMENT_CHARGE")
    name = forms.CharField(max_length=100, initial="Document charge")
    calculation_type = forms.ChoiceField(
        initial=FeeCalculationType.FIXED.value,
        choices=[(FeeCalculationType.FIXED.value, _("Fixed")), (FeeCalculationType.PERCENTAGE.value, _("Percentage"))],
    )
    value = forms.DecimalField(
        max_digits=18, decimal_places=6, min_value=0, initial=Decimal("10"),
        help_text=_("The starter document charge is a fixed INR 10 per loan. Change it before saving if needed."),
    )
    deducted_at_disbursal = forms.BooleanField(required=False, initial=True)
    effective_from = forms.DateField(widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}))

    def __init__(self, *args, workspace, **kwargs):
        super().__init__(*args, **kwargs)
        self.localize()
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
