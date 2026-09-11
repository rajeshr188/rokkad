"""Storage and physical-verification inputs; custody rules stay in services."""

from decimal import Decimal

from django import forms

from apps.tenant_apps.loans.models import (
    PawnCollateralItem,
    PawnPhysicalVerificationObservation,
    PawnPhysicalVerificationResolution,
    PawnStorageLocation,
)


class PawnStorageLocationForm(forms.Form):
    parent = forms.ModelChoiceField(
        queryset=PawnStorageLocation.objects.none(), required=False
    )
    level = forms.ChoiceField(choices=PawnStorageLocation.Level.choices)
    code = forms.CharField(max_length=32)
    name = forms.CharField(max_length=100)
    capacity = forms.IntegerField(required=False, min_value=1)

    def __init__(self, *args, workspace, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["parent"].queryset = PawnStorageLocation.objects.filter(
            workspace=workspace, is_active=True
        ).select_related("parent").order_by("level", "code")
        for field in self.fields.values():
            field.widget.attrs["class"] = (
                "form-select"
                if isinstance(field, (forms.ModelChoiceField, forms.ChoiceField))
                else "form-control"
            )


class PawnStorageTransferForm(forms.Form):
    destination = forms.ModelChoiceField(
        queryset=PawnStorageLocation.objects.none(),
        help_text="Scan the destination QR or select its Box/Slot code.",
    )
    reason = forms.CharField(
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Required when moving an already placed item.",
    )

    def __init__(self, *args, workspace, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["destination"].queryset = PawnStorageLocation.objects.filter(
            workspace=workspace,
            is_active=True,
            level__in=(PawnStorageLocation.Level.BOX, PawnStorageLocation.Level.SLOT),
        ).select_related("parent").order_by("code")
        self.fields["destination"].widget.attrs["class"] = "form-select"
        self.fields["reason"].widget.attrs["class"] = "form-control"


class PawnPhysicalVerificationStartForm(forms.Form):
    scope_location = forms.ModelChoiceField(
        queryset=PawnStorageLocation.objects.none(),
        help_text="The expected item list and locations are frozen when the session starts.",
    )

    def __init__(self, *args, workspace, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["scope_location"].queryset = PawnStorageLocation.objects.filter(
            workspace=workspace,
            is_active=True,
            level__in=(PawnStorageLocation.Level.VAULT, PawnStorageLocation.Level.CABINET,
                       PawnStorageLocation.Level.BOX, PawnStorageLocation.Level.SLOT),
        ).order_by("level", "code")
        self.fields["scope_location"].widget.attrs["class"] = "form-select"


class PawnPhysicalVerificationObservationForm(forms.Form):
    collateral_item = forms.ModelChoiceField(queryset=PawnCollateralItem.objects.none())
    classification = forms.ChoiceField(
        choices=PawnPhysicalVerificationObservation.Classification.choices
    )
    observed_location = forms.ModelChoiceField(
        queryset=PawnStorageLocation.objects.none(), required=False
    )
    notes = forms.CharField(
        required=False, max_length=500, widget=forms.Textarea(attrs={"rows": 2})
    )

    def __init__(self, *args, workspace, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["collateral_item"].queryset = PawnCollateralItem.objects.filter(
            loan__workspace=workspace
        ).select_related("loan").order_by("loan__loan_number", "pk")
        self.fields["observed_location"].queryset = PawnStorageLocation.objects.filter(
            workspace=workspace, is_active=True,
            level__in=(PawnStorageLocation.Level.BOX, PawnStorageLocation.Level.SLOT),
        ).order_by("code")
        for field in self.fields.values():
            field.widget.attrs["class"] = (
                "form-select" if isinstance(field, (forms.ModelChoiceField, forms.ChoiceField))
                else "form-control"
            )


class PawnPhysicalVerificationResolutionForm(forms.Form):
    outcome = forms.ChoiceField(choices=PawnPhysicalVerificationResolution.Outcome.choices)
    reason = forms.CharField(max_length=500, widget=forms.Textarea(attrs={"rows": 3}))
    current_market_value = forms.DecimalField(
        required=False, max_digits=18, decimal_places=2, min_value=Decimal("0.01")
    )
    agreed_compensation = forms.DecimalField(
        required=False, max_digits=18, decimal_places=2, min_value=Decimal("0.01")
    )
    compensation_reference = forms.CharField(required=False, max_length=120)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = (
                "form-select" if isinstance(field, forms.ChoiceField) else "form-control"
            )
