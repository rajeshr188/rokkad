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
from apps.tenant_apps.loans.models import (
    FundingPledgeItem,
    LoanLicense,
    LoanSeries,
    PawnCollateralItem,
)
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


class LoanDocumentOverlaySettingsForm(forms.Form):
    page_size = forms.ChoiceField(choices=(("A4", "A4"), ("A5", "A5"), ("LETTER", "Letter")))
    copy_mode = forms.ChoiceField(label="Legacy copy mode", choices=(
        ("SINGLE", "Single"), ("ORIGINAL_DUPLICATE", "Original + duplicate"),
        ("ORIGINAL_DUPLICATE_DUPLEX", "Original + duplicate duplex"),
    ))
    background_asset_key = forms.ChoiceField(required=False, label="Legacy/shared background")
    sheet_composition = forms.ChoiceField(required=False, choices=(
        ("", "Legacy copy mode"),
        ("A5_ORIGINAL", "A5 original"),
        ("A5_ORIGINAL_TERMS_DUPLEX", "A5 original + terms duplex"),
        ("A5_DUPLICATE", "A5 duplicate"),
        ("A5_DUPLICATE_D3_DUPLEX", "A5 duplicate + D3 duplex"),
        ("A5_BOTH_SIMPLEX", "A5 original + duplicate simplex"),
        ("A5_BOTH_DUPLEX", "A5 original/terms + duplicate/D3 duplex"),
        ("A4_SIDE_BY_SIDE", "A4 landscape side-by-side"),
        ("A4_SIDE_BY_SIDE_DUPLEX", "A4 landscape side-by-side duplex"),
    ))
    original_front = forms.ChoiceField(required=False)
    duplicate_front = forms.ChoiceField(required=False)
    original_back = forms.ChoiceField(required=False, label="Original back / terms")
    duplicate_back = forms.ChoiceField(required=False, label="Duplicate back / D3")

    def __init__(self, *args, background_keys=(), sheet_composition_enabled=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["background_asset_key"].choices = [
            (key, key) for key in sorted(set(background_keys) | {"form.background"})
        ]
        surface_choices = [("", "Not used")] + [(key, key) for key in sorted(set(background_keys))]
        for name in ("original_front", "duplicate_front", "original_back", "duplicate_back"):
            self.fields[name].choices = surface_choices
        if not sheet_composition_enabled:
            for name in ("sheet_composition", "original_front", "duplicate_front", "original_back", "duplicate_back"):
                self.fields.pop(name)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-select"

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("sheet_composition"):
            # Every preset is built from A5 logical surfaces. A4 landscape is
            # an output imposition detail, not a page-size choice operators
            # should have to coordinate manually.
            cleaned["page_size"] = "A5"
        if not cleaned.get("sheet_composition") and not cleaned.get("background_asset_key"):
            self.add_error("background_asset_key", "Choose a shared background for legacy composition.")
        return cleaned


class LoanDocumentOverlayBlockForm(forms.Form):
    block_type = forms.ChoiceField(choices=(
        ("field", "Field"), ("title", "Title"), ("image", "Image"),
        ("qr", "QR code"), ("verification", "Verification"),
        ("signature", "Signature"), ("table", "Table"),
    ))
    binding = forms.ChoiceField(required=False)
    asset_key = forms.ChoiceField(required=False)
    text = forms.CharField(required=False, max_length=100)
    x_mm = forms.IntegerField(min_value=0, max_value=300)
    y_mm = forms.IntegerField(min_value=0, max_value=400)
    width_mm = forms.IntegerField(min_value=5, max_value=216)
    height_mm = forms.IntegerField(min_value=1, max_value=100)
    font_size_pt = forms.IntegerField(min_value=6, max_value=24, initial=10)
    align = forms.ChoiceField(choices=(("LEFT", "Left"), ("CENTER", "Centre"), ("RIGHT", "Right")))
    copy_scope = forms.ChoiceField(
        required=False, initial="BOTH",
        choices=(("BOTH", "Both copies"), ("ORIGINAL", "Original only"), ("DUPLICATE", "Duplicate only")),
    )

    def __init__(self, *args, asset_keys=(), **kwargs):
        super().__init__(*args, **kwargs)
        field_choices = sorted((value, label) for label, value in PawnLoanDocumentProjectionBuilder.FIELD_KEYS.items())
        section_choices = sorted((value, f"Table: {label}") for label, value in PawnLoanDocumentProjectionBuilder.SECTION_KEYS.items())
        self.fields["binding"].choices = [("", "Verification ID / none")] + field_choices + section_choices
        self.fields["asset_key"].choices = [("", "Select an image asset")] + [(key, key) for key in sorted(asset_keys)]
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-select" if isinstance(field, forms.ChoiceField) else "form-control"

    def clean(self):
        cleaned = super().clean()
        block_type, binding = cleaned.get("block_type"), cleaned.get("binding")
        field_keys = set(PawnLoanDocumentProjectionBuilder.FIELD_KEYS.values())
        section_keys = set(PawnLoanDocumentProjectionBuilder.SECTION_KEYS.values())
        if block_type == "field" and binding not in field_keys:
            self.add_error("binding", "Select a registered scalar field.")
        if block_type == "table" and binding not in section_keys:
            self.add_error("binding", "Select a registered table.")
        if block_type == "qr" and binding and binding not in field_keys:
            self.add_error("binding", "Select a registered scalar field or leave blank for verification ID.")
        if block_type == "image" and not cleaned.get("asset_key"):
            self.add_error("asset_key", "Select an uploaded image asset.")
        return cleaned

    def block_definition(self):
        value = self.cleaned_data
        block = {
            "type": value["block_type"], "x_mm": value["x_mm"], "y_mm": value["y_mm"],
            "width_mm": value["width_mm"], "height_mm": value["height_mm"],
            "font_size_pt": value["font_size_pt"], "align": value["align"],
            "copy_scope": value.get("copy_scope") or "BOTH",
        }
        if value.get("binding"):
            block["binding"] = value["binding"]
        if value.get("asset_key"):
            block["asset_key"] = value["asset_key"]
        if value.get("text"):
            block["text"] = value["text"]
        return block


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
