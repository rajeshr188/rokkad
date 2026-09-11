"""Document layout, overlay, asset and print-profile editing forms."""

from django import forms

from apps.tenant_apps.loans.documents.payloads import PawnLoanDocumentProjectionBuilder
from apps.tenant_apps.loans.documents.print_profiles import built_in_print_profile
from apps.tenant_apps.loans.models import LoanLicense, LoanSeries


class LoanDocumentLayoutCreateForm(forms.Form):
    name = forms.CharField(max_length=100)
    document_type = forms.ChoiceField(
        choices=(
            ("loan_ticket", "Loan ticket"),
            ("repayment_receipt", "Repayment receipt"),
            ("release_memo", "Release memo"),
            ("auction_notice", "Auction notice"),
            ("auction_recovery", "Auction recovery memo"),
            ("renewal", "Renewal agreement"),
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
    page_size = forms.ChoiceField(
        label="Logical page size",
        choices=(("A4", "A4"), ("A5", "A5"), ("LETTER", "Letter")),
        help_text="The print profile controls physical paper and imposition.",
    )
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


class LoanDocumentOverlayLogicalSettingsForm(forms.Form):
    page_size = forms.ChoiceField(
        label="Logical surface size",
        choices=(("A4", "A4"), ("A5", "A5"), ("LETTER", "Letter")),
        help_text="The print profile controls physical paper and imposition.",
    )
    background_asset_key = forms.ChoiceField(
        required=False,
        label="Shared logical background",
        help_text="Used when a surface-specific background is not selected.",
    )
    original_front = forms.ChoiceField(required=False, label="Original front background")
    duplicate_front = forms.ChoiceField(required=False, label="Duplicate front background")
    original_back = forms.ChoiceField(required=False, label="Original Terms background")
    duplicate_back = forms.ChoiceField(required=False, label="Duplicate D3 background")

    def __init__(self, *args, background_keys=(), loan_ticket=True, **kwargs):
        super().__init__(*args, **kwargs)
        choices = [("", "Not used")] + [
            (key, key) for key in sorted(set(background_keys) | {"form.background"})
        ]
        for name in (
            "background_asset_key", "original_front", "duplicate_front",
            "original_back", "duplicate_back",
        ):
            self.fields[name].choices = choices
        if not loan_ticket:
            for name in (
                "original_front", "duplicate_front", "original_back", "duplicate_back",
            ):
                self.fields.pop(name)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-select"

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("background_asset_key") and not cleaned.get("original_front"):
            self.add_error(
                "background_asset_key",
                "Choose a shared background or an Original front background.",
            )
        return cleaned

    def surface_backgrounds(self):
        return {
            name: self.cleaned_data.get(name, "")
            for name in (
                "original_front", "duplicate_front", "original_back", "duplicate_back",
            )
            if self.cleaned_data.get(name)
        }


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


class LoanDocumentPrintProfileDefinitionForm(forms.Form):
    composition = forms.ChoiceField(choices=(
        ("A5_BOTH_SIMPLEX", "A5 Original + Duplicate (simplex)"),
        ("A5_BOTH_DUPLEX", "A5 Original/Terms + Duplicate/D3 (duplex)"),
        ("A4_SIDE_BY_SIDE", "A4 landscape side-by-side (simplex)"),
        ("A4_SIDE_BY_SIDE_DUPLEX", "A4 landscape side-by-side (duplex)"),
    ))
    scaling_policy = forms.ChoiceField(choices=(
        ("FIT_PRINTABLE_AREA", "Fit proportionally to the profile slot"),
        ("ACTUAL_SIZE", "Actual size (layout page must match)"),
    ))
    flip_edge_guidance = forms.ChoiceField(choices=(
        ("NOT_APPLICABLE", "Not applicable"),
        ("LONG_EDGE", "Flip on long edge"),
        ("SHORT_EDGE", "Flip on short edge"),
        ("VERIFY_ON_PRINTER", "Verify on the physical printer"),
    ))
    printer_guidance = forms.CharField(
        required=False, max_length=500,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Operator guidance only; it does not control the printer driver.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault(
                "class",
                "form-select" if isinstance(field, forms.ChoiceField) else "form-control",
            )

    def clean(self):
        cleaned = super().clean()
        composition = cleaned.get("composition") or ""
        duplex = composition.endswith("DUPLEX")
        flip = cleaned.get("flip_edge_guidance")
        if duplex and flip == "NOT_APPLICABLE":
            self.add_error(
                "flip_edge_guidance",
                "Duplex profiles require explicit or verify-on-printer flip guidance.",
            )
        if not duplex:
            cleaned["flip_edge_guidance"] = "NOT_APPLICABLE"
        return cleaned

    def definition(self, *, name):
        composition = self.cleaned_data["composition"]
        definition = built_in_print_profile(composition).canonical_dict()
        definition.update({
            "name": name,
            "scaling_policy": self.cleaned_data["scaling_policy"],
            "flip_edge_guidance": self.cleaned_data["flip_edge_guidance"],
            "printer_guidance": self.cleaned_data["printer_guidance"],
        })
        return definition


class LoanDocumentPrintProfileCreateForm(LoanDocumentPrintProfileDefinitionForm):
    name = forms.CharField(max_length=100)


class LoanDocumentPrintProfileAssignmentForm(forms.Form):
    series = forms.ModelChoiceField(
        queryset=LoanSeries.objects.none(), required=False,
        help_text="Leave blank for the workspace default.",
    )

    def __init__(self, *args, workspace, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["series"].queryset = LoanSeries.objects.filter(
            license__workspace=workspace
        ).select_related("license").order_by("license__license_number", "code")
        self.fields["series"].widget.attrs["class"] = "form-select"
