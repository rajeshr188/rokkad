from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection, models
from django.db.models import F, Q
from django.utils import timezone

from apps.tenant_apps.loans.domain import (
    AccountingRecognition,
    CollateralCustodyState,
    CollateralMetal,
    DisbursalPolicySnapshot,
    InterestMethod,
    LoanDocumentKind,
    PartialMonthMethod,
    PawnLoanEventKind,
    PawnLoanState,
    RoundingMethod,
    ValuationMethod,
)


def enum_choices(enum_class):
    return tuple((member.value, member.name.replace("_", " ").title()) for member in enum_class)


def current_tenant_workspace_id():
    tenant = getattr(connection, "tenant", None)
    if tenant is None or getattr(connection, "schema_name", "public") == "public":
        return None
    return getattr(tenant, "pk", None)


class LoanLicense(models.Model):
    workspace = models.ForeignKey(
        "orgs.Company",
        on_delete=models.PROTECT,
        related_name="loan_licenses",
    )
    name = models.CharField(max_length=255)
    license_number = models.CharField(max_length=100)
    issuing_authority = models.CharField(max_length=255, blank=True)
    issued_on = models.DateField()
    expires_on = models.DateField()
    is_active = models.BooleanField(default=True, db_index=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="loan_licenses_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="loan_licenses_updated",
    )

    class Meta:
        ordering = ("workspace_id", "license_number")
        constraints = [
            models.UniqueConstraint(
                fields=("workspace", "license_number"),
                name="loans_license_workspace_number_uniq",
            ),
            models.CheckConstraint(
                condition=Q(expires_on__gte=F("issued_on")),
                name="loans_license_dates_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=("workspace", "is_active", "expires_on"),
                name="loans_license_ready_idx",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.license_number})"

    def clean(self):
        super().clean()
        tenant_workspace_id = current_tenant_workspace_id()
        if tenant_workspace_id and self.workspace_id != tenant_workspace_id:
            raise ValidationError(
                {"workspace": "License workspace must match the active tenant."}
            )

    def save(self, *args, **kwargs):
        self.clean()
        return super().save(*args, **kwargs)

    def is_expired(self, as_of_date=None):
        return self.expires_on < (as_of_date or timezone.localdate())


class LoanSeries(models.Model):
    license = models.ForeignKey(
        LoanLicense,
        on_delete=models.PROTECT,
        related_name="series",
    )
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=32)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("license_id", "code")
        constraints = [
            models.UniqueConstraint(
                fields=("license", "code"),
                name="loans_series_license_code_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=("license", "is_active"),
                name="loans_series_active_idx",
            ),
        ]

    @property
    def workspace_id(self):
        return self.license.workspace_id

    def __str__(self):
        return f"{self.license.license_number}/{self.code}"


class LoanNumberSequence(models.Model):
    series = models.ForeignKey(
        LoanSeries,
        on_delete=models.PROTECT,
        related_name="number_sequences",
    )
    document_kind = models.CharField(
        max_length=32,
        choices=enum_choices(LoanDocumentKind),
    )
    prefix = models.CharField(max_length=24)
    width = models.PositiveSmallIntegerField(default=5)
    next_number = models.PositiveBigIntegerField(default=1)
    maximum_number = models.PositiveBigIntegerField(default=10000)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="loan_number_sequences_updated",
    )

    class Meta:
        ordering = ("series_id", "document_kind")
        constraints = [
            models.UniqueConstraint(
                fields=("series", "document_kind"),
                name="loans_sequence_series_kind_uniq",
            ),
            models.CheckConstraint(
                condition=Q(width__gt=0),
                name="loans_sequence_width_positive",
            ),
            models.CheckConstraint(
                condition=Q(next_number__gt=0),
                name="loans_sequence_next_positive",
            ),
            models.CheckConstraint(
                condition=Q(maximum_number__gt=0),
                name="loans_sequence_max_positive",
            ),
        ]
        indexes = [
            models.Index(
                fields=("document_kind", "is_active"),
                name="loans_sequence_kind_idx",
            ),
        ]

    def clean(self):
        super().clean()
        if self.next_number > self.maximum_number + 1:
            raise ValidationError(
                {
                    "next_number": (
                        "Next number cannot exceed the exhausted marker immediately "
                        "after the sequence maximum."
                    )
                }
            )

    def save(self, *args, **kwargs):
        self.clean()
        return super().save(*args, **kwargs)


class PawnLoan(models.Model):
    workspace = models.ForeignKey(
        "orgs.Company",
        on_delete=models.PROTECT,
        related_name="pawn_loans",
    )
    license = models.ForeignKey(
        LoanLicense,
        on_delete=models.PROTECT,
        related_name="pawn_loans",
    )
    series = models.ForeignKey(
        LoanSeries,
        on_delete=models.PROTECT,
        related_name="pawn_loans",
    )
    borrower = models.ForeignKey(
        "party.Party",
        on_delete=models.PROTECT,
        related_name="pawn_loans",
    )
    loan_number = models.CharField(max_length=64)
    state = models.CharField(
        max_length=16,
        choices=enum_choices(PawnLoanState),
        default=PawnLoanState.DRAFT.value,
        db_index=True,
    )
    principal_amount = models.DecimalField(max_digits=18, decimal_places=2)
    monthly_interest_rate = models.DecimalField(max_digits=9, decimal_places=6)
    loan_date = models.DateField(default=timezone.localdate, db_index=True)
    tenure_months = models.PositiveIntegerField(default=3)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pawn_loans_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pawn_loans_updated",
    )

    class Meta:
        ordering = ("loan_date", "loan_number")
        constraints = [
            models.UniqueConstraint(
                fields=("workspace", "loan_number"),
                name="loans_pawn_workspace_number_uniq",
            ),
            models.CheckConstraint(
                condition=Q(principal_amount__gt=0),
                name="loans_pawn_principal_positive",
            ),
            models.CheckConstraint(
                condition=Q(monthly_interest_rate__gte=0),
                name="loans_pawn_rate_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(tenure_months__gt=0),
                name="loans_pawn_tenure_positive",
            ),
        ]
        indexes = [
            models.Index(
                fields=("workspace", "state", "loan_date"),
                name="loans_pawn_state_date_idx",
            ),
            models.Index(
                fields=("borrower", "state"),
                name="loans_pawn_party_state_idx",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        tenant_workspace_id = current_tenant_workspace_id()
        if tenant_workspace_id and self.workspace_id != tenant_workspace_id:
            errors["workspace"] = "Loan workspace must match the active tenant."
        if self.license_id and self.workspace_id:
            license_workspace_id = self.license.workspace_id
            if license_workspace_id != self.workspace_id:
                errors["license"] = "License must belong to the loan workspace."
        if self.series_id and self.license_id:
            series_license_id = self.series.license_id
            if series_license_id != self.license_id:
                errors["series"] = "Series must belong to the selected license."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.loan_number


class PawnCollateralItem(models.Model):
    loan = models.ForeignKey(
        PawnLoan,
        on_delete=models.PROTECT,
        related_name="collateral_items",
    )
    description = models.CharField(max_length=255)
    metal = models.CharField(max_length=16, choices=enum_choices(CollateralMetal))
    gross_weight = models.DecimalField(max_digits=14, decimal_places=4)
    net_weight = models.DecimalField(max_digits=14, decimal_places=4)
    purity_percentage = models.DecimalField(max_digits=7, decimal_places=4)
    latest_appraised_value = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True,
    )
    custody_state = models.CharField(
        max_length=32,
        choices=enum_choices(CollateralCustodyState),
        default=CollateralCustodyState.IN_VAULT.value,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("loan_id", "id")
        constraints = [
            models.CheckConstraint(
                condition=Q(gross_weight__gt=0),
                name="loans_item_gross_positive",
            ),
            models.CheckConstraint(
                condition=Q(net_weight__gt=0),
                name="loans_item_net_positive",
            ),
            models.CheckConstraint(
                condition=Q(gross_weight__gte=F("net_weight")),
                name="loans_item_gross_gte_net",
            ),
            models.CheckConstraint(
                condition=Q(purity_percentage__gt=0)
                & Q(purity_percentage__lte=100),
                name="loans_item_purity_range",
            ),
            models.CheckConstraint(
                condition=Q(latest_appraised_value__isnull=True)
                | Q(latest_appraised_value__gt=0),
                name="loans_item_appraisal_positive",
            ),
        ]
        indexes = [
            models.Index(
                fields=("loan", "custody_state"),
                name="loans_item_custody_idx",
            ),
        ]


class LoanPolicySnapshot(models.Model):
    loan = models.OneToOneField(
        PawnLoan,
        on_delete=models.PROTECT,
        related_name="policy_snapshot",
    )
    policy_version = models.PositiveSmallIntegerField(default=1)
    interest_method = models.CharField(
        max_length=16,
        choices=enum_choices(InterestMethod),
    )
    partial_month_method = models.CharField(
        max_length=16,
        choices=enum_choices(PartialMonthMethod),
    )
    partial_month_cutoff_days = models.PositiveSmallIntegerField(default=15)
    partial_month_lower_fraction = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal("0.5"),
    )
    capitalization_interval_periods = models.PositiveSmallIntegerField(default=12)
    accounting_recognition = models.CharField(
        max_length=16,
        choices=enum_choices(AccountingRecognition),
    )
    valuation_method = models.CharField(
        max_length=48,
        choices=enum_choices(ValuationMethod),
    )
    maximum_ltv_ratio = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal("0.80"),
    )
    rounding_method = models.CharField(
        max_length=32,
        choices=enum_choices(RoundingMethod),
    )
    currency_quantum = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        default=Decimal("0.01"),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(policy_version__gt=0),
                name="loans_policy_version_positive",
            ),
            models.CheckConstraint(
                condition=Q(maximum_ltv_ratio__gt=0)
                & Q(maximum_ltv_ratio__lte=1),
                name="loans_policy_ltv_range",
            ),
        ]

    def clean(self):
        super().clean()
        try:
            DisbursalPolicySnapshot(
                policy_version=self.policy_version,
                interest_method=InterestMethod(self.interest_method),
                partial_month_method=PartialMonthMethod(self.partial_month_method),
                partial_month_cutoff_days=self.partial_month_cutoff_days,
                partial_month_lower_fraction=self.partial_month_lower_fraction,
                capitalization_interval_periods=self.capitalization_interval_periods,
                accounting_recognition=AccountingRecognition(
                    self.accounting_recognition
                ),
                valuation_method=ValuationMethod(self.valuation_method),
                maximum_ltv_ratio=self.maximum_ltv_ratio,
                rounding_method=RoundingMethod(self.rounding_method),
                currency_quantum=self.currency_quantum,
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

    def save(self, *args, **kwargs):
        self.clean()
        return super().save(*args, **kwargs)


class LoanChangeLog(models.Model):
    loan = models.ForeignKey(
        PawnLoan,
        on_delete=models.PROTECT,
        related_name="change_log",
    )
    event_kind = models.CharField(
        max_length=40,
        choices=enum_choices(PawnLoanEventKind),
    )
    from_state = models.CharField(
        max_length=16,
        choices=enum_choices(PawnLoanState),
        blank=True,
    )
    to_state = models.CharField(
        max_length=16,
        choices=enum_choices(PawnLoanState),
        blank=True,
    )
    reason = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pawn_loan_changes",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("loan_id", "created_at", "id")
        indexes = [
            models.Index(
                fields=("loan", "event_kind", "created_at"),
                name="loans_change_event_idx",
            ),
        ]
