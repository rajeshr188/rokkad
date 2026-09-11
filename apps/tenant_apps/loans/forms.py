from decimal import Decimal

from django import forms
from django.urls import reverse
from django_select2 import forms as s2forms

from apps.tenant_apps.loans.domain import (
    STAFF_CREATABLE_PAWN_LOAN_NOTICE_KINDS,
    CollateralMetal,
    LoanProductVersionStatus,
    PawnLoanNoticeChannel,
    PawnLoanNoticeKind,
    PawnLoanRenewalMode,
)
from apps.tenant_apps.loans.models import (
    FundingPledgeItem,
    LoanLicense,
    LoanSeries,
    LoanProductVersion,
    PawnCollateralItem,
    PawnPhysicalVerificationObservation,
    PawnPhysicalVerificationResolution,
    PawnStorageLocation,
)
from apps.tenant_apps.loans.web.document_forms import (
    LoanDocumentLayoutCreateForm,
    LoanDocumentLayoutDefinitionForm,
    LoanDocumentFlowSettingsForm,
    LoanDocumentFlowBlockForm,
    LoanDocumentOverlaySettingsForm,
    LoanDocumentOverlayLogicalSettingsForm,
    LoanDocumentOverlayBlockForm,
    LoanDocumentAssetUploadForm,
    LoanDocumentAssignmentForm,
    LoanDocumentLayoutPackImportForm,
    LoanDocumentPrintProfileDefinitionForm,
    LoanDocumentPrintProfileCreateForm,
    LoanDocumentPrintProfileAssignmentForm,
)
from apps.tenant_apps.loans.web.economic_forms import (
    PawnEconomicConfigurationForm,
    LoanMonitoringPolicyForm,
    PawnFeePolicyForm,
)
from apps.tenant_apps.loans.web.license_forms import (
    LoanLicenseForm,
    LoanLicenseRenewalForm,
    LoanSeriesSetupForm,
)
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.party.widgets import PartyAutocompleteWidget


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


class LoanProductVersionDraftForm(forms.ModelForm):
    class Meta:
        model = LoanProductVersion
        fields = (
            "available_from", "available_until", "repayment_structure",
            "amortisation_method", "payment_frequency", "minimum_tenor_months",
            "maximum_tenor_months", "operational_grace_days",
            "extra_payment_rule", "calculation_contract_version",
        )
        widgets = {
            "available_from": forms.DateInput(attrs={"type": "date"}),
            "available_until": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-select" if isinstance(field.widget, forms.Select) else "form-control")


class PawnDraftForm(forms.Form):
    borrower = forms.ModelChoiceField(
        queryset=Party.objects.none(),
        widget=PartyAutocompleteWidget(
            attrs={
                "autofocus": True,
                "data-placeholder": "Search by name, party code, phone, relation, or email",
            },
            select2_options={"width": "100%"},
        ),
    )
    series = forms.ModelChoiceField(
        label="Series (license / register)",
        help_text="The selected series determines the regulatory license and loan-number sequence.",
        queryset=LoanSeries.objects.none(),
        widget=s2forms.Select2Widget(
            attrs={"data-placeholder": "Search by license number or series"},
        ),
    )
    product_version = forms.ModelChoiceField(
        label="Loan product",
        queryset=LoanProductVersion.objects.none(),
    )
    loan_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    tenure_months = forms.IntegerField(min_value=1, initial=3)

    def __init__(self, *args, workspace, instance=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["borrower"].widget.data_url = reverse(
            "workspace_party:party_autocomplete", args=[workspace.slug]
        )
        self.fields["borrower"].queryset = Party.objects.filter(
            workspace=workspace, status=Party.PartyStatus.ACTIVE
        ).order_by("display_name", "party_code")
        self.fields["series"].queryset = LoanSeries.objects.filter(
            license__workspace=workspace
        ).select_related("license").order_by("license__license_number", "code")
        self.fields["product_version"].queryset = LoanProductVersion.objects.filter(
            product__workspace=workspace,
            product__is_active=True,
            status=LoanProductVersionStatus.ACTIVE.value,
        ).select_related("product").order_by("product__name", "version")
        if instance is not None:
            self.initial.update(
                {
                    "borrower": instance.borrower_id,
                    "series": instance.series_id,
                    "product_version": instance.product_version_id,
                    "loan_date": instance.loan_date,
                    "tenure_months": instance.tenure_months,
                }
            )
            self.fields["series"].disabled = True
            self.fields["product_version"].disabled = True
        elif not self.is_bound:
            self._select_single_options()
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-select" if isinstance(field, forms.ModelChoiceField) else "form-control")


    def _select_single_options(self):
        from django.core.exceptions import ValidationError
        from django.db.models import Q
        from django.utils import timezone
        from .services.number_allocation import preview_number
        from .domain import LoanDocumentKind

        try:
            loan_date = self.fields["loan_date"].clean(self.initial.get("loan_date", timezone.localdate()))
        except ValidationError:
            return
        if "series" not in self.initial:
            candidates = []
            for series in self.fields["series"].queryset.filter(
                is_active=True, license__is_active=True,
                license__issued_on__lte=loan_date, license__expires_on__gte=loan_date,
            ):
                try:
                    preview_number(series=series, document_kind=LoanDocumentKind.PAWN_LOAN)
                except ValueError:
                    continue
                candidates.append(series.pk)
                if len(candidates) > 1:
                    break
            if len(candidates) == 1:
                self.initial["series"] = candidates[0]
                self.fields["series"].help_text += " Selected automatically because only one series is currently usable. Review it for your loan date."
        if "product_version" not in self.initial:
            candidates = list(self.fields["product_version"].queryset.filter(
                Q(available_from__isnull=True) | Q(available_from__lte=loan_date),
            ).filter(
                Q(available_until__isnull=True) | Q(available_until__gte=loan_date),
            ).values_list("pk", flat=True)[:2])
            if len(candidates) == 1:
                self.initial["product_version"] = candidates[0]
                self.fields["product_version"].help_text = "The only product available for this date is selected. Review its terms and tenure."


class PawnCollateralDraftForm(forms.ModelForm):
    collateral_item_id = forms.IntegerField(required=False, widget=forms.HiddenInput())
    photograph = forms.FileField(
        required=False,
        help_text="JPEG or PNG, up to 10 MB. New collateral requires one photograph.",
    )

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
        self.fields["photograph"].widget.attrs.update({
            "class": "form-control js-collateral-photo-input",
            "accept": "image/jpeg,image/png",
            "capture": "environment",
        })
        self.fields["metal"].choices = [
            (item.value, item.name.title())
            for item in CollateralMetal
            if item in {CollateralMetal.GOLD, CollateralMetal.SILVER}
        ]
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-select" if field is self.fields["metal"] else "form-control")

    def clean(self):
        cleaned = super().clean()
        if (
            cleaned.get("description")
            and not cleaned.get("collateral_item_id")
            and not cleaned.get("photograph")
        ):
            self.add_error("photograph", "New collateral requires a JPEG or PNG photograph.")
        return cleaned


class PawnDraftSplitForm(forms.Form):
    collateral_items = forms.ModelMultipleChoiceField(
        queryset=PawnCollateralItem.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        help_text="Selected items move to one new draft. At least one item stays here.",
    )
    series = forms.ModelChoiceField(queryset=LoanSeries.objects.none())
    product_version = forms.ModelChoiceField(queryset=LoanProductVersion.objects.none(), label="Loan product")
    loan_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    tenure_months = forms.IntegerField(min_value=1, initial=3)

    def __init__(self, *args, workspace, source, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["collateral_items"].queryset = source.collateral_items.order_by("pk")
        self.fields["series"].queryset = LoanSeries.objects.filter(license__workspace=workspace, is_active=True).select_related("license")
        self.fields["product_version"].queryset = LoanProductVersion.objects.filter(product__workspace=workspace, product__is_active=True, status=LoanProductVersionStatus.ACTIVE.value).select_related("product")
        for field in ("series", "product_version", "loan_date", "tenure_months"):
            self.fields[field].widget.attrs.setdefault("class", "form-select" if field in {"series", "product_version"} else "form-control")

    def clean_collateral_items(self):
        selected = self.cleaned_data["collateral_items"]
        if selected.count() >= self.fields["collateral_items"].queryset.count():
            raise forms.ValidationError("At least one collateral item must remain on the source draft.")
        return selected


class PawnCollateralPhotoForm(forms.Form):
    photograph = forms.FileField(help_text="JPEG or PNG, up to 10 MB.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["photograph"].widget.attrs.update({
            "class": "form-control js-collateral-photo-input",
            "accept": "image/jpeg,image/png",
            "capture": "environment",
        })


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


PawnCollateralDraftFormSet = forms.formset_factory(
    PawnCollateralDraftForm,
    extra=0,
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


class PawnTransitionReasonForm(forms.Form):
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}))


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
    confirm_collateral_handoff = forms.BooleanField(
        label=(
            "I confirm the exact settlement was collected and every listed "
            "collateral item was physically returned to the customer."
        )
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["settlement_amount"].widget.attrs["class"] = "form-control"
        self.fields["confirm_collateral_handoff"].widget.attrs["class"] = "form-check-input"


class PawnReversalForm(forms.Form):
    reason = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
        help_text="This reason becomes immutable correction evidence.",
    )
    confirm_reversal = forms.BooleanField(
        label=(
            "I confirm this is the newest unreversed event and understand that "
            "the correction is compensating evidence, not an edit or deletion."
        ),
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
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
    confirm_notice_snapshot = forms.BooleanField(
        label=(
            "I confirm the borrower, delivery channel, due amounts, and schedule "
            "shown for this notice."
        )
    )

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
        label="Principal paid now",
        max_digits=18,
        decimal_places=2,
        min_value=0,
        initial=0,
    )
    top_up_amount = forms.DecimalField(
        label="Additional principal paid to borrower",
        max_digits=18,
        decimal_places=2,
        min_value=0,
        initial=0,
    )
    successor_license = forms.ModelChoiceField(queryset=LoanLicense.objects.none())
    successor_series = forms.ModelChoiceField(queryset=LoanSeries.objects.none())
    tenure_months = forms.IntegerField(min_value=1, max_value=600)
    request_key = forms.CharField(max_length=120, widget=forms.HiddenInput())
    preview_fingerprint = forms.CharField(
        max_length=64,
        required=False,
        widget=forms.HiddenInput(),
    )
    confirm_renewal_plan = forms.BooleanField(
        label=(
            "I confirm the source settlement, returned items, retained items, "
            "additional collateral, and successor allocations shown here."
        )
    )

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
            if isinstance(field, forms.BooleanField):
                field.widget.attrs.setdefault("class", "form-check-input")
            elif name != "mode":
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
        mode = cleaned.get("mode")
        principal_paid = cleaned.get("principal_paid")
        top_up_amount = cleaned.get("top_up_amount")
        if (
            mode == PawnLoanRenewalMode.PAY_AND_RENEW.value
            and top_up_amount is not None
            and top_up_amount != 0
        ):
            self.add_error("top_up_amount", "Pay and renew cannot include a top-up.")
        if mode == PawnLoanRenewalMode.TOP_UP_RENEW.value:
            if top_up_amount is not None and top_up_amount <= 0:
                self.add_error("top_up_amount", "Top-up renewal requires a positive amount.")
            if principal_paid is not None and principal_paid != 0:
                self.add_error(
                    "principal_paid",
                    "Top-up renewal cannot include a simultaneous principal payment.",
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
