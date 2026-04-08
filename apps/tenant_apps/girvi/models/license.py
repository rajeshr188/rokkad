from datetime import timedelta
from decimal import Decimal
from django.db import models
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.shortcuts import reverse
from django.utils.translation import gettext_lazy as _
from django.utils import timezone


class License(models.Model):
    # License Type Choices
    LICENSE_TYPE_CHOICES = (
        ("PBL", "Pawn Brokers License"),
        ("GST", "Goods & Service Tax Registration"),
        ("IMPORT_EXPORT", "Import/Export License"),
        ("HALLMARK", "Hallmark Certificate"),
        ("FSSAI", "FSSAI Registration (Food)"),
        ("OTHER", "Other"),
    )

    # Business Type Choices
    BUSINESS_TYPE_CHOICES = (
        ("PAWNBROKER", "Pawnbroker Only"),
        ("JEWELLER", "Jeweller Only"),
        ("COMBINED", "Pawnbroker & Jeweller"),
        ("OTHER", "Other"),
    )

    # License Status Choices
    STATUS_CHOICES = (
        ("ACTIVE", "Active"),
        ("INACTIVE", "Inactive"),
        ("EXPIRED", "Expired"),
        ("SUSPENDED", "Suspended"),
        ("PENDING", "Pending Approval"),
        ("RENEWED", "Renewed"),
    )

    # Basic License Information
    name = models.CharField(
        max_length=255, verbose_name=_("License Name"), null=True, blank=True
    )
    license_number = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_("License Number"),
        help_text=_("Unique license identifier from authority"),
        null=True,
        blank=True,
    )
    type = models.CharField(
        max_length=30,
        choices=LICENSE_TYPE_CHOICES,
        default="PBL",
        verbose_name=_("License Type"),
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="ACTIVE",
        verbose_name=_("License Status"),
    )

    # Business Details
    shopname = models.CharField(
        max_length=100, verbose_name=_("Shop/Business Name"), null=True, blank=True
    )
    business_type = models.CharField(
        max_length=20,
        choices=BUSINESS_TYPE_CHOICES,
        default="COMBINED",
        verbose_name=_("Business Type"),
    )
    address = models.TextField(
        max_length=500, verbose_name=_("Business Address"), null=True, blank=True
    )
    city = models.CharField(max_length=100, blank=True, verbose_name=_("City"))
    state = models.CharField(max_length=100, blank=True, verbose_name=_("State"))
    postal_code = models.CharField(
        max_length=20, blank=True, verbose_name=_("Postal Code")
    )
    phonenumber = models.CharField(
        max_length=20, verbose_name=_("Phone Number"), null=True, blank=True
    )
    email = models.EmailField(
        blank=True, verbose_name=_("Email"), help_text=_("Business email")
    )
    propreitor = models.CharField(
        max_length=100, verbose_name=_("Proprietor/Owner Name"), null=True, blank=True
    )

    # License Authority & Dates
    issuing_authority = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_("Issuing Authority"),
        help_text=_("Authority that issued this license"),
    )
    date_issued = models.DateField(verbose_name=_("Date Issued"), null=True, blank=True)
    renewal_date = models.DateField(
        verbose_name=_("Renewal Date"), null=True, blank=True
    )
    date_expires = models.DateField(
        verbose_name=_("Expiry Date"), null=True, blank=True
    )
    is_renewable = models.BooleanField(default=True, verbose_name=_("Auto-renewable?"))

    # Metadata
    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)
    notes = models.TextField(blank=True, verbose_name=_("Additional Notes"))
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))

    class Meta:
        ordering = ("-created",)
        verbose_name = _("License")
        verbose_name_plural = _("Licenses")
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["type"]),
            models.Index(fields=["date_expires"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.license_number})"

    def get_absolute_url(self):
        return reverse("girvi:girvi_license_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("girvi:girvi_license_update", args=(self.pk,))

    # Status and Expiry Methods
    def is_expired(self):
        """Check if license is expired"""
        if self.date_expires:
            return timezone.now().date() > self.date_expires
        return False

    def is_expiring_soon(self, days=30):
        """Check if license is expiring within specified days"""
        if self.date_expires:
            today = timezone.now().date()
            threshold = today + timedelta(days=days)
            return today <= self.date_expires <= threshold
        return False

    def days_until_expiry(self):
        """Get number of days until license expires"""
        if self.date_expires:
            delta = self.date_expires - timezone.now().date()
            return delta.days
        return None

    def get_status_display_color(self):
        """Return Bootstrap color class for status badge"""
        color_map = {
            "ACTIVE": "success",
            "INACTIVE": "secondary",
            "EXPIRED": "danger",
            "SUSPENDED": "warning",
            "PENDING": "info",
            "RENEWED": "primary",
        }
        return color_map.get(self.status, "secondary")

    def auto_update_status(self):
        """Automatically update status based on expiry date"""
        if self.date_expires:
            if self.is_expired():
                if self.status != "EXPIRED":
                    self.status = "EXPIRED"
                    self.save(update_fields=["status"])
            elif self.is_expiring_soon(days=30):
                # Could trigger notification here
                pass

    def renew_license(self, new_expiry_date, renewal_notes=""):
        """Handle license renewal"""
        old_expiry = self.date_expires
        self.date_expires = new_expiry_date
        self.status = "RENEWED"
        self.renewal_date = timezone.now().date()
        if renewal_notes:
            self.notes += f"\n[{timezone.now().isoformat()}] Renewal: {renewal_notes}"
        self.save()
        return {
            "old_expiry": old_expiry,
            "new_expiry": new_expiry_date,
            "renewed_on": self.renewal_date,
        }

    def get_linked_licenses(self):
        """Get other licenses linked to same business"""
        return License.objects.filter(shopname=self.shopname).exclude(pk=self.pk)

    def get_document_count(self):
        """Get count of documents attached to this license"""
        return self.documents.filter(is_active=True).count()

    def get_documents(self):
        """Get all active documents for this license"""
        return self.documents.filter(is_active=True)

    def get_series_count(self):
        return self.series_set.count()

    def get_unreleased_loan_data(self):
        series_data = []
        total_unreleased_loans = 0
        total_loan_amount = 0

        for series in self.series_set.all():
            # Use GivenLoan for refactored model
            from .loan_refactored import GivenLoan

            unreleased_loans = GivenLoan.objects.filter(series=series).unreleased()
            loan_count = unreleased_loans.count()
            # Get loan amounts from LoanItem related to GivenLoan
            loan_amount = unreleased_loans.values_list("id", flat=True).query
            from .loan_item import LoanItem

            loan_amount = (
                LoanItem.objects.filter(loan_id__in=loan_amount).aggregate(
                    total=Sum("loanamount")
                )["total"]
                or 0
            )

            series_data.append(
                {
                    "series_name": series.name,
                    "loan_count": loan_count,
                    "loan_amount": loan_amount,
                }
            )

            total_unreleased_loans += loan_count
            total_loan_amount += loan_amount

        return {
            "license_name": self.name,
            "total_unreleased_loans": total_unreleased_loans,
            "total_loan_amount": total_loan_amount,
            "series_data": series_data,
        }

    def create_series(self, name, prefix):
        """Create a new series under this license"""
        return Series.objects.create(license=self, name=name, prefix=prefix.upper())


class LicenseDocument(models.Model):
    """Model to store license-related documents and certificates"""

    DOCUMENT_TYPE_CHOICES = (
        ("CERTIFICATE", "License Certificate"),
        ("APPROVAL_LETTER", "Approval Letter"),
        ("RENEWAL_NOTICE", "Renewal Notice"),
        ("INSPECTION_REPORT", "Inspection Report"),
        ("COMPLIANCE_DOC", "Compliance Document"),
        ("OTHER", "Other Document"),
    )

    license = models.ForeignKey(
        License,
        on_delete=models.CASCADE,
        related_name="documents",
        verbose_name=_("License"),
    )
    document_type = models.CharField(
        max_length=20,
        choices=DOCUMENT_TYPE_CHOICES,
        default="CERTIFICATE",
        verbose_name=_("Document Type"),
    )
    title = models.CharField(max_length=255, verbose_name=_("Document Title"))
    description = models.TextField(blank=True, verbose_name=_("Description"))
    document_file = models.FileField(
        upload_to="license_documents/%Y/%m/",
        verbose_name=_("Document File"),
    )
    file_size = models.IntegerField(
        editable=False, help_text=_("File size in bytes"), null=True, blank=True
    )
    file_type = models.CharField(max_length=50, editable=False, null=True, blank=True)

    # Document Metadata
    upload_date = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        "accounts.CustomUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Uploaded By"),
    )
    expiry_date = models.DateField(
        null=True, blank=True, verbose_name=_("Document Expiry Date")
    )
    is_verified = models.BooleanField(default=False, verbose_name=_("Verified?"))
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))

    class Meta:
        ordering = ["-upload_date"]
        verbose_name = _("License Document")
        verbose_name_plural = _("License Documents")
        indexes = [
            models.Index(fields=["license", "is_active"]),
            models.Index(fields=["document_type"]),
        ]

    def __str__(self):
        return f"{self.title} - {self.get_document_type_display()}"

    def save(self, *args, **kwargs):
        """Store file metadata on save"""
        if self.document_file:
            self.file_size = self.document_file.size
            self.file_type = self.document_file.name.split(".")[-1].upper()
        super().save(*args, **kwargs)

    def is_document_expired(self):
        """Check if document is expired"""
        if self.expiry_date:
            return timezone.now().date() > self.expiry_date
        return False

    def get_document_url(self):
        """Get URL to download document"""
        if self.document_file:
            return self.document_file.url
        return None


class SeriesManager(models.Manager):
    """Custom manager for Series with guardrail-aware filtering"""
    
    def active_for_loans(self):
        """Get active series that allow new loan creation"""
        return self.filter(
            is_active=True,
            deactivated_for_loans=False
        )
    
    def active_for_releases(self):
        """Get active series that allow new release creation"""
        return self.filter(
            is_active=True,
            deactivated_for_releases=False
        )
    
    def active_for_both(self):
        """Get active series that allow both loans and releases"""
        return self.filter(
            is_active=True,
            deactivated_for_loans=False,
            deactivated_for_releases=False
        )


class Series(models.Model):
    license = models.ForeignKey(
        License, on_delete=models.CASCADE, verbose_name=_("License")
    )
    name = models.CharField(
        max_length=30,
        default="",
        blank=True,
        verbose_name=_("Series Name/prefix"),
    )
    prefix = models.CharField(
        max_length=3,
        help_text="Prefix for loan IDs in this series",
        default="Z",
        # unique=True,default="Z",
    )
    max_limit = models.PositiveIntegerField(
        default=5,
        help_text="Number of digits in loan ID sequence",
        verbose_name=_("Max Limit"),
    )
    created = models.DateTimeField(auto_now_add=True, editable=False)
    last_updated = models.DateTimeField(auto_now=True)

    class LoanType(models.TextChoices):
        TAKEN = "Taken", "Taken"
        GIVEN = "Given", "Given"

    loan_type = models.CharField(
        max_length=10,
        choices=LoanType.choices,
        default=LoanType.GIVEN,
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))
    
    # Guardrail Fields
    class DeactivationRule(models.TextChoices):
        NONE = "NONE", "No Deactivation"
        LOANS_ONLY = "LOANS", "Disable Loans Only"
        RELEASES_ONLY = "RELEASES", "Disable Releases Only"
        BOTH = "BOTH", "Disable Loans & Releases"
    
    # Threshold configuration
    loan_count_threshold = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Loan Count Threshold"),
        help_text="Max number of active loans allowed in this series. Leave blank for unlimited.",
    )
    loan_amount_threshold = models.DecimalField(
        null=True,
        blank=True,
        max_digits=15,
        decimal_places=2,
        verbose_name=_("Loan Amount Threshold (₹)"),
        help_text="Max total loan amount allowed in this series. Leave blank for unlimited.",
    )
    deactivation_rule = models.CharField(
        max_length=10,
        choices=DeactivationRule.choices,
        default=DeactivationRule.NONE,
        verbose_name=_("Deactivation Rule"),
        help_text="What to disable when threshold is exceeded",
    )
    
    # Deactivation status tracking
    deactivated_for_loans = models.BooleanField(
        default=False,
        verbose_name=_("Deactivated for Loans"),
        help_text="Series cannot create new loans",
    )
    deactivated_for_releases = models.BooleanField(
        default=False,
        verbose_name=_("Deactivated for Releases"),
        help_text="Series cannot create new releases",
    )
    deactivation_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Deactivation Date"),
        help_text="When the series was deactivated due to threshold breach",
    )
    threshold_exceeded_reason = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Threshold Exceeded Reason"),
        help_text="Which threshold was exceeded and triggered deactivation",
    )

    # Add custom manager
    objects = SeriesManager()

    class Meta:
        ordering = ("created",)
        unique_together = ["license", "name"]
        indexes = [
            models.Index(fields=["is_active", "deactivated_for_loans"]),
            models.Index(fields=["is_active", "deactivated_for_releases"]),
        ]

    def __str__(self):
        return f"{self.prefix}-{self.name}"

    def get_absolute_url(self):
        return reverse("girvi:girvi_license_series_detail", args=(self.pk,))


    def get_update_url(self):
        return reverse("girvi:girvi_license_series_update", args=(self.pk,))

    def _base_loans_queryset(self):
        """Prefer refactored GivenLoan relation; fall back to legacy Loan relation."""
        if hasattr(self, "given_loans"):
            return self.given_loans.all()
        if hasattr(self, "loan_set"):
            return self.loan_set.all()
        from .loan_refactored import GivenLoan

        return GivenLoan.objects.filter(series=self)

    def _active_loans_queryset(self):
        """Return currently active/unreleased loans for this series."""
        queryset = self._base_loans_queryset()
        if hasattr(queryset, "unreleased"):
            return queryset.unreleased()
        return queryset.exclude(status="Released")

    def get_earliest_date(self):
        earliest_loan_date = self._base_loans_queryset().aggregate(models.Min("loan_date"))[ 
            "loan_date__min"
        ]
        return earliest_loan_date

    def get_latest_date(self):
        latest_loan_date = self._base_loans_queryset().aggregate(models.Max("loan_date"))[ 
            "loan_date__max"
        ]
        return latest_loan_date

    def activate(self):
        self.is_active = not self.is_active
        self.save(update_fields=["is_active"])

    # ========================================================================
    # Guardrail Methods - Threshold Checking & Deactivation Logic
    # ========================================================================

    def get_current_loan_count(self):
        """Get count of active (unreleased) loans in this series"""
        return self._active_loans_queryset().count()

    def get_current_loan_amount(self):
        """Get total amount of active (unreleased) loans in this series"""
        unreleased_loans = self._active_loans_queryset()
        if hasattr(unreleased_loans, "total_loan_amount"):
            return unreleased_loans.total_loan_amount() or Decimal("0")

        result = unreleased_loans.aggregate(total=Coalesce(Sum("loan_amount"), Decimal("0")))
        return result.get("total", Decimal("0"))

    def is_loan_count_exceeded(self) -> bool:
        """Check if loan count threshold has been exceeded"""
        if not self.loan_count_threshold:
            return False
        return self.get_current_loan_count() >= self.loan_count_threshold

    def is_loan_amount_exceeded(self) -> bool:
        """Check if loan amount threshold has been exceeded"""
        if not self.loan_amount_threshold:
            return False
        return self.get_current_loan_amount() >= self.loan_amount_threshold

    def is_any_threshold_exceeded(self) -> bool:
        """Check if any configured threshold has been exceeded"""
        return self.is_loan_count_exceeded() or self.is_loan_amount_exceeded()

    def can_create_loan(self) -> bool:
        """Check if new loans can be created in this series"""
        if not self.is_active:
            return False
        if self.deactivated_for_loans:
            return False
        # Check thresholds and apply deactivation if needed
        if self.is_any_threshold_exceeded():
            if self.deactivation_rule in [
                self.DeactivationRule.LOANS_ONLY,
                self.DeactivationRule.BOTH
            ]:
                return False
        return True

    def can_create_release(self) -> bool:
        """Check if new releases can be created from loans in this series"""
        if not self.is_active:
            return False
        if self.deactivated_for_releases:
            return False
        # Check thresholds and apply deactivation if needed
        if self.is_any_threshold_exceeded():
            if self.deactivation_rule in [
                self.DeactivationRule.RELEASES_ONLY,
                self.DeactivationRule.BOTH
            ]:
                return False
        return True

    def check_and_apply_deactivation(self):
        """
        Check thresholds and apply deactivation rules automatically.
        This should be called after loan creation or updates.
        
        Returns:
            tuple: (was_deactivated: bool, reason: str)
        """
        if not self.deactivation_rule or self.deactivation_rule == self.DeactivationRule.NONE:
            return False, ""
        
        if not self.is_any_threshold_exceeded():
            return False, ""
        
        reason_parts = []
        
        # Build reason message
        if self.is_loan_count_exceeded():
            reason_parts.append(
                f"Loan count ({self.get_current_loan_count()}) "
                f"reached threshold ({self.loan_count_threshold})"
            )
        
        if self.is_loan_amount_exceeded():
            reason_parts.append(
                f"Loan amount (₹{self.get_current_loan_amount()}) "
                f"reached threshold (₹{self.loan_amount_threshold})"
            )
        
        reason = " | ".join(reason_parts)
        
        # Apply deactivation based on rule
        was_updated = False
        if self.deactivation_rule in [self.DeactivationRule.LOANS_ONLY, self.DeactivationRule.BOTH]:
            if not self.deactivated_for_loans:
                self.deactivated_for_loans = True
                self.deactivation_date = timezone.now()
                self.threshold_exceeded_reason = reason
                was_updated = True
        
        if self.deactivation_rule == self.DeactivationRule.RELEASES_ONLY:
            if not self.deactivated_for_releases:
                self.deactivated_for_releases = True
                self.deactivation_date = timezone.now()
                self.threshold_exceeded_reason = reason
                was_updated = True
        
        if self.deactivation_rule == self.DeactivationRule.BOTH:
            if not self.deactivated_for_releases:
                self.deactivated_for_releases = True
                was_updated = True
        
        if was_updated:
            self.save(update_fields=[
                "deactivated_for_loans",
                "deactivated_for_releases",
                "deactivation_date",
                "threshold_exceeded_reason"
            ])
            return True, reason
        
        return False, reason

    def get_guardrail_status(self) -> dict:
        """
        Get detailed status of guardrails and thresholds for this series.
        Useful for admin/monitoring interfaces.
        """
        return {
            "series_id": self.pk,
            "series_name": str(self),
            "is_active": self.is_active,
            "deactivation_rule": self.deactivation_rule,
            "deactivated_for_loans": self.deactivated_for_loans,
            "deactivated_for_releases": self.deactivated_for_releases,
            "deactivation_date": self.deactivation_date,
            "reason": self.threshold_exceeded_reason,
            "loan_count_threshold": self.loan_count_threshold,
            "loan_amount_threshold": self.loan_amount_threshold,
            "current_loan_count": self.get_current_loan_count(),
            "current_loan_amount": float(self.get_current_loan_amount()),
            "is_loan_count_exceeded": self.is_loan_count_exceeded(),
            "is_loan_amount_exceeded": self.is_loan_amount_exceeded(),
            "can_create_loan": self.can_create_loan(),
            "can_create_release": self.can_create_release(),
        }


    def loan_count(self):
        return self._active_loans_queryset().count()

    def total_loan_amount(self):
        unreleased_loans = self._active_loans_queryset()
        if hasattr(unreleased_loans, "total_loan_amount"):
            return {"t": unreleased_loans.total_loan_amount() or Decimal("0")}
        return unreleased_loans.aggregate(t=Coalesce(Sum("loan_amount"), Decimal("0")))

    def get_itemwise_loanamount(self):
        return (
            self._active_loans_queryset()
            .for_table_display()
            .with_itemwise_amounts()
            .total_itemwise_loanamount()
        )

    def get_itemwise_pure_weight(self):
        return self._active_loans_queryset().for_table_display().total_pure_weight()

    def get_unreleased_loan_data(self):
        unreleased_loans = self._active_loans_queryset()
        loan_count = unreleased_loans.count()
        if hasattr(unreleased_loans, "total_loan_amount"):
            loan_amount = unreleased_loans.total_loan_amount() or 0
        else:
            loan_amount = unreleased_loans.aggregate(total=Sum("loan_amount"))["total"] or 0

        return {
            "series_name": self.name,
            "loan_count": loan_count,
            "loan_amount": loan_amount,
        }

    def get_next_loan_id(self):
        """
        Get next loan sequence number for this series.
        Returns: integer (just the sequence number, not formatted)

        Note: This is used internally. Use format_loan_id() to get the formatted string.
        Thread-safe using select_for_update within LoanIDGenerator.
        """
        # Get last loan in this series
        last_loan = self._base_loans_queryset().order_by("-loan_id").first()

        if last_loan:
            # Extract number from formatted ID (e.g., "A00123" -> 123)
            try:
                return int(last_loan.loan_id[len(self.prefix) :]) + 1
            except (ValueError, IndexError):
                return 1
        else:
            return 1

    def format_loan_id(self, loan_id_number: int) -> str:
        """
        Format a loan ID number with series prefix and padding.
        Args:
            loan_id_number: The sequence number
        Returns:
            Formatted string like 'A00001'
        """
        return f"{self.prefix}{loan_id_number:0{self.max_limit}d}"
