"""Persistence for the disabled FundingLoan Gate B prototype."""

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from apps.tenant_apps.loans.domain.future_funding import (
    FundingLoanEventKind,
    FundingLoanState,
)

from .core import PawnCollateralItem, current_tenant_workspace_id, enum_choices


class ImmutableEvidenceModel(models.Model):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError(f"{self._meta.verbose_name.title()} is immutable.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(f"{self._meta.verbose_name.title()} cannot be deleted.")


class FundingLoanSequence(models.Model):
    workspace = models.OneToOneField(
        "orgs.Company",
        on_delete=models.PROTECT,
        related_name="funding_loan_sequence",
    )
    prefix = models.CharField(max_length=24, default="FL-")
    width = models.PositiveSmallIntegerField(default=6)
    next_value = models.PositiveBigIntegerField(default=1)
    maximum_value = models.PositiveBigIntegerField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(width__gt=0) & Q(width__lte=18),
                name="loans_funding_seq_width_valid",
            ),
            models.CheckConstraint(
                condition=Q(next_value__gt=0),
                name="loans_funding_seq_next_positive",
            ),
            models.CheckConstraint(
                condition=Q(maximum_value__isnull=True)
                | Q(next_value__lte=F("maximum_value") + 1),
                name="loans_funding_seq_max_valid",
            ),
        ]


class FundingLoan(models.Model):
    workspace = models.ForeignKey(
        "orgs.Company",
        on_delete=models.PROTECT,
        related_name="funding_loans",
    )
    lender = models.ForeignKey(
        "party.Party",
        on_delete=models.PROTECT,
        related_name="funding_loans",
    )
    funding_number = models.CharField(max_length=64)
    state = models.CharField(
        max_length=24,
        choices=enum_choices(FundingLoanState),
        default=FundingLoanState.DRAFT.value,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="funding_loans_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="funding_loans_updated",
    )

    class Meta:
        ordering = ("created_at", "funding_number")
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    state__in=tuple(state.value for state in FundingLoanState)
                ),
                name="loans_funding_state_valid",
            ),
            models.UniqueConstraint(
                fields=("workspace", "funding_number"),
                name="loans_funding_workspace_number_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=("workspace", "state", "created_at"),
                name="loans_fund_state_created_idx",
            ),
            models.Index(
                fields=("lender", "state"),
                name="loans_funding_lender_state_idx",
            ),
        ]

    def clean(self):
        super().clean()
        active_workspace_id = current_tenant_workspace_id()
        if active_workspace_id and self.workspace_id != active_workspace_id:
            raise ValidationError(
                {"workspace": "FundingLoan workspace must match the active tenant."}
            )

    def save(self, *args, **kwargs):
        self.clean()
        return super().save(*args, **kwargs)


class FundingLoanDraftTerms(models.Model):
    funding_loan = models.OneToOneField(
        FundingLoan,
        on_delete=models.CASCADE,
        related_name="draft_terms",
    )
    principal_amount = models.DecimalField(max_digits=18, decimal_places=4)
    monthly_interest_rate = models.DecimalField(max_digits=9, decimal_places=6)
    activated_on = models.DateField()
    maturity_on = models.DateField()
    maximum_funding_ltv_ratio = models.DecimalField(
        max_digits=7,
        decimal_places=6,
        default=Decimal("0.800000"),
    )
    currency_quantum = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        default=Decimal("0.0100"),
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="funding_draft_terms_updated",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(principal_amount__gt=0)
                & Q(monthly_interest_rate__gte=0)
                & Q(maturity_on__gte=F("activated_on"))
                & Q(maximum_funding_ltv_ratio__gt=0)
                & Q(maximum_funding_ltv_ratio__lte=1)
                & Q(currency_quantum__gt=0),
                name="loans_funding_draft_terms_valid",
            ),
        ]


class FundingLoanDraftCollateral(models.Model):
    funding_loan = models.ForeignKey(
        FundingLoan,
        on_delete=models.CASCADE,
        related_name="draft_collateral",
    )
    collateral_item = models.ForeignKey(
        PawnCollateralItem,
        on_delete=models.PROTECT,
        related_name="funding_draft_selections",
    )
    selected_collateral_value = models.DecimalField(max_digits=18, decimal_places=4)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("collateral_item__loan_id", "collateral_item_id")
        constraints = [
            models.UniqueConstraint(
                fields=("funding_loan", "collateral_item"),
                name="loans_funding_draft_item_uniq",
            ),
            models.CheckConstraint(
                condition=Q(selected_collateral_value__gt=0),
                name="loans_funding_draft_item_value_positive",
            ),
        ]


class FundingLoanCancellation(ImmutableEvidenceModel):
    funding_loan = models.OneToOneField(
        FundingLoan,
        on_delete=models.PROTECT,
        related_name="cancellation",
    )
    reason = models.TextField()
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="funding_loan_cancellations",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        super().clean()
        if not str(self.reason or "").strip():
            raise ValidationError({"reason": "A FundingLoan cancellation reason is required."})


class FundingLoanTermsSnapshot(ImmutableEvidenceModel):
    funding_loan = models.OneToOneField(
        FundingLoan,
        on_delete=models.PROTECT,
        related_name="terms_snapshot",
    )
    principal_amount = models.DecimalField(max_digits=18, decimal_places=4)
    monthly_interest_rate = models.DecimalField(max_digits=9, decimal_places=6)
    activated_on = models.DateField(db_index=True)
    maturity_on = models.DateField(db_index=True)
    maximum_funding_ltv_ratio = models.DecimalField(
        max_digits=7,
        decimal_places=6,
        default=Decimal("0.800000"),
    )
    currency_quantum = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        default=Decimal("0.0100"),
    )
    schema_version = models.PositiveSmallIntegerField(default=1)
    fingerprint = models.CharField(max_length=64)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="funding_terms_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(principal_amount__gt=0)
                & Q(monthly_interest_rate__gte=0)
                & Q(maturity_on__gte=F("activated_on"))
                & Q(maximum_funding_ltv_ratio__gt=0)
                & Q(maximum_funding_ltv_ratio__lte=1)
                & Q(currency_quantum__gt=0)
                & Q(schema_version__gt=0),
                name="loans_funding_terms_valid",
            ),
        ]


class FundingLoanEvent(ImmutableEvidenceModel):
    funding_loan = models.ForeignKey(
        FundingLoan,
        on_delete=models.PROTECT,
        related_name="events",
    )
    sequence = models.PositiveIntegerField()
    event_kind = models.CharField(
        max_length=24,
        choices=enum_choices(FundingLoanEventKind),
    )
    operation = models.CharField(max_length=40)
    effective_date = models.DateField(db_index=True)
    principal_amount = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        default=Decimal("0"),
    )
    interest_amount = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        default=Decimal("0"),
    )
    fee_amount = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        default=Decimal("0"),
    )
    request_key = models.CharField(max_length=120)
    request_fingerprint = models.CharField(max_length=64)
    reversal_of = models.OneToOneField(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="reversed_by",
    )
    reason = models.TextField(blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="funding_loan_events",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("funding_loan_id", "sequence")
        constraints = [
            models.UniqueConstraint(
                fields=("funding_loan", "sequence"),
                name="loans_funding_event_sequence_uniq",
            ),
            models.UniqueConstraint(
                fields=("funding_loan", "operation", "request_key"),
                name="loans_funding_event_request_uniq",
            ),
            models.CheckConstraint(
                condition=Q(sequence__gt=0),
                name="loans_funding_event_sequence_positive",
            ),
            models.CheckConstraint(
                condition=Q(principal_amount__gte=0)
                & Q(interest_amount__gte=0)
                & Q(fee_amount__gte=0),
                name="loans_funding_event_amounts_nonnegative",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        event_kind=FundingLoanEventKind.REVERSAL.value,
                        reversal_of__isnull=False,
                    )
                    | (
                        ~Q(event_kind=FundingLoanEventKind.REVERSAL.value)
                        & Q(reversal_of__isnull=True)
                    )
                ),
                name="loans_funding_event_reversal_link",
            ),
        ]
        indexes = [
            models.Index(
                fields=("funding_loan", "effective_date", "sequence"),
                name="loans_funding_event_date_idx",
            ),
            models.Index(
                fields=("funding_loan", "event_kind", "sequence"),
                name="loans_funding_event_kind_idx",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        is_reversal = self.event_kind == FundingLoanEventKind.REVERSAL.value
        if is_reversal and not str(self.reason or "").strip():
            errors["reason"] = "A funding event reversal reason is required."
        if not is_reversal and str(self.reason or "").strip():
            errors["reason"] = "A reason is allowed only for a reversal."
        if self.reversal_of_id and self.funding_loan_id:
            if self.reversal_of.funding_loan_id != self.funding_loan_id:
                errors["reversal_of"] = "Reversal and original must belong to one FundingLoan."
        if errors:
            raise ValidationError(errors)


class FundingPledge(ImmutableEvidenceModel):
    workspace = models.ForeignKey(
        "orgs.Company",
        on_delete=models.PROTECT,
        related_name="funding_pledges",
    )
    funding_loan = models.OneToOneField(
        FundingLoan,
        on_delete=models.PROTECT,
        related_name="pledge",
    )
    effective_date = models.DateField(db_index=True)
    request_key = models.CharField(max_length=120)
    request_fingerprint = models.CharField(max_length=64)
    total_collateral_value = models.DecimalField(max_digits=18, decimal_places=4)
    maximum_funded_amount = models.DecimalField(max_digits=18, decimal_places=4)
    valuation_method = models.CharField(max_length=48)
    valuation_version = models.PositiveSmallIntegerField(default=1)
    valuation_snapshot = models.JSONField(default=dict)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="funding_pledges_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("funding_loan", "request_key"),
                name="loans_funding_pledge_request_uniq",
            ),
            models.CheckConstraint(
                condition=Q(total_collateral_value__gt=0)
                & Q(maximum_funded_amount__gt=0)
                & Q(valuation_version__gt=0),
                name="loans_funding_pledge_values_valid",
            ),
        ]

    def clean(self):
        super().clean()
        if self.funding_loan_id and self.workspace_id:
            if self.funding_loan.workspace_id != self.workspace_id:
                raise ValidationError(
                    {"workspace": "Funding pledge workspace must match its FundingLoan."}
                )


class FundingPledgeItem(models.Model):
    funding_pledge = models.ForeignKey(
        FundingPledge,
        on_delete=models.PROTECT,
        related_name="items",
    )
    collateral_item = models.ForeignKey(
        PawnCollateralItem,
        on_delete=models.PROTECT,
        related_name="funding_pledge_items",
    )
    source_pawn_loan_id = models.PositiveBigIntegerField()
    selected_collateral_value = models.DecimalField(max_digits=18, decimal_places=4)
    valuation_snapshot = models.JSONField(default=dict)
    valuation_fingerprint = models.CharField(max_length=64)
    released_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("funding_pledge", "collateral_item"),
                name="loans_funding_pledge_item_uniq",
            ),
            models.UniqueConstraint(
                fields=("collateral_item",),
                condition=Q(released_at__isnull=True),
                name="loans_funding_active_item_uniq",
            ),
            models.CheckConstraint(
                condition=Q(selected_collateral_value__gt=0),
                name="loans_funding_item_value_positive",
            ),
        ]

    def clean(self):
        super().clean()
        if not self.pk and self.released_at is not None:
            raise ValidationError(
                {"released_at": "A funding pledge item must be created active."}
            )
        if self.collateral_item_id and self.source_pawn_loan_id:
            if self.collateral_item.loan_id != self.source_pawn_loan_id:
                raise ValidationError(
                    {"source_pawn_loan_id": "Source PawnLoan must own the collateral item."}
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.pk:
            original = type(self).objects.get(pk=self.pk)
            changed_fields = {
                field.attname
                for field in self._meta.concrete_fields
                if getattr(original, field.attname) != getattr(self, field.attname)
            }
            if changed_fields - {"released_at"}:
                raise ValidationError("Funding pledge item snapshots are immutable.")
            if original.released_at == self.released_at:
                raise ValidationError("Funding pledge release state must change.")
            if original.released_at is None and self.released_at is not None:
                has_return = self.return_items.filter(
                    funding_return__reversal__isnull=True
                ).exists()
                has_pledge_reversal = hasattr(self.funding_pledge, "reversal")
                if not (has_return or has_pledge_reversal):
                    raise ValidationError(
                        "Funding pledge release requires return or reversal evidence."
                    )
            elif original.released_at is not None and self.released_at is None:
                has_return_reversal = self.return_items.filter(
                    funding_return__reversal__isnull=False
                ).exists()
                if not has_return_reversal:
                    raise ValidationError(
                        "Funding pledge reactivation requires return reversal evidence."
                    )
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Funding pledge items cannot be deleted.")


class FundingReturn(ImmutableEvidenceModel):
    workspace = models.ForeignKey(
        "orgs.Company",
        on_delete=models.PROTECT,
        related_name="funding_returns",
    )
    funding_loan = models.ForeignKey(
        FundingLoan,
        on_delete=models.PROTECT,
        related_name="returns",
    )
    effective_date = models.DateField(db_index=True)
    operation = models.CharField(max_length=40, default="RETURN_COLLATERAL")
    request_key = models.CharField(max_length=120)
    request_fingerprint = models.CharField(max_length=64)
    principal_outstanding = models.DecimalField(max_digits=18, decimal_places=4)
    retained_collateral_value = models.DecimalField(max_digits=18, decimal_places=4)
    retained_ltv_ratio = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )
    evidence_snapshot = models.JSONField(default=dict)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="funding_returns_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("funding_loan", "operation", "request_key"),
                name="loans_funding_return_request_uniq",
            ),
            models.CheckConstraint(
                condition=Q(principal_outstanding__gte=0)
                & Q(retained_collateral_value__gte=0)
                & (
                    Q(retained_ltv_ratio__isnull=True)
                    | (
                        Q(retained_ltv_ratio__gte=0)
                        & Q(retained_ltv_ratio__lte=1)
                    )
                ),
                name="loans_funding_return_values_valid",
            ),
        ]

    def clean(self):
        super().clean()
        if self.funding_loan_id and self.workspace_id:
            if self.funding_loan.workspace_id != self.workspace_id:
                raise ValidationError(
                    {"workspace": "Funding return workspace must match its FundingLoan."}
                )


class FundingReturnItem(ImmutableEvidenceModel):
    funding_return = models.ForeignKey(
        FundingReturn,
        on_delete=models.PROTECT,
        related_name="items",
    )
    pledge_item = models.ForeignKey(
        FundingPledgeItem,
        on_delete=models.PROTECT,
        related_name="return_items",
    )
    returned_at = models.DateTimeField(default=timezone.now)
    evidence_snapshot = models.JSONField(default=dict)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("funding_return", "pledge_item"),
                name="loans_funding_return_item_uniq",
            ),
        ]

    def clean(self):
        super().clean()
        if self.funding_return_id and self.pledge_item_id:
            if (
                self.pledge_item.funding_pledge.funding_loan_id
                != self.funding_return.funding_loan_id
            ):
                raise ValidationError(
                    {"pledge_item": "Returned pledge item must belong to the FundingLoan."}
                )


class FundingPledgeReversal(ImmutableEvidenceModel):
    funding_pledge = models.OneToOneField(
        FundingPledge,
        on_delete=models.PROTECT,
        related_name="reversal",
    )
    effective_date = models.DateField(db_index=True)
    request_key = models.CharField(max_length=120)
    request_fingerprint = models.CharField(max_length=64)
    reason = models.TextField()
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="funding_pledge_reversals_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("funding_pledge", "request_key"),
                name="loans_funding_pledge_reversal_request_uniq",
            ),
        ]

    def clean(self):
        super().clean()
        if not str(self.reason or "").strip():
            raise ValidationError({"reason": "A funding pledge reversal reason is required."})


class FundingReturnReversal(ImmutableEvidenceModel):
    funding_return = models.OneToOneField(
        FundingReturn,
        on_delete=models.PROTECT,
        related_name="reversal",
    )
    effective_date = models.DateField(db_index=True)
    request_key = models.CharField(max_length=120)
    request_fingerprint = models.CharField(max_length=64)
    reason = models.TextField()
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="funding_return_reversals_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("funding_return", "request_key"),
                name="loans_funding_return_reversal_request_uniq",
            ),
        ]

    def clean(self):
        super().clean()
        if not str(self.reason or "").strip():
            raise ValidationError({"reason": "A funding return reversal reason is required."})
