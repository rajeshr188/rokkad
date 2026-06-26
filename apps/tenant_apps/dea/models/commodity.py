import re
from decimal import Decimal

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models


MONETARY_CURRENCY_CODES = {
    "INR",
    "USD",
    "AUD",
    "EUR",
    "GBP",
    "CAD",
    "SGD",
    "AED",
    "JPY",
    "CHF",
    "CNY",
}

COMMODITY_CODE_RE = re.compile(r"^[A-Z0-9_]+$")


class Commodity(models.Model):
    class CommodityType(models.TextChoices):
        METAL = "METAL", "Metal"
        OTHER = "OTHER", "Other"

    class UnitOfMeasure(models.TextChoices):
        GRAM = "GRAM", "Gram"
        KG = "KG", "Kilogram"
        TOLA = "TOLA", "Tola"
        OUNCE = "OUNCE", "Ounce"

    code = models.CharField(max_length=16, db_index=True)
    name = models.CharField(max_length=64)
    commodity_type = models.CharField(
        max_length=16,
        choices=CommodityType.choices,
        default=CommodityType.METAL,
    )
    default_uom = models.CharField(
        max_length=16,
        choices=UnitOfMeasure.choices,
        default=UnitOfMeasure.GRAM,
    )
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("code",)
        constraints = [
            models.UniqueConstraint(fields=["code"], name="uniq_dea_commodity_code"),
        ]
        indexes = [
            models.Index(fields=["code"], name="idx_dea_commodity_code"),
            models.Index(
                fields=["is_active", "commodity_type"],
                name="idx_dea_commodity_active_type",
            ),
        ]

    def clean(self):
        super().clean()
        self.code = (self.code or "").strip().upper()
        if not self.code:
            raise ValidationError({"code": "Commodity code is required."})
        if not COMMODITY_CODE_RE.match(self.code):
            raise ValidationError(
                {"code": "Commodity code must use uppercase letters, numbers, or underscore."}
            )
        if self.code in MONETARY_CURRENCY_CODES:
            raise ValidationError(
                {
                    "code": (
                        "Commodity code must not be a monetary currency code. "
                        "Use financial currency configuration for money."
                    )
                }
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} - {self.name}"


class CommodityAccount(models.Model):
    class Purpose(models.TextChoices):
        OWNED_STOCK = "OWNED_STOCK", "Owned stock"
        VAULT = "VAULT", "Vault"
        KARIGAR_CUSTODY = "KARIGAR_CUSTODY", "Karigar custody"
        PARTY_RECEIVABLE = "PARTY_RECEIVABLE", "Party receivable"
        PARTY_PAYABLE = "PARTY_PAYABLE", "Party payable"
        ADJUSTMENT = "ADJUSTMENT", "Adjustment"
        LOSS_GAIN = "LOSS_GAIN", "Loss/gain"

    PARTY_REQUIRED_PURPOSES = {
        Purpose.KARIGAR_CUSTODY,
        Purpose.PARTY_RECEIVABLE,
        Purpose.PARTY_PAYABLE,
    }

    code = models.CharField(max_length=64, db_index=True)
    name = models.CharField(max_length=128)
    commodity = models.ForeignKey(
        Commodity,
        on_delete=models.PROTECT,
        related_name="commodity_accounts",
    )
    purpose = models.CharField(max_length=32, choices=Purpose.choices)
    party = models.ForeignKey(
        "party.Party",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="commodity_accounts",
    )
    location_label = models.CharField(max_length=128, blank=True)
    financial_control_ledger = models.ForeignKey(
        "dea.Ledger",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="commodity_accounts",
        help_text="Optional reconciliation reference only; not a metal balance.",
    )
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("commodity__code", "code")
        constraints = [
            models.UniqueConstraint(
                fields=["code"], name="uniq_dea_commodity_account_code"
            ),
        ]
        indexes = [
            models.Index(fields=["code"], name="idx_dea_comm_account_code"),
            models.Index(
                fields=["commodity", "purpose"],
                name="idx_dea_comm_account_purpose",
            ),
            models.Index(
                fields=["party", "commodity", "purpose"],
                name="idx_dea_comm_account_party",
            ),
            models.Index(
                fields=["is_active", "commodity"],
                name="idx_dea_comm_account_active",
            ),
        ]

    def clean(self):
        super().clean()
        self.code = (self.code or "").strip().upper()
        if not self.code:
            raise ValidationError({"code": "Commodity account code is required."})
        if not COMMODITY_CODE_RE.match(self.code):
            raise ValidationError(
                {
                    "code": (
                        "Commodity account code must use uppercase letters, "
                        "numbers, or underscore."
                    )
                }
            )
        if self.purpose in self.PARTY_REQUIRED_PURPOSES and not self.party_id:
            raise ValidationError(
                {"party": "Party is required for this commodity account purpose."}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} - {self.name}"


class CommodityMovement(models.Model):
    FINE_WEIGHT_TOLERANCE = Decimal("0.001")

    class MovementType(models.TextChoices):
        OPENING = "OPENING", "Opening"
        PURCHASE_RECEIPT = "PURCHASE_RECEIPT", "Purchase receipt"
        SALE_ISSUE = "SALE_ISSUE", "Sale issue"
        RATE_FIXING = "RATE_FIXING", "Rate fixing"
        KARIGAR_ISSUE = "KARIGAR_ISSUE", "Karigar issue"
        KARIGAR_RECEIPT = "KARIGAR_RECEIPT", "Karigar receipt"
        ADJUSTMENT_IN = "ADJUSTMENT_IN", "Adjustment in"
        ADJUSTMENT_OUT = "ADJUSTMENT_OUT", "Adjustment out"
        REVERSAL = "REVERSAL", "Reversal"

    class FixedStatus(models.TextChoices):
        FIXED = "FIXED", "Fixed"
        UNFIXED = "UNFIXED", "Unfixed"
        PARTIALLY_FIXED = "PARTIALLY_FIXED", "Partially fixed"
        NOT_APPLICABLE = "NOT_APPLICABLE", "Not applicable"

    movement_no = models.CharField(max_length=64, db_index=True)
    movement_date = models.DateField(db_index=True)
    source_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        related_name="dea_commodity_movements",
    )
    source_object_id = models.PositiveIntegerField()
    source = GenericForeignKey("source_content_type", "source_object_id")
    voucher = models.ForeignKey(
        "dea.Voucher",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="commodity_movements",
    )
    commodity = models.ForeignKey(
        Commodity,
        on_delete=models.PROTECT,
        related_name="movements",
    )
    uom = models.CharField(
        max_length=16,
        choices=Commodity.UnitOfMeasure.choices,
        default=Commodity.UnitOfMeasure.GRAM,
    )
    gross_weight = models.DecimalField(max_digits=14, decimal_places=3)
    purity = models.DecimalField(max_digits=7, decimal_places=6)
    fine_weight = models.DecimalField(max_digits=14, decimal_places=3)
    from_account = models.ForeignKey(
        CommodityAccount,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="outgoing_movements",
    )
    to_account = models.ForeignKey(
        CommodityAccount,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="incoming_movements",
    )
    movement_type = models.CharField(max_length=32, choices=MovementType.choices)
    fixed_status = models.CharField(
        max_length=16,
        choices=FixedStatus.choices,
        default=FixedStatus.NOT_APPLICABLE,
    )
    rate = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        null=True,
        blank=True,
    )
    rate_currency = models.CharField(max_length=3, blank=True)
    valuation_currency = models.CharField(max_length=3, blank=True)
    valuation_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
    )
    is_reversal_of = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reversal_movements",
    )
    idempotency_key = models.CharField(max_length=128, db_index=True)
    narration = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dea_commodity_movements",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("movement_date", "movement_no")
        constraints = [
            models.UniqueConstraint(
                fields=["movement_no"], name="uniq_dea_commodity_movement_no"
            ),
            models.UniqueConstraint(
                fields=["idempotency_key"],
                name="uniq_dea_commodity_movement_idempotency",
            ),
            models.UniqueConstraint(
                fields=["is_reversal_of"],
                condition=models.Q(is_reversal_of__isnull=False),
                name="uniq_dea_commodity_movement_reversal",
            ),
            models.CheckConstraint(
                condition=models.Q(gross_weight__gt=0),
                name="ck_dea_commodity_movement_gross_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(fine_weight__gt=0),
                name="ck_dea_commodity_movement_fine_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(purity__gt=0) & models.Q(purity__lte=1),
                name="ck_dea_commodity_movement_purity_valid",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(from_account__isnull=False)
                    | models.Q(to_account__isnull=False)
                ),
                name="ck_dea_commodity_movement_one_side",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(from_account__isnull=True)
                    | models.Q(to_account__isnull=True)
                    | ~models.Q(from_account=models.F("to_account"))
                ),
                name="ck_dea_commodity_movement_diff_accounts",
            ),
        ]
        indexes = [
            models.Index(
                fields=["source_content_type", "source_object_id"],
                name="idx_dea_comm_move_source",
            ),
            models.Index(fields=["voucher"], name="idx_dea_comm_move_voucher"),
            models.Index(
                fields=["commodity", "movement_date"],
                name="idx_dea_comm_move_position",
            ),
            models.Index(
                fields=["from_account", "movement_date"],
                name="idx_dea_comm_move_from",
            ),
            models.Index(
                fields=["to_account", "movement_date"],
                name="idx_dea_comm_move_to",
            ),
            models.Index(
                fields=["is_reversal_of"],
                name="idx_dea_comm_move_reversal",
            ),
        ]

    def clean(self):
        super().clean()
        self.movement_no = (self.movement_no or "").strip().upper()
        self.idempotency_key = (self.idempotency_key or "").strip()
        self.rate_currency = (self.rate_currency or "").strip().upper()
        self.valuation_currency = (self.valuation_currency or "").strip().upper()

        errors = {}
        if not self.movement_no:
            errors["movement_no"] = "Movement number is required."
        if not self.idempotency_key:
            errors["idempotency_key"] = "Idempotency key is required."

        self._validate_accounts(errors)
        self._validate_fine_weight(errors)
        self._validate_monetary_fields(errors)
        self._validate_reversal(errors)

        if errors:
            raise ValidationError(errors)

    def _validate_accounts(self, errors):
        if not self.from_account_id and not self.to_account_id:
            errors["to_account"] = "At least one movement side is required."
            return
        if (
            self.from_account_id
            and self.to_account_id
            and self.from_account_id == self.to_account_id
        ):
            errors["to_account"] = "From and to commodity accounts must differ."

        for field_name, account in (
            ("from_account", self.from_account),
            ("to_account", self.to_account),
        ):
            if account and self.commodity_id and account.commodity_id != self.commodity_id:
                errors[field_name] = (
                    "Commodity account commodity must match movement commodity."
                )

    def _validate_fine_weight(self, errors):
        if self.gross_weight is None or self.purity is None or self.fine_weight is None:
            return
        expected_fine_weight = (self.gross_weight * self.purity).quantize(
            Decimal("0.001")
        )
        if abs(self.fine_weight - expected_fine_weight) > self.FINE_WEIGHT_TOLERANCE:
            errors["fine_weight"] = (
                "Fine weight must match gross weight multiplied by purity."
            )

    def _validate_monetary_fields(self, errors):
        for field_name in ("rate_currency", "valuation_currency"):
            currency = getattr(self, field_name)
            if currency and currency not in MONETARY_CURRENCY_CODES:
                errors[field_name] = (
                    "Currency must be a supported monetary currency code."
                )

        if self.rate is not None and not self.rate_currency:
            errors["rate_currency"] = "Rate currency is required when rate is set."
        if self.valuation_amount is not None and not self.valuation_currency:
            errors["valuation_currency"] = (
                "Valuation currency is required when valuation amount is set."
            )

    def _validate_reversal(self, errors):
        if self.movement_type != self.MovementType.REVERSAL:
            if self.is_reversal_of_id:
                errors["is_reversal_of"] = (
                    "Only reversal movements can reference an original movement."
                )
            return

        original = self.is_reversal_of
        if original is None:
            errors["is_reversal_of"] = "Reversal movement must reference original."
            return
        if original.movement_type == self.MovementType.REVERSAL:
            errors["is_reversal_of"] = "Cannot reverse a reversal movement."
        if self.commodity_id and original.commodity_id != self.commodity_id:
            errors["commodity"] = "Reversal commodity must match original movement."
        if self.uom != original.uom:
            errors["uom"] = "Reversal unit of measure must match original movement."
        if self.gross_weight != original.gross_weight:
            errors["gross_weight"] = "Reversal gross weight must match original."
        if self.purity != original.purity:
            errors["purity"] = "Reversal purity must match original."
        if self.fine_weight != original.fine_weight:
            errors["fine_weight"] = "Reversal fine weight must match original."
        if self.from_account_id != original.to_account_id:
            errors["from_account"] = "Reversal from account must invert original."
        if self.to_account_id != original.from_account_id:
            errors["to_account"] = "Reversal to account must invert original."

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Commodity movements are immutable after creation.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Commodity movements cannot be deleted; post a reversal.")

    def __str__(self):
        return f"{self.movement_no} - {self.commodity.code} {self.fine_weight} {self.uom}"


class ExposureLine(models.Model):
    class Side(models.TextChoices):
        PURCHASE = "PURCHASE", "Purchase"
        SALE = "SALE", "Sale"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        PARTIALLY_FIXED = "PARTIALLY_FIXED", "Partially fixed"
        FIXED = "FIXED", "Fixed"
        REVERSED = "REVERSED", "Reversed"
        CLOSED = "CLOSED", "Closed"

    exposure_no = models.CharField(max_length=64, db_index=True)
    source_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        related_name="dea_exposure_lines",
    )
    source_object_id = models.PositiveIntegerField()
    source = GenericForeignKey("source_content_type", "source_object_id")
    voucher = models.ForeignKey(
        "dea.Voucher",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="commodity_exposures",
    )
    party = models.ForeignKey(
        "party.Party",
        on_delete=models.PROTECT,
        related_name="commodity_exposures",
    )
    commodity = models.ForeignKey(
        Commodity,
        on_delete=models.PROTECT,
        related_name="exposures",
    )
    side = models.CharField(max_length=16, choices=Side.choices)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.OPEN,
    )
    fixed_status = models.CharField(
        max_length=16,
        choices=CommodityMovement.FixedStatus.choices,
        default=CommodityMovement.FixedStatus.UNFIXED,
    )
    original_fine_weight = models.DecimalField(max_digits=14, decimal_places=3)
    open_fine_weight = models.DecimalField(max_digits=14, decimal_places=3)
    uom = models.CharField(
        max_length=16,
        choices=Commodity.UnitOfMeasure.choices,
        default=Commodity.UnitOfMeasure.GRAM,
    )
    rate_basis = models.CharField(max_length=64, blank=True)
    valuation_currency = models.CharField(max_length=3, default="INR")
    last_valuation_rate = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        null=True,
        blank=True,
    )
    last_valuation_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
    )
    is_reversal_of = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reversal_exposures",
    )
    idempotency_key = models.CharField(max_length=128, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dea_exposure_lines",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("exposure_no",)
        constraints = [
            models.UniqueConstraint(
                fields=["exposure_no"], name="uniq_dea_exposure_no"
            ),
            models.UniqueConstraint(
                fields=["idempotency_key"], name="uniq_dea_exposure_idempotency"
            ),
            models.CheckConstraint(
                condition=models.Q(original_fine_weight__gt=0),
                name="ck_dea_exposure_original_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(open_fine_weight__gte=0),
                name="ck_dea_exposure_open_non_negative",
            ),
        ]
        indexes = [
            models.Index(
                fields=["source_content_type", "source_object_id"],
                name="idx_dea_exposure_source",
            ),
            models.Index(fields=["party", "status"], name="idx_dea_exposure_party"),
            models.Index(
                fields=["commodity", "status"],
                name="idx_dea_exposure_commodity",
            ),
            models.Index(fields=["side", "status"], name="idx_dea_exposure_side"),
        ]

    def clean(self):
        super().clean()
        self.exposure_no = (self.exposure_no or "").strip().upper()
        self.idempotency_key = (self.idempotency_key or "").strip()
        self.valuation_currency = (self.valuation_currency or "").strip().upper()

        errors = {}
        if not self.exposure_no:
            errors["exposure_no"] = "Exposure number is required."
        if not self.idempotency_key:
            errors["idempotency_key"] = "Idempotency key is required."
        if self.valuation_currency not in MONETARY_CURRENCY_CODES:
            errors["valuation_currency"] = (
                "Valuation currency must be a supported monetary currency code."
            )
        if (
            self.original_fine_weight is not None
            and self.open_fine_weight is not None
            and self.open_fine_weight > self.original_fine_weight
        ):
            errors["open_fine_weight"] = (
                "Open fine weight cannot exceed original fine weight."
            )
        if (
            self.status == self.Status.FIXED
            and self.open_fine_weight is not None
            and self.open_fine_weight != Decimal("0.000")
        ):
            errors["status"] = "Fixed exposure must have zero open fine weight."
        if (
            self.status == self.Status.OPEN
            and self.open_fine_weight is not None
            and self.open_fine_weight <= 0
        ):
            errors["status"] = "Open exposure must have positive open fine weight."
        if self.status == self.Status.REVERSED and not self.is_reversal_of_id:
            errors["is_reversal_of"] = "Reversed exposure must reference original."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.exposure_no} - {self.side} {self.commodity.code} {self.open_fine_weight}"


class RateFixing(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        POSTED = "POSTED", "Posted"
        REVERSED = "REVERSED", "Reversed"
        CORRECTED = "CORRECTED", "Corrected"

    fixing_no = models.CharField(max_length=64, db_index=True)
    fixing_date = models.DateField(db_index=True)
    party = models.ForeignKey(
        "party.Party",
        on_delete=models.PROTECT,
        related_name="commodity_rate_fixings",
    )
    commodity = models.ForeignKey(
        Commodity,
        on_delete=models.PROTECT,
        related_name="rate_fixings",
    )
    side = models.CharField(max_length=16, choices=ExposureLine.Side.choices)
    fine_weight = models.DecimalField(max_digits=14, decimal_places=3)
    uom = models.CharField(
        max_length=16,
        choices=Commodity.UnitOfMeasure.choices,
        default=Commodity.UnitOfMeasure.GRAM,
    )
    rate = models.DecimalField(max_digits=14, decimal_places=4)
    currency = models.CharField(max_length=3, default="INR")
    valuation_amount = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    voucher = models.ForeignKey(
        "dea.Voucher",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="commodity_rate_fixings",
    )
    idempotency_key = models.CharField(max_length=128, db_index=True, blank=True)
    narration = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dea_rate_fixings_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dea_rate_fixings_updated",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("fixing_date", "fixing_no")
        constraints = [
            models.UniqueConstraint(
                fields=["fixing_no"], name="uniq_dea_rate_fixing_no"
            ),
            models.UniqueConstraint(
                fields=["idempotency_key"],
                condition=~models.Q(idempotency_key=""),
                name="uniq_dea_rate_fixing_idempotency",
            ),
            models.CheckConstraint(
                condition=models.Q(fine_weight__gt=0),
                name="ck_dea_rate_fixing_weight_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(rate__gt=0),
                name="ck_dea_rate_fixing_rate_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(valuation_amount__gt=0),
                name="ck_dea_rate_fixing_value_positive",
            ),
        ]
        indexes = [
            models.Index(fields=["party", "status"], name="idx_dea_fixing_party"),
            models.Index(
                fields=["commodity", "fixing_date"],
                name="idx_dea_fixing_commodity_date",
            ),
            models.Index(fields=["voucher"], name="idx_dea_fixing_voucher"),
        ]

    def clean(self):
        super().clean()
        self.fixing_no = (self.fixing_no or "").strip().upper()
        self.currency = (self.currency or "").strip().upper()
        self.idempotency_key = (self.idempotency_key or "").strip()

        errors = {}
        if not self.fixing_no:
            errors["fixing_no"] = "Fixing number is required."
        if self.currency not in MONETARY_CURRENCY_CODES:
            errors["currency"] = "Currency must be a supported monetary currency code."
        if self.status != self.Status.DRAFT and not self.idempotency_key:
            errors["idempotency_key"] = (
                "Idempotency key is required outside draft status."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk:
            original = RateFixing.objects.get(pk=self.pk)
            if original.status != self.Status.DRAFT:
                raise ValidationError("Posted rate fixings are immutable.")
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.fixing_no} - {self.side} {self.commodity.code} {self.fine_weight}"


class RateFixingAllocation(models.Model):
    rate_fixing = models.ForeignKey(
        RateFixing,
        on_delete=models.CASCADE,
        related_name="allocations",
    )
    exposure = models.ForeignKey(
        ExposureLine,
        on_delete=models.PROTECT,
        related_name="rate_fixing_allocations",
    )
    fine_weight = models.DecimalField(max_digits=14, decimal_places=3)
    amount = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["rate_fixing", "exposure"],
                name="uniq_dea_rate_fixing_exposure",
            ),
            models.CheckConstraint(
                condition=models.Q(fine_weight__gt=0),
                name="ck_dea_fixing_alloc_weight_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="ck_dea_fixing_alloc_amount_positive",
            ),
        ]
        indexes = [
            models.Index(
                fields=["rate_fixing", "exposure"],
                name="idx_dea_fixing_alloc_parent",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.rate_fixing and self.exposure:
            if self.rate_fixing.party_id != self.exposure.party_id:
                errors["exposure"] = "Exposure party must match fixing party."
            if self.rate_fixing.commodity_id != self.exposure.commodity_id:
                errors["exposure"] = "Exposure commodity must match fixing commodity."
            if self.rate_fixing.side != self.exposure.side:
                errors["exposure"] = "Exposure side must match fixing side."
            if self.rate_fixing.uom != self.exposure.uom:
                errors["exposure"] = "Exposure unit must match fixing unit."
            if (
                self.fine_weight is not None
                and self.exposure.open_fine_weight is not None
                and self.fine_weight > self.exposure.open_fine_weight
            ):
                errors["fine_weight"] = (
                    "Allocation fine weight cannot exceed exposure open fine weight."
                )
            if self.exposure.status in {
                ExposureLine.Status.FIXED,
                ExposureLine.Status.REVERSED,
                ExposureLine.Status.CLOSED,
            }:
                errors["exposure"] = "Exposure is not open for rate fixing."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.rate_fixing.fixing_no} -> {self.exposure.exposure_no}"
