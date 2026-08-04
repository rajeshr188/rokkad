from django import forms

from apps.tenant_apps.loans.domain import (
    STAFF_CREATABLE_PAWN_LOAN_NOTICE_KINDS,
    CollateralMetal,
    PawnLoanNoticeChannel,
    PawnLoanNoticeKind,
)
from apps.tenant_apps.loans.models import LoanLicense, LoanSeries, PawnCollateralItem
from apps.tenant_apps.party.models import Party


class LoanLicenseForm(forms.ModelForm):
    class Meta:
        model = LoanLicense
        fields = (
            "name",
            "license_number",
            "issuing_authority",
            "issued_on",
            "expires_on",
            "notes",
        )
        widgets = {
            "issued_on": forms.DateInput(attrs={"type": "date"}),
            "expires_on": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class LoanSeriesSetupForm(forms.ModelForm):
    pawn_loan_prefix = forms.CharField(max_length=24, initial="PL-")
    release_prefix = forms.CharField(max_length=24, initial="RL-")
    number_width = forms.IntegerField(min_value=1, max_value=12, initial=5)
    maximum_number = forms.IntegerField(min_value=1, initial=10000)

    class Meta:
        model = LoanSeries
        fields = ("name", "code", "is_active")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            css_class = "form-check-input" if name == "is_active" else "form-control"
            field.widget.attrs.setdefault("class", css_class)


class PawnDraftForm(forms.Form):
    borrower = forms.ModelChoiceField(queryset=Party.objects.none())
    license = forms.ModelChoiceField(queryset=LoanLicense.objects.none())
    series = forms.ModelChoiceField(queryset=LoanSeries.objects.none())
    principal_amount = forms.DecimalField(max_digits=18, decimal_places=2, min_value=0.01)
    monthly_interest_rate = forms.DecimalField(max_digits=9, decimal_places=6, min_value=0)
    loan_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    tenure_months = forms.IntegerField(min_value=1, initial=3)

    def __init__(self, *args, workspace, instance=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["borrower"].queryset = Party.objects.filter(
            status=Party.PartyStatus.ACTIVE
        ).order_by("display_name", "party_code")
        self.fields["license"].queryset = LoanLicense.objects.filter(
            workspace=workspace
        ).order_by("license_number")
        self.fields["series"].queryset = LoanSeries.objects.filter(
            license__workspace=workspace
        ).select_related("license").order_by("license__license_number", "code")
        if instance is not None and not self.is_bound:
            self.initial.update(
                {
                    "borrower": instance.borrower_id,
                    "license": instance.license_id,
                    "series": instance.series_id,
                    "principal_amount": instance.principal_amount,
                    "monthly_interest_rate": instance.monthly_interest_rate,
                    "loan_date": instance.loan_date,
                    "tenure_months": instance.tenure_months,
                }
            )
            self.fields["license"].disabled = True
            self.fields["series"].disabled = True
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-select" if isinstance(field, forms.ModelChoiceField) else "form-control")

    def clean(self):
        cleaned = super().clean()
        license = cleaned.get("license")
        series = cleaned.get("series")
        if license and series and series.license_id != license.pk:
            self.add_error("series", "Series must belong to the selected license.")
        return cleaned


class PawnCollateralDraftForm(forms.ModelForm):
    class Meta:
        model = PawnCollateralItem
        fields = (
            "description",
            "metal",
            "gross_weight",
            "net_weight",
            "purity_percentage",
            "latest_appraised_value",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["metal"].choices = [
            (item.value, item.name.title()) for item in CollateralMetal
        ]
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-select" if field is self.fields["metal"] else "form-control")


PawnCollateralDraftFormSet = forms.formset_factory(
    PawnCollateralDraftForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


class PawnTransitionReasonForm(forms.Form):
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}))


class LoanModuleFeatureGateForm(forms.Form):
    enabled = forms.BooleanField(
        required=False,
        label="Create new pawn loans in Loans",
        help_text=(
            "Existing Girvi loans remain in Girvi. Turning this off restores "
            "Girvi as the new-loan entrypoint without deleting Loans records."
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["enabled"].widget.attrs["class"] = "form-check-input"


class PawnSetupTransferForm(forms.Form):
    license = forms.ModelChoiceField(queryset=LoanLicense.objects.none())
    series = forms.ModelChoiceField(queryset=LoanSeries.objects.none())
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, workspace, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["license"].queryset = LoanLicense.objects.filter(workspace=workspace)
        self.fields["series"].queryset = LoanSeries.objects.filter(
            license__workspace=workspace
        ).select_related("license")
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-select" if isinstance(field, forms.ModelChoiceField) else "form-control")

    def clean(self):
        cleaned = super().clean()
        license = cleaned.get("license")
        series = cleaned.get("series")
        if license and series and series.license_id != license.pk:
            self.add_error("series", "Series must belong to the selected license.")
        return cleaned


class PawnDisbursalForm(forms.Form):
    effective_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["effective_date"].widget.attrs["class"] = "form-control"


class PawnRepaymentForm(forms.Form):
    amount = forms.DecimalField(max_digits=18, decimal_places=2, min_value=0.01)
    request_key = forms.CharField(max_length=120, widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["amount"].widget.attrs["class"] = "form-control"


class PawnAccrualForm(forms.Form):
    period_number = forms.IntegerField(min_value=1)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["period_number"].widget.attrs["class"] = "form-control"


class PawnCapitalizationForm(forms.Form):
    through_period_number = forms.IntegerField(min_value=1)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["through_period_number"].widget.attrs["class"] = "form-control"


class PawnFullReleaseForm(forms.Form):
    settlement_amount = forms.DecimalField(
        max_digits=18,
        decimal_places=2,
        min_value=0,
    )
    request_key = forms.CharField(max_length=120, widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["settlement_amount"].widget.attrs["class"] = "form-control"


class PawnPartialReleaseForm(PawnFullReleaseForm):
    selected_items = forms.ModelMultipleChoiceField(
        queryset=PawnCollateralItem.objects.none(),
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args, loan, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["settlement_amount"].required = False
        self.fields["settlement_amount"].help_text = (
            "Preview the selected collateral first, then enter the displayed minimum."
        )
        self.fields["selected_items"].queryset = loan.collateral_items.filter(
            custody_state="IN_VAULT"
        ).order_by("pk")


class PawnReversalForm(forms.Form):
    reason = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"})
    )


class PawnLoanNoticeForm(forms.Form):
    notice_kind = forms.ChoiceField(
        choices=[
            (kind.value, kind.name.replace("_", " ").title())
            for kind in PawnLoanNoticeKind
            if kind in STAFF_CREATABLE_PAWN_LOAN_NOTICE_KINDS
        ]
    )
    channel = forms.ChoiceField(
        choices=[
            (channel.value, channel.name.title())
            for channel in PawnLoanNoticeChannel
        ]
    )
    scheduled_for = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
        help_text="Leave blank to send immediately after saving.",
    )
    request_key = forms.CharField(max_length=120, widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["notice_kind"].widget.attrs["class"] = "form-select"
        self.fields["channel"].widget.attrs["class"] = "form-select"
        self.fields["scheduled_for"].widget.attrs["class"] = "form-control"


class PawnAuctionInitiateForm(forms.Form):
    scheduled_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    channel = forms.ChoiceField(
        choices=[
            (channel.value, channel.name.title())
            for channel in PawnLoanNoticeChannel
        ]
    )
    request_key = forms.CharField(max_length=120, widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["scheduled_date"].widget.attrs["class"] = "form-control"
        self.fields["channel"].widget.attrs["class"] = "form-select"


class PawnAuctionCompletionForm(forms.Form):
    recovery_amount = forms.DecimalField(max_digits=18, decimal_places=2, min_value=0.01)
    buyer_name = forms.CharField(max_length=255)
    buyer_reference = forms.CharField(max_length=120, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"
