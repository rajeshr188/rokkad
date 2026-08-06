from decimal import Decimal

from django import forms

from apps.tenant_apps.loans.domain import (
    STAFF_CREATABLE_PAWN_LOAN_NOTICE_KINDS,
    CollateralMetal,
    FeeCalculationType,
    PawnLoanNoticeChannel,
    PawnLoanNoticeKind,
    PawnLoanRenewalMode,
    ValuationMethod,
)
from apps.tenant_apps.loans.models import LoanLicense, LoanSeries, PawnCollateralItem
from apps.tenant_apps.loans.documents.payloads import PawnLoanDocumentProjectionBuilder


class LoanDocumentLayoutCreateForm(forms.Form):
    name = forms.CharField(max_length=100)
    document_type = forms.ChoiceField(
        choices=(
            ("loan_ticket", "Loan ticket"),
            ("repayment_receipt", "Repayment receipt"),
            ("release_memo", "Release memo"),
            ("auction_notice", "Auction notice"),
            ("auction_recovery", "Auction recovery memo"),
            ("renewal", "Renewal memo"),
        )
    )
    layout_mode = forms.ChoiceField(
        choices=(("FLOW", "Flow document"), ("ABSOLUTE_OVERLAY", "Exact PDF overlay")),
        initial="FLOW",
        required=False,
        help_text="Flow paginates automatically; overlay places data at exact millimetre coordinates over a PDF background.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].widget.attrs["class"] = "form-control"
        self.fields["document_type"].widget.attrs["class"] = "form-select"
        self.fields["layout_mode"].widget.attrs["class"] = "form-select"


class LoanDocumentLayoutDefinitionForm(forms.Form):
    definition = forms.JSONField(
        widget=forms.Textarea(attrs={"rows": 24, "class": "form-control font-monospace"}),
        help_text="Versioned structured layout JSON. Unknown or executable bindings are rejected.",
    )


class LoanDocumentFlowSettingsForm(forms.Form):
    page_size = forms.ChoiceField(choices=(("A4", "A4"), ("A5", "A5"), ("LETTER", "Letter")))
    margin_mm = forms.IntegerField(min_value=5, max_value=30)
    primary_color = forms.RegexField(regex=r"^#[0-9a-fA-F]{6}$", max_length=7)
    border_color = forms.RegexField(regex=r"^#[0-9a-fA-F]{6}$", max_length=7)
    font_family = forms.ChoiceField(choices=(("NOTO_SANS_TAMIL", "Noto Sans Tamil"), ("HELVETICA", "Helvetica")))
    body_font_size_pt = forms.IntegerField(min_value=7, max_value=14)
    heading_font_size_pt = forms.IntegerField(min_value=10, max_value=24)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-select" if isinstance(field, forms.ChoiceField) else "form-control"


class LoanDocumentFlowBlockForm(forms.Form):
    block_type = forms.ChoiceField(choices=(
        ("FIELD", "Single field"), ("FIELD_GRID", "Field grid"),
        ("SECTION", "Outlined field section"), ("FIELD_QR_COLUMNS", "Field + QR columns"),
        ("SPACER", "Spacer"), ("PAGE_BREAK", "Page break"),
        ("SIGNATURE", "Signature row"),
    ))
    binding = forms.ChoiceField(required=False)
    bindings = forms.MultipleChoiceField(required=False, widget=forms.SelectMultiple(attrs={"size": 8}))
    text = forms.CharField(required=False, max_length=100, help_text="Section title or signature labels separated by |.")
    height_mm = forms.IntegerField(required=False, min_value=1, max_value=100, initial=8)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choices = sorted((value, label) for label, value in PawnLoanDocumentProjectionBuilder.FIELD_KEYS.items())
        self.fields["binding"].choices = [("", "Select a field")] + choices
        self.fields["bindings"].choices = choices
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-select" if isinstance(field, (forms.ChoiceField, forms.MultipleChoiceField)) else "form-control")

    def clean(self):
        cleaned = super().clean()
        block_type = cleaned.get("block_type")
        if block_type in {"FIELD", "FIELD_QR_COLUMNS"} and not cleaned.get("binding"):
            self.add_error("binding", "Select a registered field.")
        if block_type in {"FIELD_GRID", "SECTION"} and not cleaned.get("bindings"):
            self.add_error("bindings", "Select at least one registered field.")
        return cleaned

    def block_definition(self):
        value = self.cleaned_data
        block_type = value["block_type"]
        if block_type == "FIELD":
            return {"type": "field", "binding": value["binding"]}
        if block_type == "FIELD_GRID":
            return {"type": "field_grid", "bindings": value["bindings"], "grid_columns": min(2, len(value["bindings"]))}
        if block_type == "SECTION":
            return {"type": "section", "text": value.get("text") or "Details", "style_variant": "OUTLINED", "blocks": [{"type": "field_grid", "bindings": value["bindings"], "grid_columns": min(2, len(value["bindings"]))}]}
        if block_type == "FIELD_QR_COLUMNS":
            return {"type": "columns", "columns": [
                {"width_percent": 70, "blocks": [{"type": "field", "binding": value["binding"]}]},
                {"width_percent": 30, "blocks": [{"type": "qr", "binding": "document.verification_id", "width_mm": 20}]},
            ]}
        if block_type == "SPACER":
            return {"type": "spacer", "height_mm": value.get("height_mm") or 8}
        if block_type == "PAGE_BREAK":
            return {"type": "page_break"}
        return {"type": "signature", "text": value.get("text") or "Borrower | Authorized pawnbroker", "height_mm": value.get("height_mm") or 18}


class LoanDocumentAssetUploadForm(forms.Form):
    key = forms.RegexField(regex=r"^[a-z][a-z0-9_.-]{0,63}$", max_length=64)
    kind = forms.ChoiceField(choices=(("IMAGE", "Image / logo"), ("BACKGROUND", "Page background")))
    file = forms.FileField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-select" if isinstance(field, forms.ChoiceField) else "form-control")


class LoanDocumentAssignmentForm(forms.Form):
    license = forms.ModelChoiceField(queryset=LoanLicense.objects.none(), required=False)
    series = forms.ModelChoiceField(queryset=LoanSeries.objects.none(), required=False)

    def __init__(self, *args, workspace, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["license"].queryset = LoanLicense.objects.filter(workspace=workspace).order_by("license_number")
        self.fields["series"].queryset = LoanSeries.objects.filter(license__workspace=workspace).select_related("license").order_by("license__license_number", "code")
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-select"

    def clean(self):
        cleaned = super().clean()
        license = cleaned.get("license")
        series = cleaned.get("series")
        if license and series and series.license_id != license.pk:
            self.add_error("series", "Series must belong to the selected license.")
        return cleaned


class LoanDocumentLayoutPackImportForm(forms.Form):
    name = forms.CharField(max_length=100, required=False, help_text="Optional local name override.")
    pack = forms.FileField(help_text="Sanitized ZIP exported by Rokkad; imports always remain draft.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"
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
            "allocated_principal",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["allocated_principal"].required = True
        self.fields["metal"].choices = [
            (item.value, item.name.title())
            for item in CollateralMetal
            if item in {CollateralMetal.GOLD, CollateralMetal.SILVER}
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

PawnAdditionalCollateralFormSet = forms.formset_factory(
    PawnCollateralDraftForm,
    extra=1,
    can_delete=True,
    min_num=0,
    validate_min=False,
)


class PawnEconomicConfigurationForm(forms.Form):
    license = forms.ModelChoiceField(
        queryset=LoanLicense.objects.none(),
        required=False,
        help_text="Leave blank to create the workspace default.",
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
    gold_monthly_interest_rate = forms.DecimalField(
        max_digits=9, decimal_places=6, min_value=0, max_value=100
    )
    silver_monthly_interest_rate = forms.DecimalField(
        max_digits=9, decimal_places=6, min_value=0, max_value=100
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


class PawnFeePolicyForm(forms.Form):
    license = forms.ModelChoiceField(
        queryset=LoanLicense.objects.none(),
        required=False,
        help_text="Leave blank to create the workspace default.",
    )
    code = forms.CharField(max_length=32)
    name = forms.CharField(max_length=100)
    calculation_type = forms.ChoiceField(
        choices=[
            (item.value, item.name.replace("_", " ").title())
            for item in FeeCalculationType
        ]
    )
    value = forms.DecimalField(max_digits=18, decimal_places=6, min_value=0)
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


class PawnRenewalForm(forms.Form):
    mode = forms.ChoiceField(
        choices=[
            (PawnLoanRenewalMode.PAY_AND_RENEW.value, "Pay and renew"),
            (PawnLoanRenewalMode.TOP_UP_RENEW.value, "Top-up renewal"),
        ],
        widget=forms.RadioSelect,
        initial=PawnLoanRenewalMode.PAY_AND_RENEW.value,
    )
    principal_paid = forms.DecimalField(
        max_digits=18, decimal_places=2, min_value=0, initial=0
    )
    top_up_amount = forms.DecimalField(
        max_digits=18, decimal_places=2, min_value=0, initial=0
    )
    successor_license = forms.ModelChoiceField(queryset=LoanLicense.objects.none())
    successor_series = forms.ModelChoiceField(queryset=LoanSeries.objects.none())
    tenure_months = forms.IntegerField(min_value=1, max_value=600)
    request_key = forms.CharField(max_length=120, widget=forms.HiddenInput())

    def __init__(self, *args, workspace, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["successor_license"].queryset = LoanLicense.objects.filter(
            workspace=workspace,
            is_active=True,
        ).order_by("name")
        self.fields["successor_series"].queryset = LoanSeries.objects.filter(
            license__workspace=workspace,
            license__is_active=True,
            is_active=True,
        ).select_related("license").order_by("license__name", "name")
        for name, field in self.fields.items():
            if name != "mode":
                field.widget.attrs.setdefault(
                    "class",
                    "form-select" if name in {"successor_license", "successor_series"} else "form-control",
                )

    def clean(self):
        cleaned = super().clean()
        license = cleaned.get("successor_license")
        series = cleaned.get("successor_series")
        if license and series and series.license_id != license.pk:
            self.add_error(
                "successor_series",
                "Successor series must belong to the selected license.",
            )
        return cleaned


class PawnRenewalRetainedItemForm(forms.Form):
    collateral_item_id = forms.IntegerField(widget=forms.HiddenInput())
    retain = forms.BooleanField(required=False, initial=True)
    allocated_principal = forms.DecimalField(
        max_digits=18,
        decimal_places=2,
        min_value=Decimal("0.01"),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["retain"].widget.attrs["class"] = "form-check-input"
        self.fields["allocated_principal"].widget.attrs["class"] = "form-control"

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("retain") and cleaned.get("allocated_principal") is None:
            self.add_error(
                "allocated_principal",
                "Retained collateral requires a successor principal allocation.",
            )
        return cleaned


PawnRenewalRetainedItemFormSet = forms.formset_factory(
    PawnRenewalRetainedItemForm,
    extra=0,
)
