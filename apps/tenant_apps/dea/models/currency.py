"""
Exchange Rate tracking for multi-currency transactions
"""
from decimal import Decimal
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class ExchangeRateSource(models.TextChoices):
    """Source of exchange rate"""

    MANUAL = "MANUAL", _("Manual Entry")
    CENTRAL_BANK = "CENTRAL_BANK", _("Central Bank")
    API = "API", _("External API")
    MARKET = "MARKET", _("Market Rate")


class ExchangeRate(models.Model):
    """
    Exchange rates for currency conversion.
    Stores rates as: 1 base_currency = rate * quote_currency
    Example: 1 USD = 83.25 INR
    """

    base_currency = models.CharField(
        max_length=3, db_index=True, help_text="ISO 4217 currency code (e.g., USD)"
    )
    quote_currency = models.CharField(
        max_length=3, db_index=True, help_text="ISO 4217 currency code (e.g., INR)"
    )
    rate = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        help_text="1 base_currency = rate × quote_currency",
    )
    effective_date = models.DateField(
        db_index=True, help_text="Date when this rate becomes effective"
    )
    valid_until = models.DateField(
        null=True,
        blank=True,
        help_text="Date when this rate expires (null = indefinite)",
    )
    source = models.CharField(
        max_length=20,
        choices=ExchangeRateSource.choices,
        default=ExchangeRateSource.MANUAL,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "accounts.CustomUser",
        on_delete=models.SET_NULL,
        null=True,
        related_name="exchange_rates_created",
    )
    notes = models.TextField(blank=True)

    # Lock to prevent modification of historical rates
    is_locked = models.BooleanField(
        default=False, help_text="Locked rates cannot be modified"
    )

    class Meta:
        ordering = ["-effective_date", "base_currency", "quote_currency"]
        indexes = [
            models.Index(fields=["base_currency", "quote_currency", "effective_date"]),
            models.Index(fields=["effective_date", "valid_until"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(rate__gt=0), name="positive_exchange_rate"
            ),
            models.CheckConstraint(
                condition=models.Q(valid_until__gte=models.F("effective_date"))
                | models.Q(valid_until__isnull=True),
                name="valid_date_range",
            ),
            models.UniqueConstraint(
                fields=["base_currency", "quote_currency", "effective_date"],
                name="unique_rate_per_currency_pair_date",
            ),
        ]
        verbose_name = _("Exchange Rate")
        verbose_name_plural = _("Exchange Rates")

    def __str__(self):
        return f"1 {self.base_currency} = {self.rate} {self.quote_currency} (as of {self.effective_date})"

    def clean(self):
        """Validate exchange rate"""
        # Prevent same currency conversion
        if self.base_currency == self.quote_currency:
            raise ValidationError("Base and quote currencies must be different")

        # Prevent modification of locked rates
        if self.pk and self.is_locked:
            original = ExchangeRate.objects.get(pk=self.pk)
            if original.rate != self.rate:
                raise ValidationError("Locked exchange rates cannot be modified")

        # Check for overlapping rates
        if self.valid_until:
            overlapping = ExchangeRate.objects.filter(
                base_currency=self.base_currency,
                quote_currency=self.quote_currency,
                effective_date__lte=self.valid_until,
            ).filter(
                models.Q(valid_until__gte=self.effective_date)
                | models.Q(valid_until__isnull=True)
            )
            if self.pk:
                overlapping = overlapping.exclude(pk=self.pk)
            if overlapping.exists():
                raise ValidationError(
                    f"Date range overlaps with existing rate: {overlapping.first()}"
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def get_inverse_rate(self):
        """Get the inverse rate (for reverse conversion)"""
        if self.rate == 0:
            raise ValueError("Cannot calculate inverse of zero rate")
        return Decimal("1") / self.rate

    @classmethod
    def get_rate(cls, from_currency, to_currency, as_of_date=None):
        """
        Get exchange rate for converting from_currency to to_currency

        Args:
            from_currency: Source currency code
            to_currency: Target currency code
            as_of_date: Date for rate lookup (default: today)

        Returns:
            Decimal: Exchange rate or None if not found
        """
        if from_currency == to_currency:
            return Decimal("1")

        if as_of_date is None:
            as_of_date = timezone.now().date()

        # Try direct rate
        try:
            rate = (
                cls.objects.filter(
                    base_currency=from_currency,
                    quote_currency=to_currency,
                    effective_date__lte=as_of_date,
                )
                .filter(
                    models.Q(valid_until__gte=as_of_date)
                    | models.Q(valid_until__isnull=True)
                )
                .order_by("-effective_date")
                .first()
            )

            if rate:
                return rate.rate
        except cls.DoesNotExist:
            pass

        # Try inverse rate
        try:
            rate = (
                cls.objects.filter(
                    base_currency=to_currency,
                    quote_currency=from_currency,
                    effective_date__lte=as_of_date,
                )
                .filter(
                    models.Q(valid_until__gte=as_of_date)
                    | models.Q(valid_until__isnull=True)
                )
                .order_by("-effective_date")
                .first()
            )

            if rate:
                return rate.get_inverse_rate()
        except cls.DoesNotExist:
            pass

        return None

    @classmethod
    def convert_money(cls, amount, from_currency, to_currency, as_of_date=None):
        """
        Convert money from one currency to another

        Args:
            amount: Decimal amount to convert
            from_currency: Source currency code
            to_currency: Target currency code
            as_of_date: Date for rate lookup

        Returns:
            Decimal: Converted amount

        Raises:
            ValueError: If no exchange rate found
        """
        rate = cls.get_rate(from_currency, to_currency, as_of_date)
        if rate is None:
            raise ValueError(
                f"No exchange rate found for {from_currency} to {to_currency} "
                f"as of {as_of_date or 'today'}"
            )
        return amount * rate


class CurrencyConfiguration(models.Model):
    """
    Tenant-schema currency configuration (one per tenant schema).
    No cross-schema FK needed — isolation is handled by the schema itself.
    """

    base_currency = models.CharField(
        max_length=3, default="INR", help_text="Primary currency for this workspace"
    )
    enabled_currencies = models.JSONField(
        default=list, help_text="List of enabled currency codes ['INR', 'USD', 'EUR']"
    )
    auto_update_rates = models.BooleanField(
        default=False, help_text="Automatically fetch exchange rates from external API"
    )
    rate_update_frequency = models.CharField(
        max_length=20,
        choices=[
            ("DAILY", "Daily"),
            ("WEEKLY", "Weekly"),
            ("MANUAL", "Manual Only"),
        ],
        default="MANUAL",
    )
    last_rate_update = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("Currency Configuration")
        verbose_name_plural = _("Currency Configurations")

    def __str__(self):
        return f"Currency config - Base: {self.base_currency}"

    def get_enabled_currencies(self):
        """Get list of enabled currencies including base currency"""
        currencies = set(self.enabled_currencies or [])
        currencies.add(self.base_currency)
        return sorted(list(currencies))
