from decimal import Decimal

from django import forms

from apps.tenant_apps.dea.models import (
    Account,
    Commodity,
    CommodityAccount,
    CommodityMovement,
    ExposureLine,
    Ledger,
    PaymentMethod,
)
from apps.tenant_apps.dea.models.commodity import MONETARY_CURRENCY_CODES
from apps.tenant_apps.party.models import Party


class FixedPurchasePreviewForm(forms.Form):
    source_reference = forms.CharField(
        max_length=80,
        help_text="Supplier bill, memo, or temporary document reference.",
    )
    purchase_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    supplier_account = forms.ModelChoiceField(queryset=Account.objects.none())
    inventory_ledger = forms.ModelChoiceField(queryset=Ledger.objects.none())
    payable_ledger = forms.ModelChoiceField(queryset=Ledger.objects.none())
    commodity = forms.ModelChoiceField(queryset=Commodity.objects.none())
    gross_weight = forms.DecimalField(max_digits=14, decimal_places=3, min_value=Decimal("0.001"))
    purity = forms.DecimalField(max_digits=7, decimal_places=6, min_value=Decimal("0.000001"))
    fine_weight = forms.DecimalField(max_digits=14, decimal_places=3, min_value=Decimal("0.001"))
    from_commodity_account = forms.ModelChoiceField(
        queryset=CommodityAccount.objects.none(),
        label="Supplier metal account (source)",
        help_text="Select the supplier-side commodity account the metal is coming from.",
    )
    to_commodity_account = forms.ModelChoiceField(
        queryset=CommodityAccount.objects.none(),
        label="Your stock/vault account (destination)",
        help_text="Select your commodity account that will receive the purchased metal.",
    )
    money_amount = forms.DecimalField(max_digits=15, decimal_places=2, min_value=Decimal("0.01"))
    currency = forms.ChoiceField(choices=(("INR", "INR"),), initial="INR")
    narration = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["supplier_account"].queryset = Account.objects.select_related(
            "contact",
            "AccountType_Ext",
        ).order_by("account_number", "id")
        self.fields["inventory_ledger"].queryset = Ledger.objects.select_related(
            "AccountType",
        ).order_by("name", "id")
        self.fields["payable_ledger"].queryset = Ledger.objects.select_related(
            "AccountType",
        ).order_by("name", "id")
        self.fields["commodity"].queryset = Commodity.objects.filter(
            is_active=True,
        ).order_by("code")
        self.fields["from_commodity_account"].queryset = CommodityAccount.objects.filter(
            is_active=True,
        ).select_related("commodity", "party").order_by("commodity__code", "code")
        self.fields["to_commodity_account"].queryset = CommodityAccount.objects.filter(
            is_active=True,
        ).select_related("commodity", "party").order_by("commodity__code", "code")

    def clean_currency(self):
        currency = (self.cleaned_data["currency"] or "").strip().upper()
        if currency != "INR":
            raise forms.ValidationError("Fixed purchase preview currently supports INR only.")
        if currency not in MONETARY_CURRENCY_CODES:
            raise forms.ValidationError("Currency must be a supported monetary currency code.")
        return currency

    def clean(self):
        cleaned = super().clean()
        commodity = cleaned.get("commodity")
        from_account = cleaned.get("from_commodity_account")
        to_account = cleaned.get("to_commodity_account")
        if not commodity or not from_account or not to_account:
            return cleaned
        if from_account == to_account:
            raise forms.ValidationError(
                "From and to commodity accounts must be different."
            )
        if (
            from_account.commodity_id != commodity.pk
            or to_account.commodity_id != commodity.pk
        ):
            raise forms.ValidationError(
                "Commodity accounts must belong to the selected commodity."
            )
        return cleaned


class UnfixedPurchasePreviewForm(forms.Form):
    source_reference = forms.CharField(
        max_length=80,
        help_text="Supplier memo, receipt, or temporary unfixed purchase reference.",
    )
    purchase_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    party = forms.ModelChoiceField(queryset=Party.objects.none())
    commodity = forms.ModelChoiceField(queryset=Commodity.objects.none())
    gross_weight = forms.DecimalField(max_digits=14, decimal_places=3, min_value=Decimal("0.001"))
    purity = forms.DecimalField(max_digits=7, decimal_places=6, min_value=Decimal("0.000001"))
    fine_weight = forms.DecimalField(max_digits=14, decimal_places=3, min_value=Decimal("0.001"))
    from_commodity_account = forms.ModelChoiceField(
        queryset=CommodityAccount.objects.none(),
        label="Supplier metal account (source)",
        help_text="Select the supplier-side commodity account the unfixed metal is coming from.",
    )
    to_commodity_account = forms.ModelChoiceField(
        queryset=CommodityAccount.objects.none(),
        label="Your stock/vault account (destination)",
        help_text="Select your commodity account that will hold this unfixed metal until rate fixing.",
    )
    rate_basis = forms.CharField(
        required=False,
        max_length=120,
        help_text="Market source, contract term, or verbal basis for later fixing.",
    )
    valuation_currency = forms.ChoiceField(choices=(("INR", "INR"),), initial="INR")
    last_valuation_rate = forms.DecimalField(
        max_digits=15,
        decimal_places=4,
        min_value=Decimal("0.0001"),
        required=False,
    )
    narration = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["party"].queryset = Party.objects.exclude(
            status=Party.PartyStatus.ARCHIVED,
        ).order_by("display_name", "id")
        self.fields["commodity"].queryset = Commodity.objects.filter(
            is_active=True,
        ).order_by("code")
        self.fields["from_commodity_account"].queryset = CommodityAccount.objects.filter(
            is_active=True,
        ).select_related("commodity", "party").order_by("commodity__code", "code")
        self.fields["to_commodity_account"].queryset = CommodityAccount.objects.filter(
            is_active=True,
        ).select_related("commodity", "party").order_by("commodity__code", "code")

    def clean_valuation_currency(self):
        currency = (self.cleaned_data["valuation_currency"] or "").strip().upper()
        if currency != "INR":
            raise forms.ValidationError("Unfixed purchase preview currently supports INR valuation only.")
        if currency not in MONETARY_CURRENCY_CODES:
            raise forms.ValidationError("Valuation currency must be a supported monetary currency code.")
        return currency

    def clean(self):
        cleaned = super().clean()
        commodity = cleaned.get("commodity")
        from_account = cleaned.get("from_commodity_account")
        to_account = cleaned.get("to_commodity_account")
        if not commodity or not from_account or not to_account:
            return cleaned
        if from_account == to_account:
            raise forms.ValidationError(
                "From and to commodity accounts must be different."
            )
        if (
            from_account.commodity_id != commodity.pk
            or to_account.commodity_id != commodity.pk
        ):
            raise forms.ValidationError(
                "Commodity accounts must belong to the selected commodity."
            )
        return cleaned


class PurchaseRateFixingPreviewForm(forms.Form):
    source_reference = forms.CharField(
        max_length=80,
        help_text="Rate-fixing memo, supplier call reference, or temporary document reference.",
    )
    exposure = forms.ModelChoiceField(queryset=ExposureLine.objects.none())
    fixing_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    fine_weight = forms.DecimalField(
        max_digits=14,
        decimal_places=3,
        min_value=Decimal("0.001"),
    )
    rate = forms.DecimalField(
        max_digits=15,
        decimal_places=4,
        min_value=Decimal("0.0001"),
        help_text="INR rate per fine-weight unit.",
    )
    supplier_account = forms.ModelChoiceField(queryset=Account.objects.none())
    inventory_ledger = forms.ModelChoiceField(queryset=Ledger.objects.none())
    payable_ledger = forms.ModelChoiceField(queryset=Ledger.objects.none())
    currency = forms.ChoiceField(choices=(("INR", "INR"),), initial="INR")
    narration = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["exposure"].queryset = (
            ExposureLine.objects.filter(
                side=ExposureLine.Side.PURCHASE,
                status__in=[
                    ExposureLine.Status.OPEN,
                    ExposureLine.Status.PARTIALLY_FIXED,
                ],
                fixed_status__in=[
                    CommodityMovement.FixedStatus.UNFIXED,
                    CommodityMovement.FixedStatus.PARTIALLY_FIXED,
                ],
                open_fine_weight__gt=Decimal("0.000"),
            )
            .select_related("party", "commodity")
            .order_by("exposure_no", "id")
        )
        self.fields["supplier_account"].queryset = Account.objects.select_related(
            "contact",
            "AccountType_Ext",
        ).order_by("account_number", "id")
        self.fields["inventory_ledger"].queryset = Ledger.objects.select_related(
            "AccountType",
        ).order_by("name", "id")
        self.fields["payable_ledger"].queryset = Ledger.objects.select_related(
            "AccountType",
        ).order_by("name", "id")

    def clean_currency(self):
        currency = (self.cleaned_data["currency"] or "").strip().upper()
        if currency != "INR":
            raise forms.ValidationError("Purchase rate fixing preview currently supports INR only.")
        if currency not in MONETARY_CURRENCY_CODES:
            raise forms.ValidationError("Currency must be a supported monetary currency code.")
        return currency

    def clean(self):
        cleaned = super().clean()
        exposure = cleaned.get("exposure")
        fine_weight = cleaned.get("fine_weight")
        supplier_account = cleaned.get("supplier_account")
        if not exposure:
            return cleaned
        if exposure.side != ExposureLine.Side.PURCHASE:
            raise forms.ValidationError("Only purchase exposures can be fixed here.")
        if exposure.status not in {
            ExposureLine.Status.OPEN,
            ExposureLine.Status.PARTIALLY_FIXED,
        }:
            raise forms.ValidationError("Exposure is not open for purchase rate fixing.")
        if exposure.fixed_status not in {
            CommodityMovement.FixedStatus.UNFIXED,
            CommodityMovement.FixedStatus.PARTIALLY_FIXED,
        }:
            raise forms.ValidationError("Exposure fixed status is not open for fixing.")
        if fine_weight and fine_weight > exposure.open_fine_weight:
            raise forms.ValidationError("Fixing fine weight cannot exceed open exposure.")
        if (
            supplier_account
            and supplier_account.contact_id
            and supplier_account.contact.party_id
            and supplier_account.contact.party_id != exposure.party_id
        ):
            raise forms.ValidationError(
                "Supplier account party must match exposure party when linked."
            )
        return cleaned


class SaleRateFixingPreviewForm(forms.Form):
    source_reference = forms.CharField(
        max_length=80,
        help_text="Rate fixing memo or customer confirmation reference.",
    )
    exposure = forms.ModelChoiceField(queryset=ExposureLine.objects.none())
    fixing_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    fine_weight = forms.DecimalField(
        max_digits=14,
        decimal_places=3,
        min_value=Decimal("0.001"),
        help_text="Fine weight to fix from the open sale exposure.",
    )
    rate = forms.DecimalField(
        max_digits=15,
        decimal_places=4,
        min_value=Decimal("0.0001"),
        help_text="INR rate per fine-weight unit.",
    )
    customer_account = forms.ModelChoiceField(queryset=Account.objects.none())
    receivable_ledger = forms.ModelChoiceField(queryset=Ledger.objects.none())
    revenue_ledger = forms.ModelChoiceField(queryset=Ledger.objects.none())
    currency = forms.ChoiceField(choices=(("INR", "INR"),), initial="INR")
    narration = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["exposure"].queryset = (
            ExposureLine.objects.filter(
                side=ExposureLine.Side.SALE,
                status__in=[
                    ExposureLine.Status.OPEN,
                    ExposureLine.Status.PARTIALLY_FIXED,
                ],
                fixed_status__in=[
                    CommodityMovement.FixedStatus.UNFIXED,
                    CommodityMovement.FixedStatus.PARTIALLY_FIXED,
                ],
                open_fine_weight__gt=Decimal("0.000"),
            )
            .select_related("party", "commodity")
            .order_by("exposure_no", "id")
        )
        self.fields["customer_account"].queryset = Account.objects.select_related(
            "contact",
            "AccountType_Ext",
        ).order_by("account_number", "id")
        self.fields["receivable_ledger"].queryset = Ledger.objects.select_related(
            "AccountType",
        ).order_by("name", "id")
        self.fields["revenue_ledger"].queryset = Ledger.objects.select_related(
            "AccountType",
        ).order_by("name", "id")

    def clean_currency(self):
        currency = (self.cleaned_data["currency"] or "").strip().upper()
        if currency != "INR":
            raise forms.ValidationError("Sale rate fixing preview currently supports INR only.")
        if currency not in MONETARY_CURRENCY_CODES:
            raise forms.ValidationError("Currency must be a supported monetary currency code.")
        return currency

    def clean(self):
        cleaned = super().clean()
        exposure = cleaned.get("exposure")
        fine_weight = cleaned.get("fine_weight")
        customer_account = cleaned.get("customer_account")
        if not exposure:
            return cleaned
        if exposure.side != ExposureLine.Side.SALE:
            raise forms.ValidationError("Only sale exposures can be fixed here.")
        if exposure.status not in {
            ExposureLine.Status.OPEN,
            ExposureLine.Status.PARTIALLY_FIXED,
        }:
            raise forms.ValidationError("Exposure is not open for sale rate fixing.")
        if exposure.fixed_status not in {
            CommodityMovement.FixedStatus.UNFIXED,
            CommodityMovement.FixedStatus.PARTIALLY_FIXED,
        }:
            raise forms.ValidationError("Exposure fixed status is not open for fixing.")
        if fine_weight and fine_weight > exposure.open_fine_weight:
            raise forms.ValidationError("Fixing fine weight cannot exceed open exposure.")
        if (
            customer_account
            and customer_account.contact_id
            and customer_account.contact.party_id
            and customer_account.contact.party_id != exposure.party_id
        ):
            raise forms.ValidationError(
                "Customer account party must match exposure party when linked."
            )
        return cleaned


class FixedSalePreviewForm(forms.Form):
    source_reference = forms.CharField(
        max_length=80,
        help_text="Customer bill, sale memo, or temporary document reference.",
    )
    sale_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    customer_account = forms.ModelChoiceField(queryset=Account.objects.none())
    receivable_ledger = forms.ModelChoiceField(queryset=Ledger.objects.none())
    revenue_ledger = forms.ModelChoiceField(queryset=Ledger.objects.none())
    commodity = forms.ModelChoiceField(queryset=Commodity.objects.none())
    gross_weight = forms.DecimalField(
        max_digits=14,
        decimal_places=3,
        min_value=Decimal("0.001"),
    )
    purity = forms.DecimalField(
        max_digits=7,
        decimal_places=6,
        min_value=Decimal("0.000001"),
    )
    fine_weight = forms.DecimalField(
        max_digits=14,
        decimal_places=3,
        min_value=Decimal("0.001"),
    )
    from_commodity_account = forms.ModelChoiceField(
        queryset=CommodityAccount.objects.none(),
        help_text="Owned/vault/stock account that issues metal.",
    )
    money_amount = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )
    currency = forms.ChoiceField(choices=(("INR", "INR"),), initial="INR")
    narration = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["customer_account"].queryset = Account.objects.select_related(
            "contact",
            "AccountType_Ext",
        ).order_by("account_number", "id")
        self.fields["receivable_ledger"].queryset = Ledger.objects.select_related(
            "AccountType",
        ).order_by("name", "id")
        self.fields["revenue_ledger"].queryset = Ledger.objects.select_related(
            "AccountType",
        ).order_by("name", "id")
        self.fields["commodity"].queryset = Commodity.objects.filter(
            is_active=True,
        ).order_by("code")
        self.fields["from_commodity_account"].queryset = (
            CommodityAccount.objects.filter(is_active=True)
            .select_related("commodity", "party")
            .order_by("commodity__code", "code")
        )

    def clean_currency(self):
        currency = (self.cleaned_data["currency"] or "").strip().upper()
        if currency != "INR":
            raise forms.ValidationError("Fixed sale preview currently supports INR only.")
        if currency not in MONETARY_CURRENCY_CODES:
            raise forms.ValidationError("Currency must be a supported monetary currency code.")
        return currency

    def clean(self):
        cleaned = super().clean()
        commodity = cleaned.get("commodity")
        from_account = cleaned.get("from_commodity_account")
        if not commodity or not from_account:
            return cleaned
        if from_account.commodity_id != commodity.pk:
            raise forms.ValidationError(
                "Commodity account must belong to the selected commodity."
            )
        return cleaned


class UnfixedSalePreviewForm(forms.Form):
    source_reference = forms.CharField(
        max_length=80,
        help_text="Customer memo, delivery note, or temporary unfixed sale reference.",
    )
    sale_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    party = forms.ModelChoiceField(queryset=Party.objects.none())
    commodity = forms.ModelChoiceField(queryset=Commodity.objects.none())
    gross_weight = forms.DecimalField(
        max_digits=14,
        decimal_places=3,
        min_value=Decimal("0.001"),
    )
    purity = forms.DecimalField(
        max_digits=7,
        decimal_places=6,
        min_value=Decimal("0.000001"),
    )
    fine_weight = forms.DecimalField(
        max_digits=14,
        decimal_places=3,
        min_value=Decimal("0.001"),
    )
    from_commodity_account = forms.ModelChoiceField(
        queryset=CommodityAccount.objects.none(),
        help_text="Owned/vault/stock account that issues metal.",
    )
    rate_basis = forms.CharField(
        required=False,
        max_length=120,
        help_text="Market source, contract term, or verbal basis for later fixing.",
    )
    valuation_currency = forms.ChoiceField(choices=(("INR", "INR"),), initial="INR")
    last_valuation_rate = forms.DecimalField(
        max_digits=15,
        decimal_places=4,
        min_value=Decimal("0.0001"),
        required=False,
    )
    narration = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["party"].queryset = Party.objects.exclude(
            status=Party.PartyStatus.ARCHIVED,
        ).order_by("display_name", "id")
        self.fields["commodity"].queryset = Commodity.objects.filter(
            is_active=True,
        ).order_by("code")
        self.fields["from_commodity_account"].queryset = (
            CommodityAccount.objects.filter(is_active=True)
            .select_related("commodity", "party")
            .order_by("commodity__code", "code")
        )

    def clean_valuation_currency(self):
        currency = (self.cleaned_data["valuation_currency"] or "").strip().upper()
        if currency != "INR":
            raise forms.ValidationError("Unfixed sale preview currently supports INR valuation only.")
        if currency not in MONETARY_CURRENCY_CODES:
            raise forms.ValidationError("Valuation currency must be a supported monetary currency code.")
        return currency

    def clean(self):
        cleaned = super().clean()
        commodity = cleaned.get("commodity")
        from_account = cleaned.get("from_commodity_account")
        if not commodity or not from_account:
            return cleaned
        if from_account.commodity_id != commodity.pk:
            raise forms.ValidationError(
                "Commodity account must belong to the selected commodity."
            )
        return cleaned


class MonetarySettlementPreviewForm(forms.Form):
    class SettlementType:
        CUSTOMER_RECEIPT = "CUSTOMER_RECEIPT"
        SUPPLIER_PAYMENT = "SUPPLIER_PAYMENT"

    SETTLEMENT_CHOICES = (
        (SettlementType.CUSTOMER_RECEIPT, "Receipt from customer"),
        (SettlementType.SUPPLIER_PAYMENT, "Payment to supplier"),
    )

    settlement_type = forms.ChoiceField(choices=SETTLEMENT_CHOICES)
    source_reference = forms.CharField(
        max_length=80,
        help_text="Receipt/payment memo or temporary settlement reference.",
    )
    event_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    party_account = forms.ModelChoiceField(
        queryset=Account.objects.none(),
        help_text="Customer account for receipt, supplier account for payment.",
    )
    cash_or_bank_ledger = forms.ModelChoiceField(queryset=Ledger.objects.none())
    counterparty_ledger = forms.ModelChoiceField(
        queryset=Ledger.objects.none(),
        help_text="Receivable ledger for customer receipt, payable ledger for supplier payment.",
    )
    money_amount = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )
    reference_number = forms.CharField(
        max_length=80,
        help_text="Bank/cash receipt/payment reference used later for idempotency.",
    )
    currency = forms.ChoiceField(choices=(("INR", "INR"),), initial="INR")
    payment_method = forms.ChoiceField(
        choices=PaymentMethod.choices,
        initial=PaymentMethod.CASH,
    )
    narration = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["party_account"].queryset = Account.objects.select_related(
            "contact",
            "AccountType_Ext",
        ).order_by("account_number", "id")
        self.fields["cash_or_bank_ledger"].queryset = Ledger.objects.select_related(
            "AccountType",
        ).order_by("name", "id")
        self.fields["counterparty_ledger"].queryset = Ledger.objects.select_related(
            "AccountType",
        ).order_by("name", "id")

    def clean_currency(self):
        currency = (self.cleaned_data["currency"] or "").strip().upper()
        if currency != "INR":
            raise forms.ValidationError("Settlement preview currently supports INR only.")
        if currency not in MONETARY_CURRENCY_CODES:
            raise forms.ValidationError("Currency must be a supported monetary currency code.")
        return currency

    def clean_reference_number(self):
        reference = (self.cleaned_data["reference_number"] or "").strip()
        if not reference:
            raise forms.ValidationError("Reference number is required.")
        return reference


class KarigarMovementPreviewForm(forms.Form):
    class MovementType:
        ISSUE = "KARIGAR_ISSUE"
        RECEIPT = "KARIGAR_RECEIPT"

    MOVEMENT_CHOICES = (
        (MovementType.ISSUE, "Issue metal to karigar"),
        (MovementType.RECEIPT, "Receive metal from karigar"),
    )

    movement_type = forms.ChoiceField(choices=MOVEMENT_CHOICES)
    source_reference = forms.CharField(
        max_length=80,
        help_text="Karigar issue/receipt memo or temporary document reference.",
    )
    event_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    karigar = forms.ModelChoiceField(queryset=Party.objects.none())
    commodity = forms.ModelChoiceField(queryset=Commodity.objects.none())
    gross_weight = forms.DecimalField(
        max_digits=14,
        decimal_places=3,
        min_value=Decimal("0.001"),
    )
    purity = forms.DecimalField(
        max_digits=7,
        decimal_places=6,
        min_value=Decimal("0.000001"),
    )
    fine_weight = forms.DecimalField(
        max_digits=14,
        decimal_places=3,
        min_value=Decimal("0.001"),
    )
    from_commodity_account = forms.ModelChoiceField(
        queryset=CommodityAccount.objects.none(),
        help_text="Owned/vault account for issue; karigar custody account for receipt.",
    )
    to_commodity_account = forms.ModelChoiceField(
        queryset=CommodityAccount.objects.none(),
        help_text="Karigar custody account for issue; owned/vault account for receipt.",
    )
    narration = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["karigar"].queryset = Party.objects.exclude(
            status=Party.PartyStatus.ARCHIVED,
        ).order_by("display_name", "id")
        self.fields["commodity"].queryset = Commodity.objects.filter(
            is_active=True,
        ).order_by("code")
        account_queryset = (
            CommodityAccount.objects.filter(is_active=True)
            .select_related("commodity", "party")
            .order_by("commodity__code", "purpose", "code")
        )
        self.fields["from_commodity_account"].queryset = account_queryset
        self.fields["to_commodity_account"].queryset = account_queryset

    def clean(self):
        cleaned = super().clean()
        movement_type = cleaned.get("movement_type")
        karigar = cleaned.get("karigar")
        commodity = cleaned.get("commodity")
        from_account = cleaned.get("from_commodity_account")
        to_account = cleaned.get("to_commodity_account")
        if not movement_type or not karigar or not commodity or not from_account or not to_account:
            return cleaned
        if from_account == to_account:
            raise forms.ValidationError(
                "From and to commodity accounts must be different."
            )
        if (
            from_account.commodity_id != commodity.pk
            or to_account.commodity_id != commodity.pk
        ):
            raise forms.ValidationError(
                "Commodity accounts must belong to the selected commodity."
            )
        if movement_type == self.MovementType.ISSUE:
            if to_account.purpose != CommodityAccount.Purpose.KARIGAR_CUSTODY:
                raise forms.ValidationError(
                    "Issue destination must be a karigar custody account."
                )
            if to_account.party_id != karigar.pk:
                raise forms.ValidationError(
                    "Issue destination custody account must belong to the selected karigar."
                )
        if movement_type == self.MovementType.RECEIPT:
            if from_account.purpose != CommodityAccount.Purpose.KARIGAR_CUSTODY:
                raise forms.ValidationError(
                    "Receipt source must be a karigar custody account."
                )
            if from_account.party_id != karigar.pk:
                raise forms.ValidationError(
                    "Receipt source custody account must belong to the selected karigar."
                )
        return cleaned
