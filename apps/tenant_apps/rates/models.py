# Create your models here.
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.tenancy.models import WorkspaceOwnedModel


class RateSource(WorkspaceOwnedModel):
    name = models.CharField(max_length=30)
    location = models.CharField(max_length=30)
    tax_included = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class Rate(WorkspaceOwnedModel):
    class Metal(models.TextChoices):
        GOLD = "Gold", "Gold"
        SILVER = "Silver", "Silver"
        BRONZE = "Bronze", "Bronze"

    class Currency(models.TextChoices):
        INR = "INR", "INR"
        USD = "USD", "USD"

    class Purity(models.TextChoices):
        K24 = "24k", "Pure metal (100%)"
        K22 = "22k", "22K"
        K18 = "18k", "18K"
        K14 = "14k", "14K"
        K10 = "10k", "10K"

    metal = models.CharField(max_length=6, choices=Metal.choices, default=Metal.GOLD)
    currency = models.CharField(
        max_length=3, choices=Currency.choices, default=Currency.INR
    )
    purity = models.CharField(max_length=3, choices=Purity.choices, default=Purity.K24)
    buying_rate = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))], help_text="Currency per gram of the selected purity.")
    selling_rate = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))], help_text="Currency per gram of the selected purity.")
    effective_at = models.DateTimeField(default=timezone.now)
    timestamp = models.DateTimeField(auto_now_add=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, editable=False, on_delete=models.PROTECT, related_name="+")
    supersedes = models.OneToOneField("self", null=True, blank=True, editable=False, on_delete=models.PROTECT, related_name="successor")
    is_withdrawal = models.BooleanField(default=False, editable=False)
    reason = models.CharField(max_length=500, blank=True)
    source_snapshot = models.JSONField(default=dict, editable=False)

    # related Fields
    rate_source = models.ForeignKey("RateSource", on_delete=models.PROTECT)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "metal", "currency", "timestamp", "purity"],
                name="rates_rate_workspace_quote_uniq",
            )
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Quotes are immutable. Record a correction or withdrawal.")
        self.clean()
        if self.rate_source_id:
            source_workspace_id = self.rate_source.workspace_id
            if self.workspace_id is None:
                self.workspace_id = source_workspace_id
            elif self.workspace_id != source_workspace_id:
                raise ValidationError("Rate and rate source must share a Workspace.")
            self.source_snapshot = {"name": self.rate_source.name, "location": self.rate_source.location, "tax_included": self.rate_source.tax_included}
        if self.supersedes_id and self.supersedes.workspace_id != self.workspace_id:
            raise ValidationError("A correction must belong to the original Workspace.")
        return super().save(*args, **kwargs)

    def clean(self):
        errors = {}
        for field in ("buying_rate", "selling_rate"):
            value = getattr(self, field)
            if not self.is_withdrawal and value is not None and (not Decimal(value).is_finite() or Decimal(value) <= 0):
                errors[field] = "Enter a positive price per gram."
        if not self.is_withdrawal and self.metal != self.Metal.GOLD and self.purity != self.Purity.K24:
            errors["purity"] = "Use Pure metal for silver or bronze; karats apply to gold."
        if self.supersedes_id and (not self.reason.strip() or not self.recorded_by_id):
            errors["reason"] = "A correction or withdrawal requires a reason and actor."
        if errors:
            raise ValidationError(errors)

    def delete(self, *args, **kwargs):
        raise ValidationError("Quotes are immutable. Record a withdrawal.")

    @property
    def record_status(self):
        if self.is_withdrawal:
            return "Withdrawal"
        if hasattr(self, "successor"):
            return "Superseded"
        return "Available"

    def __str__(self):
        return f" {self.timestamp.date()} {self.metal} {self.purity} {self.buying_rate}"

    def get_absolute_url(self):
        return reverse("workspace_rates:rate_detail", kwargs={"workspace_slug": self.workspace.slug, "pk": self.pk})

    def for_purity(self, desired_purity):
        # Calculate the rate for the desired purity
        rate_for_purity = self.buying_rate * Decimal(desired_purity[1:]) / 24

        return rate_for_purity
