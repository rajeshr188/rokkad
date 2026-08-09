from decimal import Decimal
import uuid

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
    FeeCalculationType,
    InterestMethod,
    LoanDocumentKind,
    LoanOutboxStatus,
    PartialMonthMethod,
    PawnLoanNoticeChannel,
    PawnLoanNoticeKind,
    PawnLoanAuctionState,
    PawnLoanRenewalMode,
    PawnLoanEventKind,
    PawnLoanState,
    RoundingMethod,
    TransactionKind,
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


class PawnLoanEconomicPolicy(models.Model):
    workspace = models.ForeignKey(
        "orgs.Company",
        on_delete=models.PROTECT,
        related_name="pawn_loan_economic_policies",
    )
    license = models.ForeignKey(
        LoanLicense,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="economic_policies",
    )
    valuation_method = models.CharField(
        max_length=40,
        choices=enum_choices(ValuationMethod),
        default=ValuationMethod.LOWER_OF_CALCULATED_AND_APPRAISAL.value,
    )
    maximum_ltv_ratio = models.DecimalField(
        max_digits=7,
        decimal_places=6,
        default=Decimal("0.800000"),
    )
    advance_interest_periods = models.PositiveSmallIntegerField(default=1)
    effective_from = models.DateField(default=timezone.localdate, db_index=True)
    effective_until = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pawn_loan_economic_policies_created",
    )

    class Meta:
        ordering = ("workspace_id", "license_id", "-effective_from", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("workspace", "effective_from"),
                condition=Q(license__isnull=True),
                name="loans_econ_ws_date_uniq",
            ),
            models.UniqueConstraint(
                fields=("license", "effective_from"),
                condition=Q(license__isnull=False),
                name="loans_econ_license_date_uniq",
            ),
            models.CheckConstraint(
                condition=Q(maximum_ltv_ratio__gt=0)
                & Q(maximum_ltv_ratio__lte=1),
                name="loans_econ_ltv_range",
            ),
            models.CheckConstraint(
                condition=Q(advance_interest_periods__lte=12),
                name="loans_econ_advance_range",
            ),
            models.CheckConstraint(
                condition=Q(effective_until__isnull=True)
                | Q(effective_until__gte=F("effective_from")),
                name="loans_econ_dates_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=("workspace", "license", "is_active", "effective_from"),
                name="loans_econ_resolve_idx",
            ),
        ]

    def clean(self):
        super().clean()
        _validate_policy_scope(self, label="Economic policy")

    def save(self, *args, **kwargs):
        self.clean()
        return super().save(*args, **kwargs)


class PawnMetalInterestRatePolicy(models.Model):
    workspace = models.ForeignKey(
        "orgs.Company",
        on_delete=models.PROTECT,
        related_name="pawn_metal_interest_rate_policies",
    )
    license = models.ForeignKey(
        LoanLicense,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="metal_interest_rate_policies",
    )
    metal = models.CharField(max_length=16, choices=enum_choices(CollateralMetal))
    monthly_interest_rate = models.DecimalField(max_digits=9, decimal_places=6)
    effective_from = models.DateField(default=timezone.localdate, db_index=True)
    effective_until = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pawn_metal_interest_rate_policies_created",
    )

    class Meta:
        ordering = ("workspace_id", "license_id", "metal", "-effective_from", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("workspace", "metal", "effective_from"),
                condition=Q(license__isnull=True),
                name="loans_rate_ws_metal_date_uniq",
            ),
            models.UniqueConstraint(
                fields=("license", "metal", "effective_from"),
                condition=Q(license__isnull=False),
                name="loans_rate_license_date_uniq",
            ),
            models.CheckConstraint(
                condition=Q(monthly_interest_rate__gte=0)
                & Q(monthly_interest_rate__lte=100),
                name="loans_rate_percent_range",
            ),
            models.CheckConstraint(
                condition=Q(effective_until__isnull=True)
                | Q(effective_until__gte=F("effective_from")),
                name="loans_rate_dates_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=("workspace", "license", "metal", "is_active", "effective_from"),
                name="loans_rate_resolve_idx",
            ),
        ]

    def clean(self):
        super().clean()
        _validate_policy_scope(self, label="Metal interest-rate policy")

    def save(self, *args, **kwargs):
        self.clean()
        return super().save(*args, **kwargs)


class PawnLoanFeePolicy(models.Model):
    workspace = models.ForeignKey(
        "orgs.Company",
        on_delete=models.PROTECT,
        related_name="pawn_loan_fee_policies",
    )
    license = models.ForeignKey(
        LoanLicense,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="fee_policies",
    )
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=100)
    calculation_type = models.CharField(
        max_length=16,
        choices=enum_choices(FeeCalculationType),
    )
    value = models.DecimalField(max_digits=18, decimal_places=6)
    deducted_at_disbursal = models.BooleanField(default=True)
    effective_from = models.DateField(default=timezone.localdate, db_index=True)
    effective_until = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pawn_loan_fee_policies_created",
    )

    class Meta:
        ordering = ("workspace_id", "license_id", "code", "-effective_from", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("workspace", "code", "effective_from"),
                condition=Q(license__isnull=True),
                name="loans_fee_ws_code_date_uniq",
            ),
            models.UniqueConstraint(
                fields=("license", "code", "effective_from"),
                condition=Q(license__isnull=False),
                name="loans_fee_license_date_uniq",
            ),
            models.CheckConstraint(
                condition=Q(value__gte=0),
                name="loans_fee_value_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(effective_until__isnull=True)
                | Q(effective_until__gte=F("effective_from")),
                name="loans_fee_dates_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=("workspace", "license", "code", "is_active", "effective_from"),
                name="loans_fee_resolve_idx",
            ),
        ]

    def clean(self):
        super().clean()
        _validate_policy_scope(self, label="Fee policy")
        if (
            self.calculation_type == FeeCalculationType.PERCENTAGE.value
            and self.value is not None
            and self.value > Decimal("100")
        ):
            raise ValidationError({"value": "Percentage fees cannot exceed 100%."})

    def save(self, *args, **kwargs):
        self.clean()
        return super().save(*args, **kwargs)


def _validate_policy_scope(policy, *, label):
    errors = {}
    tenant_workspace_id = current_tenant_workspace_id()
    if tenant_workspace_id and policy.workspace_id != tenant_workspace_id:
        errors["workspace"] = f"{label} workspace must match the active tenant."
    if policy.license_id and policy.workspace_id:
        if policy.license.workspace_id != policy.workspace_id:
            errors["license"] = f"{label} license must belong to its workspace."
    if (
        policy.effective_until
        and policy.effective_from
        and policy.effective_until < policy.effective_from
    ):
        errors["effective_until"] = "Effective-until cannot precede effective-from."
    if errors:
        raise ValidationError(errors)


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
    license_revision = models.ForeignKey(
        "loans.LoanLicenseRevision",
        null=True,
        blank=True,
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
        if self.license_revision_id and self.license_id:
            if self.license_revision.license_id != self.license_id:
                errors["license_revision"] = (
                    "License revision must belong to the selected license."
                )
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.loan_number


class PawnCollateralItem(models.Model):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
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
    allocated_principal = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True,
    )
    monthly_interest_rate = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )
    interest_rate_policy = models.ForeignKey(
        PawnMetalInterestRatePolicy,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="collateral_items",
    )
    custody_state = models.CharField(
        max_length=32,
        choices=enum_choices(CollateralCustodyState),
        default=CollateralCustodyState.IN_VAULT.value,
        db_index=True,
    )
    renewed_from = models.OneToOneField(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="renewed_as",
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
            models.CheckConstraint(
                condition=Q(allocated_principal__isnull=True)
                | Q(allocated_principal__gt=0),
                name="loans_item_allocation_positive",
            ),
            models.CheckConstraint(
                condition=Q(monthly_interest_rate__isnull=True)
                | (
                    Q(monthly_interest_rate__gte=0)
                    & Q(monthly_interest_rate__lte=100)
                ),
                name="loans_item_rate_range",
            ),
        ]
        indexes = [
            models.Index(
                fields=("loan", "custody_state"),
                name="loans_item_custody_idx",
            ),
        ]

    def clean(self):
        super().clean()
        if self.interest_rate_policy_id and self.loan_id:
            policy = self.interest_rate_policy
            if policy.workspace_id != self.loan.workspace_id:
                raise ValidationError(
                    {"interest_rate_policy": "Rate policy must belong to the loan workspace."}
                )
            if policy.metal != self.metal:
                raise ValidationError(
                    {"interest_rate_policy": "Rate policy metal must match the collateral metal."}
                )
            if policy.license_id and policy.license_id != self.loan.license_id:
                raise ValidationError(
                    {
                        "interest_rate_policy": (
                            "A license-specific rate policy must match the loan license."
                        )
                    }
                )

    def save(self, *args, **kwargs):
        self.clean()
        return super().save(*args, **kwargs)


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


class PawnLoanApprovalSnapshot(models.Model):
    loan = models.ForeignKey(
        PawnLoan,
        on_delete=models.PROTECT,
        related_name="approval_snapshots",
    )
    version = models.PositiveIntegerField()
    payload = models.JSONField()
    fingerprint = models.CharField(max_length=64)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pawn_loan_approvals",
    )
    approved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("loan_id", "version")
        constraints = [
            models.UniqueConstraint(
                fields=("loan", "version"),
                name="loans_approval_loan_version_uniq",
            ),
            models.CheckConstraint(
                condition=Q(version__gt=0),
                name="loans_approval_version_positive",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Approval snapshots are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Approval snapshots cannot be deleted.")


class PawnLoanAccountingEvent(models.Model):
    loan = models.ForeignKey(
        PawnLoan,
        on_delete=models.PROTECT,
        related_name="accounting_events",
    )
    event_kind = models.CharField(
        max_length=32,
        choices=enum_choices(TransactionKind),
    )
    effective_date = models.DateField(db_index=True)
    payload = models.JSONField()
    payload_fingerprint = models.CharField(max_length=64)
    idempotency_key = models.CharField(max_length=180, unique=True)
    reversal_of = models.OneToOneField(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="reversed_by_event",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pawn_loan_accounting_events",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("loan_id", "created_at", "id")
        indexes = [
            models.Index(
                fields=("loan", "event_kind", "effective_date"),
                name="loans_acct_event_lookup_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(
                        event_kind=TransactionKind.REVERSAL.value,
                        reversal_of__isnull=False,
                    )
                    | (
                        ~Q(event_kind=TransactionKind.REVERSAL.value)
                        & Q(reversal_of__isnull=True)
                    )
                ),
                name="loans_event_reversal_link_valid",
            ),
        ]


class PawnLoanDisbursalSnapshot(models.Model):
    """Immutable gross-to-net evidence for one PawnLoan disbursal."""

    loan = models.OneToOneField(
        PawnLoan,
        on_delete=models.PROTECT,
        related_name="disbursal_snapshot",
    )
    approval_snapshot = models.ForeignKey(
        PawnLoanApprovalSnapshot,
        on_delete=models.PROTECT,
        related_name="disbursal_snapshots",
    )
    policy_snapshot = models.OneToOneField(
        LoanPolicySnapshot,
        on_delete=models.PROTECT,
        related_name="disbursal_snapshot",
    )
    accounting_event = models.OneToOneField(
        PawnLoanAccountingEvent,
        on_delete=models.PROTECT,
        related_name="disbursal_snapshot",
    )
    gross_principal = models.DecimalField(max_digits=18, decimal_places=4)
    monthly_interest = models.DecimalField(max_digits=18, decimal_places=4)
    advance_interest_periods = models.PositiveSmallIntegerField(default=0)
    advance_interest = models.DecimalField(max_digits=18, decimal_places=4)
    deducted_fees = models.DecimalField(max_digits=18, decimal_places=4)
    net_disbursed = models.DecimalField(max_digits=18, decimal_places=4)
    evidence = models.JSONField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pawn_loan_disbursal_snapshots",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("loan_id",)
        constraints = [
            models.CheckConstraint(
                condition=Q(gross_principal__gt=0),
                name="loans_disbursal_gross_positive",
            ),
            models.CheckConstraint(
                condition=Q(monthly_interest__gte=0)
                & Q(advance_interest__gte=0)
                & Q(deducted_fees__gte=0)
                & Q(net_disbursed__gt=0),
                name="loans_disbursal_amounts_valid",
            ),
        ]

    def clean(self):
        super().clean()
        if self.loan_id and self.approval_snapshot_id:
            if self.approval_snapshot.loan_id != self.loan_id:
                raise ValidationError("Approval snapshot must belong to this PawnLoan.")
        if self.loan_id and self.policy_snapshot_id:
            if self.policy_snapshot.loan_id != self.loan_id:
                raise ValidationError("Policy snapshot must belong to this PawnLoan.")
        if self.loan_id and self.accounting_event_id:
            if self.accounting_event.loan_id != self.loan_id:
                raise ValidationError("Accounting event must belong to this PawnLoan.")
            if self.accounting_event.event_kind != TransactionKind.DISBURSAL.value:
                raise ValidationError("Disbursal snapshot requires a disbursal event.")
        if self.gross_principal is not None and (
            self.net_disbursed is not None
            and self.advance_interest is not None
            and self.deducted_fees is not None
            and self.gross_principal
            != self.net_disbursed + self.advance_interest + self.deducted_fees
        ):
            raise ValidationError(
                "Net cash plus advance interest and deducted fees must equal gross principal."
            )

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Disbursal snapshots are immutable.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Disbursal snapshots cannot be deleted.")


class PawnLoanAccountingOutbox(models.Model):
    event = models.OneToOneField(
        PawnLoanAccountingEvent,
        on_delete=models.PROTECT,
        related_name="outbox",
    )
    idempotency_key = models.CharField(max_length=180, unique=True)
    payload = models.JSONField()
    payload_fingerprint = models.CharField(max_length=64)
    contract_version = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(
        max_length=16,
        choices=enum_choices(LoanOutboxStatus),
        default=LoanOutboxStatus.PENDING.value,
        db_index=True,
    )
    attempt_count = models.PositiveIntegerField(default=0)
    available_at = models.DateTimeField(default=timezone.now, db_index=True)
    claimed_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default="")
    dea_voucher_id = models.PositiveBigIntegerField(null=True, blank=True)
    dea_journal_entry_id = models.PositiveBigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("id",)
        indexes = [
            models.Index(
                fields=("status", "available_at"),
                name="loans_outbox_due_idx",
            ),
        ]


class PawnLoanInterestAccrual(models.Model):
    """Immutable, currency-rounded monthly interest recognition row."""

    loan = models.ForeignKey(
        PawnLoan,
        on_delete=models.PROTECT,
        related_name="interest_accruals",
    )
    period_number = models.PositiveIntegerField()
    period_start = models.DateField()
    period_end = models.DateField(db_index=True)
    period_fraction = models.DecimalField(max_digits=8, decimal_places=4)
    calculation_base = models.DecimalField(max_digits=30, decimal_places=12)
    unrounded_interest = models.DecimalField(max_digits=30, decimal_places=12)
    recognized_interest = models.DecimalField(max_digits=18, decimal_places=4)
    accounting_event = models.OneToOneField(
        PawnLoanAccountingEvent,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="interest_accrual",
    )
    finalized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pawn_loan_interest_accruals",
    )
    finalized_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("loan_id", "period_number")
        constraints = [
            models.UniqueConstraint(
                fields=("loan", "period_number"),
                name="loans_accrual_loan_period_uniq",
            ),
            models.CheckConstraint(
                condition=Q(period_number__gt=0),
                name="loans_accrual_period_positive",
            ),
            models.CheckConstraint(
                condition=Q(period_end__gte=F("period_start")),
                name="loans_accrual_dates_ordered",
            ),
            models.CheckConstraint(
                condition=Q(period_fraction__gt=0) & Q(period_fraction__lte=1),
                name="loans_accrual_fraction_range",
            ),
            models.CheckConstraint(
                condition=Q(calculation_base__gte=0)
                & Q(unrounded_interest__gte=0)
                & Q(recognized_interest__gte=0),
                name="loans_accrual_amounts_nonnegative",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Finalized PawnLoan interest accruals are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Finalized PawnLoan interest accruals cannot be deleted.")


class PawnLoanInterestAccrualLine(models.Model):
    """Immutable collateral-tranche calculation behind one accrual header."""

    accrual = models.ForeignKey(
        PawnLoanInterestAccrual,
        on_delete=models.PROTECT,
        related_name="lines",
    )
    collateral_item = models.ForeignKey(
        PawnCollateralItem,
        on_delete=models.PROTECT,
        related_name="interest_accrual_lines",
    )
    principal_base = models.DecimalField(max_digits=30, decimal_places=12)
    monthly_interest_rate = models.DecimalField(max_digits=12, decimal_places=6)
    period_fraction = models.DecimalField(max_digits=8, decimal_places=4)
    unrounded_interest = models.DecimalField(max_digits=30, decimal_places=12)
    calculated_interest = models.DecimalField(max_digits=18, decimal_places=4)
    advance_interest_applied = models.DecimalField(max_digits=18, decimal_places=4)
    recognized_interest = models.DecimalField(max_digits=18, decimal_places=4)

    class Meta:
        ordering = ("accrual_id", "collateral_item_id")
        constraints = [
            models.UniqueConstraint(
                fields=("accrual", "collateral_item"),
                name="loans_accrual_item_uniq",
            ),
            models.CheckConstraint(
                condition=Q(principal_base__gte=0)
                & Q(monthly_interest_rate__gte=0)
                & Q(unrounded_interest__gte=0)
                & Q(calculated_interest__gte=0)
                & Q(advance_interest_applied__gte=0)
                & Q(recognized_interest__gte=0),
                name="loans_accrual_line_amounts_valid",
            ),
            models.CheckConstraint(
                condition=Q(period_fraction__gt=0) & Q(period_fraction__lte=1),
                name="loans_accrual_line_fraction_valid",
            ),
        ]

    def clean(self):
        super().clean()
        if self.accrual_id and self.collateral_item_id:
            if self.accrual.loan_id != self.collateral_item.loan_id:
                raise ValidationError(
                    "Accrual line collateral must belong to the accrual PawnLoan."
                )
        if (
            self.calculated_interest is not None
            and self.advance_interest_applied is not None
            and self.recognized_interest is not None
            and self.calculated_interest
            != self.advance_interest_applied + self.recognized_interest
        ):
            raise ValidationError(
                "Calculated interest must equal advance interest applied plus recognized interest."
            )

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("PawnLoan accrual lines are immutable.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("PawnLoan accrual lines cannot be deleted.")


class PawnLoanRepaymentAllocationLine(models.Model):
    """Immutable principal movement against one collateral tranche."""

    accounting_event = models.ForeignKey(
        PawnLoanAccountingEvent,
        on_delete=models.PROTECT,
        related_name="repayment_allocation_lines",
    )
    collateral_item = models.ForeignKey(
        PawnCollateralItem,
        on_delete=models.PROTECT,
        related_name="repayment_allocation_lines",
    )
    allocation_order = models.PositiveSmallIntegerField()
    monthly_interest_rate = models.DecimalField(max_digits=12, decimal_places=6)
    balance_before = models.DecimalField(max_digits=18, decimal_places=4)
    principal_applied = models.DecimalField(max_digits=18, decimal_places=4)
    balance_after = models.DecimalField(max_digits=18, decimal_places=4)

    class Meta:
        ordering = ("accounting_event_id", "allocation_order")
        constraints = [
            models.UniqueConstraint(
                fields=("accounting_event", "collateral_item"),
                name="loans_repayment_event_item_uniq",
            ),
            models.UniqueConstraint(
                fields=("accounting_event", "allocation_order"),
                name="loans_repayment_event_order_uniq",
            ),
            models.CheckConstraint(
                condition=Q(allocation_order__gt=0),
                name="loans_repayment_order_positive",
            ),
            models.CheckConstraint(
                condition=Q(monthly_interest_rate__gte=0)
                & Q(balance_before__gte=0)
                & Q(principal_applied__gte=0)
                & Q(balance_after__gte=0),
                name="loans_repayment_line_amounts_valid",
            ),
        ]

    def clean(self):
        super().clean()
        if self.accounting_event_id and self.collateral_item_id:
            if self.accounting_event.loan_id != self.collateral_item.loan_id:
                raise ValidationError(
                    "Repayment allocation collateral must belong to the event PawnLoan."
                )
            if self.accounting_event.event_kind != TransactionKind.REPAYMENT.value:
                raise ValidationError(
                    "Repayment allocation requires a repayment accounting event."
                )
        if (
            self.balance_before is not None
            and self.principal_applied is not None
            and self.balance_after is not None
            and self.balance_before - self.principal_applied != self.balance_after
        ):
            raise ValidationError(
                "Repayment allocation balance after must equal balance before minus principal applied."
            )

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("PawnLoan repayment allocation lines are immutable.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("PawnLoan repayment allocation lines cannot be deleted.")


class PawnLoanPrincipalClosingLine(models.Model):
    """Immutable item-principal settlement for release or renewal closure."""

    accounting_event = models.ForeignKey(
        PawnLoanAccountingEvent,
        on_delete=models.PROTECT,
        related_name="principal_closing_lines",
    )
    collateral_item = models.ForeignKey(
        PawnCollateralItem,
        on_delete=models.PROTECT,
        related_name="principal_closing_lines",
    )
    allocation_order = models.PositiveSmallIntegerField()
    monthly_interest_rate = models.DecimalField(max_digits=12, decimal_places=6)
    balance_before = models.DecimalField(max_digits=18, decimal_places=4)
    principal_settled = models.DecimalField(max_digits=18, decimal_places=4)
    balance_after = models.DecimalField(max_digits=18, decimal_places=4)

    class Meta:
        ordering = ("accounting_event_id", "allocation_order")
        constraints = [
            models.UniqueConstraint(
                fields=("accounting_event", "collateral_item"),
                name="loans_close_event_item_uniq",
            ),
            models.UniqueConstraint(
                fields=("accounting_event", "allocation_order"),
                name="loans_close_event_order_uniq",
            ),
            models.CheckConstraint(
                condition=Q(allocation_order__gt=0),
                name="loans_close_order_positive",
            ),
            models.CheckConstraint(
                condition=(
                    Q(monthly_interest_rate__gte=0)
                    & Q(balance_before__gte=0)
                    & Q(principal_settled__gte=0)
                    & Q(balance_after__gte=0)
                ),
                name="loans_close_line_amounts_valid",
            ),
        ]

    def clean(self):
        super().clean()
        if self.accounting_event_id and self.collateral_item_id:
            if self.accounting_event.loan_id != self.collateral_item.loan_id:
                raise ValidationError(
                    "Closing-line collateral must belong to the event PawnLoan."
                )
            if self.accounting_event.event_kind not in {
                TransactionKind.RELEASE_RECEIPT.value,
                TransactionKind.RENEWAL_SETTLEMENT.value,
            }:
                raise ValidationError(
                    "Closing lines require a release or renewal-settlement event."
                )
        if (
            self.balance_before is not None
            and self.principal_settled is not None
            and self.balance_after is not None
            and self.balance_before - self.principal_settled != self.balance_after
        ):
            raise ValidationError("Closing-line balances do not reconcile.")

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("PawnLoan principal closing lines are immutable.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("PawnLoan principal closing lines cannot be deleted.")


class PawnLoanPrincipalOpeningLine(models.Model):
    """Immutable initial item-principal evidence for a renewal successor."""

    accounting_event = models.ForeignKey(
        PawnLoanAccountingEvent,
        on_delete=models.PROTECT,
        related_name="principal_opening_lines",
    )
    collateral_item = models.OneToOneField(
        PawnCollateralItem,
        on_delete=models.PROTECT,
        related_name="principal_opening_line",
    )
    predecessor_collateral_item = models.ForeignKey(
        PawnCollateralItem,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="successor_principal_opening_lines",
    )
    allocation_order = models.PositiveSmallIntegerField()
    monthly_interest_rate = models.DecimalField(max_digits=12, decimal_places=6)
    principal_opened = models.DecimalField(max_digits=18, decimal_places=4)

    class Meta:
        ordering = ("accounting_event_id", "allocation_order")
        constraints = [
            models.UniqueConstraint(
                fields=("accounting_event", "allocation_order"),
                name="loans_open_event_order_uniq",
            ),
            models.CheckConstraint(
                condition=Q(allocation_order__gt=0),
                name="loans_open_order_positive",
            ),
            models.CheckConstraint(
                condition=Q(monthly_interest_rate__gte=0)
                & Q(principal_opened__gt=0),
                name="loans_open_line_amounts_valid",
            ),
        ]

    def clean(self):
        super().clean()
        if self.accounting_event_id and self.collateral_item_id:
            if self.accounting_event.loan_id != self.collateral_item.loan_id:
                raise ValidationError(
                    "Opening-line collateral must belong to the successor PawnLoan."
                )
            if self.accounting_event.event_kind != TransactionKind.RENEWAL_OPENING.value:
                raise ValidationError("Opening lines require a renewal-opening event.")
        if self.predecessor_collateral_item_id and self.collateral_item_id:
            if self.predecessor_collateral_item_id == self.collateral_item_id:
                raise ValidationError(
                    "Renewal predecessor and successor collateral must differ."
                )
        if self.collateral_item_id:
            expected_predecessor_id = self.collateral_item.renewed_from_id
            if self.predecessor_collateral_item_id != expected_predecessor_id:
                raise ValidationError(
                    "Opening-line predecessor must match the collateral renewal lineage."
                )

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("PawnLoan principal opening lines are immutable.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("PawnLoan principal opening lines cannot be deleted.")


class PawnLoanRelease(models.Model):
    """Immutable settlement document authorizing a physical collateral return."""

    workspace = models.ForeignKey(
        "orgs.Company",
        on_delete=models.PROTECT,
        related_name="pawn_loan_releases",
    )
    loan = models.ForeignKey(
        PawnLoan,
        on_delete=models.PROTECT,
        related_name="releases",
    )
    release_number = models.CharField(max_length=64)
    request_key = models.CharField(max_length=120)
    effective_date = models.DateField(db_index=True)
    is_full_release = models.BooleanField(default=True)
    settlement_amount = models.DecimalField(max_digits=18, decimal_places=4)
    principal_amount = models.DecimalField(max_digits=18, decimal_places=4)
    interest_amount = models.DecimalField(max_digits=18, decimal_places=4)
    fee_amount = models.DecimalField(max_digits=18, decimal_places=4)
    valuation_snapshot = models.JSONField(default=dict)
    accounting_event = models.OneToOneField(
        PawnLoanAccountingEvent,
        on_delete=models.PROTECT,
        related_name="release",
    )
    catch_up_accrual = models.OneToOneField(
        PawnLoanInterestAccrual,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="release_catch_up",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pawn_loan_releases_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("loan_id", "effective_date", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("workspace", "release_number"),
                name="loans_release_workspace_number_uniq",
            ),
            models.UniqueConstraint(
                fields=("loan", "request_key"),
                name="loans_release_loan_request_uniq",
            ),
            models.CheckConstraint(
                condition=(
                    Q(settlement_amount__gte=0)
                    & Q(principal_amount__gte=0)
                    & Q(interest_amount__gte=0)
                    & Q(fee_amount__gte=0)
                ),
                name="loans_release_amounts_nonnegative",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("PawnLoan releases are immutable.")
        self.clean()
        return super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        errors = {}
        tenant_workspace_id = current_tenant_workspace_id()
        if tenant_workspace_id and self.workspace_id != tenant_workspace_id:
            errors["workspace"] = "Release workspace must match the active tenant."
        if self.loan_id and self.workspace_id:
            if self.loan.workspace_id != self.workspace_id:
                errors["loan"] = "Release loan must belong to its workspace."
        if self.catch_up_accrual_id and self.loan_id:
            if self.catch_up_accrual.loan_id != self.loan_id:
                errors["catch_up_accrual"] = (
                    "Release catch-up accrual must belong to the same loan."
                )
        if self.settlement_amount != (
            self.principal_amount + self.interest_amount + self.fee_amount
        ):
            errors["settlement_amount"] = (
                "Settlement must equal principal, interest, and fees."
            )
        if errors:
            raise ValidationError(errors)

    def delete(self, *args, **kwargs):
        raise ValidationError("PawnLoan releases cannot be deleted.")


class PawnLoanReleaseItem(models.Model):
    release = models.ForeignKey(
        PawnLoanRelease,
        on_delete=models.PROTECT,
        related_name="items",
    )
    collateral_item = models.ForeignKey(
        PawnCollateralItem,
        on_delete=models.PROTECT,
        related_name="release_items",
    )
    valuation_snapshot = models.JSONField(default=dict)
    returned_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("release_id", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("release", "collateral_item"),
                name="loans_release_item_uniq",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("PawnLoan release items are immutable.")
        self.clean()
        return super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if (
            self.release_id
            and self.collateral_item_id
            and self.release.loan_id != self.collateral_item.loan_id
        ):
            raise ValidationError(
                {"collateral_item": "Released collateral must belong to the loan."}
            )

    def delete(self, *args, **kwargs):
        raise ValidationError("PawnLoan release items cannot be deleted.")


class PawnCollateralCustodyEvent(models.Model):
    collateral_item = models.ForeignKey(
        PawnCollateralItem,
        on_delete=models.PROTECT,
        related_name="custody_history",
    )
    release = models.ForeignKey(
        PawnLoanRelease,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="custody_events",
    )
    auction = models.ForeignKey(
        "PawnLoanAuction",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="custody_events",
    )
    renewal = models.ForeignKey(
        "PawnLoanRenewal",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="custody_events",
    )
    funding_pledge = models.ForeignKey(
        "FundingPledge",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="custody_events",
    )
    funding_return = models.ForeignKey(
        "FundingReturn",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="custody_events",
    )
    funding_pledge_reversal = models.ForeignKey(
        "FundingPledgeReversal",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="custody_events",
    )
    funding_return_reversal = models.ForeignKey(
        "FundingReturnReversal",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="custody_events",
    )
    release_reversal = models.ForeignKey(
        "PawnLoanReleaseReversal",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="custody_events",
    )
    auction_reversal = models.ForeignKey(
        "PawnLoanAuctionReversal",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="custody_events",
    )
    renewal_reversal = models.ForeignKey(
        "PawnLoanRenewalReversal",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="custody_events",
    )
    from_state = models.CharField(
        max_length=32,
        choices=enum_choices(CollateralCustodyState),
    )
    to_state = models.CharField(
        max_length=32,
        choices=enum_choices(CollateralCustodyState),
    )
    effective_date = models.DateField(db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pawn_collateral_custody_events",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("collateral_item_id", "created_at", "id")
        constraints = [
            models.CheckConstraint(
                condition=~Q(from_state=F("to_state")),
                name="loans_custody_state_changes",
            ),
            models.UniqueConstraint(
                fields=("funding_pledge_reversal", "collateral_item"),
                name="loans_funding_pledge_custody_reversal_uniq",
            ),
            models.UniqueConstraint(
                fields=("funding_return_reversal", "collateral_item"),
                name="loans_funding_return_custody_reversal_uniq",
            ),
            models.CheckConstraint(
                condition=(
                    (
                        Q(release__isnull=False)
                        & Q(auction__isnull=True)
                        & Q(renewal__isnull=True)
                        & Q(funding_pledge__isnull=True)
                        & Q(funding_return__isnull=True)
                    )
                    | (
                        Q(release__isnull=True)
                        & Q(auction__isnull=False)
                        & Q(renewal__isnull=True)
                        & Q(funding_pledge__isnull=True)
                        & Q(funding_return__isnull=True)
                    )
                    | (
                        Q(release__isnull=True)
                        & Q(auction__isnull=True)
                        & Q(renewal__isnull=False)
                        & Q(funding_pledge__isnull=True)
                        & Q(funding_return__isnull=True)
                    )
                    | (
                        Q(release__isnull=True)
                        & Q(auction__isnull=True)
                        & Q(renewal__isnull=True)
                        & Q(funding_pledge__isnull=False)
                        & Q(funding_return__isnull=True)
                    )
                    | (
                        Q(release__isnull=True)
                        & Q(auction__isnull=True)
                        & Q(renewal__isnull=True)
                        & Q(funding_pledge__isnull=True)
                        & Q(funding_return__isnull=False)
                    )
                ),
                name="loans_custody_one_source",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Collateral custody events are immutable.")
        self.clean()
        return super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if (
            self.release_id
            and self.collateral_item_id
            and self.release.loan_id != self.collateral_item.loan_id
        ):
            raise ValidationError(
                {"collateral_item": "Custody item must belong to the release loan."}
            )
        if self.auction_id and self.collateral_item_id:
            if self.auction.loan_id != self.collateral_item.loan_id:
                raise ValidationError(
                    {"collateral_item": "Custody item must belong to the auction loan."}
                )
        if self.renewal_id and self.collateral_item_id:
            if self.collateral_item.loan_id not in {
                self.renewal.source_loan_id,
                self.renewal.successor_loan_id,
            }:
                raise ValidationError(
                    {"collateral_item": "Custody item must belong to the renewal chain."}
                )
        if self.funding_pledge_id and self.collateral_item_id:
            pledge_item_exists = self.funding_pledge.items.filter(
                collateral_item_id=self.collateral_item_id
            ).exists()
            if not pledge_item_exists:
                raise ValidationError(
                    {"collateral_item": "Custody item must belong to the funding pledge."}
                )
        if self.funding_return_id and self.collateral_item_id:
            return_item_exists = self.funding_return.items.filter(
                pledge_item__collateral_item_id=self.collateral_item_id
            ).exists()
            if not return_item_exists:
                raise ValidationError(
                    {"collateral_item": "Custody item must belong to the funding return."}
                )
        if self.auction_reversal_id and self.auction_id:
            if self.auction_reversal.auction_id != self.auction_id:
                raise ValidationError(
                    {"auction_reversal": "Custody reversal must match the auction."}
                )
        elif self.auction_reversal_id:
            raise ValidationError(
                {"auction_reversal": "Auction reversal custody requires its auction."}
            )
        if self.renewal_reversal_id and self.renewal_id:
            if self.renewal_reversal.renewal_id != self.renewal_id:
                raise ValidationError(
                    {"renewal_reversal": "Custody reversal must match the renewal."}
                )
        elif self.renewal_reversal_id:
            raise ValidationError(
                {"renewal_reversal": "Renewal reversal custody requires its renewal."}
            )
        if self.release_reversal_id and self.release_id:
            if self.release_reversal.release_id != self.release_id:
                raise ValidationError(
                    {"release_reversal": "Custody reversal must match the release."}
                )
        elif self.release_reversal_id:
            raise ValidationError(
                {"release_reversal": "Release reversal custody requires its release."}
            )
        if self.funding_pledge_reversal_id and self.funding_pledge_id:
            if (
                self.funding_pledge_reversal.funding_pledge_id
                != self.funding_pledge_id
            ):
                raise ValidationError(
                    {"funding_pledge_reversal": "Custody reversal must match the funding pledge."}
                )
        elif self.funding_pledge_reversal_id:
            raise ValidationError(
                {"funding_pledge_reversal": "Funding pledge reversal custody requires its pledge."}
            )
        if self.funding_return_reversal_id and self.funding_return_id:
            if (
                self.funding_return_reversal.funding_return_id
                != self.funding_return_id
            ):
                raise ValidationError(
                    {"funding_return_reversal": "Custody reversal must match the funding return."}
                )
        elif self.funding_return_reversal_id:
            raise ValidationError(
                {"funding_return_reversal": "Funding return reversal custody requires its return."}
            )

    def delete(self, *args, **kwargs):
        raise ValidationError("Collateral custody events cannot be deleted.")


class PawnLoanReleaseReversal(models.Model):
    """Immutable compensation record; the original release is never edited."""

    release = models.OneToOneField(
        PawnLoanRelease,
        on_delete=models.PROTECT,
        related_name="reversal",
    )
    accounting_event = models.OneToOneField(
        PawnLoanAccountingEvent,
        on_delete=models.PROTECT,
        related_name="release_reversal",
    )
    catch_up_reversal_event = models.OneToOneField(
        PawnLoanAccountingEvent,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="release_catch_up_reversal",
    )
    reason = models.TextField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pawn_loan_release_reversals_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("PawnLoan release reversals are immutable.")
        self.clean()
        return super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        errors = {}
        if not str(self.reason or "").strip():
            errors["reason"] = "A reversal reason is required."
        if self.release_id and self.accounting_event_id:
            if (
                self.accounting_event.reversal_of_id
                != self.release.accounting_event_id
            ):
                errors["accounting_event"] = (
                    "Release reversal event must compensate the release event."
                )
        if self.catch_up_reversal_event_id and self.release_id:
            catch_up_event_id = (
                self.release.catch_up_accrual.accounting_event_id
                if self.release.catch_up_accrual_id
                else None
            )
            if self.catch_up_reversal_event.reversal_of_id != catch_up_event_id:
                errors["catch_up_reversal_event"] = (
                    "Catch-up reversal must compensate the release catch-up accrual."
                )
        if errors:
            raise ValidationError(errors)

    def delete(self, *args, **kwargs):
        raise ValidationError("PawnLoan release reversals cannot be deleted.")


class PawnLoanNotice(models.Model):
    """Loan-owned notice intent; provider delivery remains owned by Notify v2."""

    workspace = models.ForeignKey(
        "orgs.Company",
        on_delete=models.PROTECT,
        related_name="pawn_loan_notices",
    )
    loan = models.ForeignKey(
        PawnLoan,
        on_delete=models.PROTECT,
        related_name="notices",
    )
    notice_kind = models.CharField(
        max_length=32,
        choices=enum_choices(PawnLoanNoticeKind),
    )
    channel = models.CharField(
        max_length=16,
        choices=enum_choices(PawnLoanNoticeChannel),
    )
    request_key = models.CharField(max_length=120)
    scheduled_for = models.DateTimeField(db_index=True)
    recipient_name = models.CharField(max_length=255)
    recipient_email = models.EmailField(blank=True)
    recipient_phone = models.CharField(max_length=32, blank=True)
    payload_snapshot = models.JSONField(default=dict)
    notification_event_id = models.PositiveBigIntegerField(null=True, blank=True)
    notification_job_id = models.PositiveBigIntegerField(null=True, blank=True)
    source_auction = models.OneToOneField(
        "PawnLoanAuction",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="notice",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pawn_loan_notices_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("loan", "request_key"),
                name="loans_notice_loan_request_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=("workspace", "scheduled_for"),
                name="loans_notice_due_idx",
            ),
            models.Index(
                fields=("loan", "notice_kind", "created_at"),
                name="loans_notice_kind_idx",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        tenant_workspace_id = current_tenant_workspace_id()
        if tenant_workspace_id and self.workspace_id != tenant_workspace_id:
            errors["workspace"] = "Notice workspace must match the active tenant."
        if self.loan_id and self.workspace_id:
            if self.loan.workspace_id != self.workspace_id:
                errors["loan"] = "Notice loan must belong to its workspace."
        if self.channel == PawnLoanNoticeChannel.EMAIL.value and not self.recipient_email:
            errors["recipient_email"] = "Email delivery requires a recipient email."
        if self.channel in {
            PawnLoanNoticeChannel.SMS.value,
            PawnLoanNoticeChannel.WHATSAPP.value,
        } and not self.recipient_phone:
            errors["recipient_phone"] = "SMS/WhatsApp delivery requires a recipient phone."
        if self.source_auction_id:
            if self.notice_kind != PawnLoanNoticeKind.AUCTION_NOTICE.value:
                errors["source_auction"] = "Only an auction notice can reference an auction."
            elif self.source_auction.loan_id != self.loan_id:
                errors["source_auction"] = "Auction notice must reference the same loan."
        elif self.notice_kind == PawnLoanNoticeKind.AUCTION_NOTICE.value:
            errors["source_auction"] = "Auction notice requires its source auction."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("PawnLoan notices cannot be deleted.")


class PawnLoanAuction(models.Model):
    """Loan-owned recovery process; accounting remains an immutable event."""

    workspace = models.ForeignKey(
        "orgs.Company", on_delete=models.PROTECT, related_name="pawn_loan_auctions"
    )
    loan = models.ForeignKey(PawnLoan, on_delete=models.PROTECT, related_name="auctions")
    auction_number = models.CharField(max_length=96)
    attempt_number = models.PositiveIntegerField()
    request_key = models.CharField(max_length=120)
    state = models.CharField(
        max_length=20,
        choices=enum_choices(PawnLoanAuctionState),
        default=PawnLoanAuctionState.INITIATED.value,
        db_index=True,
    )
    notice_date = models.DateField()
    scheduled_date = models.DateField(db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)
    buyer_name = models.CharField(max_length=255, blank=True)
    buyer_reference = models.CharField(max_length=120, blank=True)
    recovery_amount = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    principal_amount = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    interest_amount = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    fee_amount = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    accounting_event = models.OneToOneField(
        PawnLoanAccountingEvent,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="auction",
    )
    catch_up_accrual = models.OneToOneField(
        PawnLoanInterestAccrual,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="auction_catch_up",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pawn_loan_auctions_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("loan_id", "attempt_number")
        constraints = [
            models.UniqueConstraint(fields=("workspace", "auction_number"), name="loans_auction_workspace_number_uniq"),
            models.UniqueConstraint(fields=("loan", "attempt_number"), name="loans_auction_loan_attempt_uniq"),
            models.UniqueConstraint(fields=("loan", "request_key"), name="loans_auction_loan_request_uniq"),
        ]
        indexes = [
            models.Index(fields=("workspace", "state", "scheduled_date"), name="loans_auction_state_date_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        tenant_workspace_id = current_tenant_workspace_id()
        if tenant_workspace_id and self.workspace_id != tenant_workspace_id:
            errors["workspace"] = "Auction workspace must match the active tenant."
        if self.loan_id and self.workspace_id and self.loan.workspace_id != self.workspace_id:
            errors["loan"] = "Auction loan must belong to its workspace."
        if self.scheduled_date and self.notice_date and self.scheduled_date <= self.notice_date:
            errors["scheduled_date"] = "Auction must be scheduled after its notice date."
        if self.state == PawnLoanAuctionState.COMPLETED.value:
            required = {
                "recovery_amount": self.recovery_amount,
                "principal_amount": self.principal_amount,
                "interest_amount": self.interest_amount,
                "fee_amount": self.fee_amount,
                "accounting_event": self.accounting_event_id,
                "completed_at": self.completed_at,
                "buyer_name": self.buyer_name,
            }
            for field, value in required.items():
                if value in (None, ""):
                    errors[field] = "Completed auction is missing required recovery evidence."
            if all(value is not None for value in (self.recovery_amount, self.principal_amount, self.interest_amount, self.fee_amount)):
                if self.recovery_amount != self.principal_amount + self.interest_amount + self.fee_amount:
                    errors["recovery_amount"] = "Recovery must equal principal, interest, and fees."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("PawnLoan auctions cannot be deleted.")


class PawnLoanAuctionItem(models.Model):
    auction = models.ForeignKey(PawnLoanAuction, on_delete=models.PROTECT, related_name="items")
    collateral_item = models.ForeignKey(PawnCollateralItem, on_delete=models.PROTECT, related_name="auction_items")
    snapshot = models.JSONField(default=dict)
    disposed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("auction_id", "id")
        constraints = [models.UniqueConstraint(fields=("auction", "collateral_item"), name="loans_auction_item_uniq")]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("PawnLoan auction items are immutable.")
        if self.auction_id and self.collateral_item_id and self.auction.loan_id != self.collateral_item.loan_id:
            raise ValidationError({"collateral_item": "Auction item must belong to the auction loan."})
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("PawnLoan auction items cannot be deleted.")


class PawnLoanAuctionReversal(models.Model):
    auction = models.OneToOneField(PawnLoanAuction, on_delete=models.PROTECT, related_name="reversal")
    accounting_event = models.OneToOneField(PawnLoanAccountingEvent, on_delete=models.PROTECT, related_name="auction_reversal")
    catch_up_reversal_event = models.OneToOneField(
        PawnLoanAccountingEvent,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="auction_catch_up_reversal",
    )
    reason = models.TextField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pawn_loan_auction_reversals_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("PawnLoan auction reversals are immutable.")
        if not str(self.reason or "").strip():
            raise ValidationError({"reason": "A reversal reason is required."})
        if self.auction_id and self.accounting_event_id and self.accounting_event.reversal_of_id != self.auction.accounting_event_id:
            raise ValidationError({"accounting_event": "Auction reversal must compensate the recovery event."})
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("PawnLoan auction reversals cannot be deleted.")


class PawnLoanRenewal(models.Model):
    """Immutable completed renewal linking one source loan to its successor."""

    workspace = models.ForeignKey(
        "orgs.Company", on_delete=models.PROTECT, related_name="pawn_loan_renewals"
    )
    source_loan = models.OneToOneField(
        PawnLoan, on_delete=models.PROTECT, related_name="renewal_as_source"
    )
    successor_loan = models.OneToOneField(
        PawnLoan, on_delete=models.PROTECT, related_name="origin_renewal"
    )
    renewal_number = models.CharField(max_length=96)
    request_key = models.CharField(max_length=120)
    mode = models.CharField(max_length=20, choices=enum_choices(PawnLoanRenewalMode))
    renewal_date = models.DateField(db_index=True)
    source_principal_amount = models.DecimalField(max_digits=18, decimal_places=4)
    source_capitalized_principal_amount = models.DecimalField(max_digits=18, decimal_places=4)
    interest_settled = models.DecimalField(max_digits=18, decimal_places=4)
    fees_settled = models.DecimalField(max_digits=18, decimal_places=4)
    principal_paid = models.DecimalField(max_digits=18, decimal_places=4)
    top_up_amount = models.DecimalField(max_digits=18, decimal_places=4)
    successor_principal_amount = models.DecimalField(max_digits=18, decimal_places=4)
    successor_capitalized_principal_amount = models.DecimalField(max_digits=18, decimal_places=4)
    valuation_snapshot = models.JSONField(default=dict)
    settlement_event = models.OneToOneField(
        PawnLoanAccountingEvent,
        on_delete=models.PROTECT,
        related_name="renewal_settlement",
    )
    opening_event = models.OneToOneField(
        PawnLoanAccountingEvent,
        on_delete=models.PROTECT,
        related_name="renewal_opening",
    )
    catch_up_accrual = models.OneToOneField(
        PawnLoanInterestAccrual,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="renewal_catch_up",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pawn_loan_renewals_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-renewal_date", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("workspace", "renewal_number"),
                name="loans_renewal_workspace_number_uniq",
            ),
            models.UniqueConstraint(
                fields=("workspace", "request_key"),
                name="loans_renewal_workspace_request_uniq",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        tenant_workspace_id = current_tenant_workspace_id()
        if tenant_workspace_id and self.workspace_id != tenant_workspace_id:
            errors["workspace"] = "Renewal workspace must match the active tenant."
        if self.source_loan_id and self.successor_loan_id:
            if self.source_loan_id == self.successor_loan_id:
                errors["successor_loan"] = "Renewal successor must be a different loan."
            if self.source_loan.workspace_id != self.workspace_id or self.successor_loan.workspace_id != self.workspace_id:
                errors["workspace"] = "Both renewal loans must belong to the workspace."
            if self.source_loan.borrower_id != self.successor_loan.borrower_id:
                errors["successor_loan"] = "Renewal successor must retain the borrower."
        amounts = (
            self.source_principal_amount,
            self.source_capitalized_principal_amount,
            self.interest_settled,
            self.fees_settled,
            self.principal_paid,
            self.top_up_amount,
            self.successor_principal_amount,
            self.successor_capitalized_principal_amount,
        )
        if any(value is None or value < 0 for value in amounts):
            errors["successor_principal_amount"] = "Renewal amounts must be non-negative."
        if self.source_principal_amount is not None and self.principal_paid is not None and self.top_up_amount is not None:
            if self.successor_principal_amount != self.source_principal_amount - self.principal_paid + self.top_up_amount:
                errors["successor_principal_amount"] = "Successor principal does not reconcile to the renewal."
        if self.successor_principal_amount is not None and self.successor_principal_amount <= 0:
            errors["successor_principal_amount"] = "Renewal successor principal must be positive."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("PawnLoan renewals are immutable.")
        self.clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("PawnLoan renewals cannot be deleted.")


class PawnLoanRenewalReversal(models.Model):
    renewal = models.OneToOneField(
        PawnLoanRenewal, on_delete=models.PROTECT, related_name="reversal"
    )
    settlement_reversal_event = models.OneToOneField(
        PawnLoanAccountingEvent,
        on_delete=models.PROTECT,
        related_name="renewal_settlement_reversal",
    )
    opening_reversal_event = models.OneToOneField(
        PawnLoanAccountingEvent,
        on_delete=models.PROTECT,
        related_name="renewal_opening_reversal",
    )
    catch_up_reversal_event = models.OneToOneField(
        PawnLoanAccountingEvent,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="renewal_catch_up_reversal",
    )
    reason = models.TextField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pawn_loan_renewal_reversals_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("PawnLoan renewal reversals are immutable.")
        if not str(self.reason or "").strip():
            raise ValidationError({"reason": "A renewal reversal reason is required."})
        if self.renewal_id and self.settlement_reversal_event_id:
            if self.settlement_reversal_event.reversal_of_id != self.renewal.settlement_event_id:
                raise ValidationError({"settlement_reversal_event": "Reversal must compensate the settlement event."})
        if self.renewal_id and self.opening_reversal_event_id:
            if self.opening_reversal_event.reversal_of_id != self.renewal.opening_event_id:
                raise ValidationError({"opening_reversal_event": "Reversal must compensate the opening event."})
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("PawnLoan renewal reversals cannot be deleted.")
