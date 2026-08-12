from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

from apps.tenant_apps.loans.domain import (
    LoanAmortisationMethod,
    LoanExtraPaymentRule,
    LoanPaymentFrequency,
    LoanProductVersionStatus,
    LoanRepaymentStructure,
)
from apps.tenant_apps.loans.models.core import current_tenant_workspace_id, enum_choices


class LoanProduct(models.Model):
    workspace = models.ForeignKey(
        "orgs.Company", on_delete=models.PROTECT, related_name="loan_products"
    )
    code = models.CharField(max_length=40)
    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="loan_products_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="loan_products_updated",
    )

    class Meta:
        ordering = ("workspace_id", "code")
        constraints = [
            models.UniqueConstraint(
                fields=("workspace", "code"), name="loans_product_workspace_code_uniq"
            )
        ]
        indexes = [
            models.Index(
                fields=("workspace", "is_active"), name="loans_product_active_idx"
            )
        ]

    def clean(self):
        super().clean()
        workspace_id = current_tenant_workspace_id()
        if workspace_id and self.workspace_id != workspace_id:
            raise ValidationError({"workspace": "Product must belong to the active workspace."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} - {self.name}"


class LoanProductVersion(models.Model):
    product = models.ForeignKey(
        LoanProduct, on_delete=models.PROTECT, related_name="versions"
    )
    version = models.PositiveIntegerField()
    status = models.CharField(
        max_length=12,
        choices=enum_choices(LoanProductVersionStatus),
        default=LoanProductVersionStatus.DRAFT.value,
        db_index=True,
    )
    available_from = models.DateField(null=True, blank=True)
    available_until = models.DateField(null=True, blank=True)
    repayment_structure = models.CharField(
        max_length=32, choices=enum_choices(LoanRepaymentStructure)
    )
    amortisation_method = models.CharField(
        max_length=24,
        choices=enum_choices(LoanAmortisationMethod),
        default=LoanAmortisationMethod.NONE.value,
    )
    payment_frequency = models.CharField(
        max_length=16, choices=enum_choices(LoanPaymentFrequency)
    )
    minimum_tenor_months = models.PositiveIntegerField(default=1)
    maximum_tenor_months = models.PositiveIntegerField()
    operational_grace_days = models.PositiveSmallIntegerField(default=3)
    extra_payment_rule = models.CharField(
        max_length=32, choices=enum_choices(LoanExtraPaymentRule)
    )
    calculation_contract_version = models.CharField(max_length=40)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="loan_product_versions_created",
    )

    class Meta:
        ordering = ("product_id", "version")
        constraints = [
            models.UniqueConstraint(
                fields=("product", "version"), name="loans_product_version_uniq"
            ),
            models.UniqueConstraint(
                fields=("product",),
                condition=Q(status=LoanProductVersionStatus.ACTIVE.value),
                name="loans_product_one_active_uniq",
            ),
            models.CheckConstraint(
                condition=Q(maximum_tenor_months__gte=F("minimum_tenor_months")),
                name="loans_product_tenor_range_valid",
            ),
            models.CheckConstraint(
                condition=Q(operational_grace_days__lte=30),
                name="loans_product_grace_reasonable",
            ),
        ]
        indexes = [
            models.Index(
                fields=("product", "status", "available_from"),
                name="loans_product_ready_idx",
            )
        ]

    @property
    def workspace_id(self):
        return self.product.workspace_id

    def clean(self):
        super().clean()
        errors = {}
        workspace_id = current_tenant_workspace_id()
        if workspace_id and self.product_id and self.product.workspace_id != workspace_id:
            errors["product"] = "Product version must belong to the active workspace."
        if self.available_from and self.available_until:
            if self.available_until < self.available_from:
                errors["available_until"] = "Availability end cannot precede its start."
        if self.repayment_structure == LoanRepaymentStructure.INSTALLMENT.value:
            if self.amortisation_method == LoanAmortisationMethod.NONE.value:
                errors["amortisation_method"] = "Installment products require amortisation."
        elif self.amortisation_method != LoanAmortisationMethod.NONE.value:
            errors["amortisation_method"] = "Only installment products use amortisation."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            original = type(self).objects.get(pk=self.pk)
            immutable_fields = (
                "product_id", "version", "available_from", "available_until",
                "repayment_structure", "amortisation_method", "payment_frequency",
                "minimum_tenor_months", "maximum_tenor_months",
                "operational_grace_days", "extra_payment_rule",
                "calculation_contract_version", "created_by_id",
            )
            if any(getattr(self, field) != getattr(original, field) for field in immutable_fields):
                raise ValidationError("LoanProductVersion contract is immutable; create a new version.")
            allowed = {
                LoanProductVersionStatus.DRAFT.value: LoanProductVersionStatus.ACTIVE.value,
                LoanProductVersionStatus.ACTIVE.value: LoanProductVersionStatus.RETIRED.value,
            }
            if self.status != original.status and allowed.get(original.status) != self.status:
                raise ValidationError("Product version status must transition DRAFT to ACTIVE to RETIRED.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("LoanProductVersion is immutable and cannot be deleted.")

    def __str__(self):
        return f"{self.product.code} v{self.version}"
