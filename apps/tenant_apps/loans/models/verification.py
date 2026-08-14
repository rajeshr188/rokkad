import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class PawnPhysicalVerificationSession(models.Model):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        COMPLETED = "COMPLETED", "Completed"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    workspace = models.ForeignKey(
        "orgs.Company", on_delete=models.PROTECT, related_name="pawn_verification_sessions"
    )
    scope_location = models.ForeignKey(
        "loans.PawnStorageLocation",
        on_delete=models.PROTECT,
        related_name="verification_sessions",
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN)
    started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="pawn_verification_sessions_started",
    )
    started_at = models.DateTimeField(auto_now_add=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pawn_verification_sessions_completed",
    )
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-started_at", "-id")

    def save(self, *args, **kwargs):
        if self.pk:
            original = type(self).objects.get(pk=self.pk)
            allowed = (
                original.status == self.Status.OPEN
                and self.status == self.Status.COMPLETED
                and original.workspace_id == self.workspace_id
                and original.scope_location_id == self.scope_location_id
                and original.public_id == self.public_id
                and original.started_by_id == self.started_by_id
                and original.started_at == self.started_at
            )
            if not allowed:
                raise ValidationError("Verification sessions are immutable except for completion.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Verification sessions cannot be deleted.")


class PawnPhysicalVerificationExpectation(models.Model):
    session = models.ForeignKey(
        PawnPhysicalVerificationSession,
        on_delete=models.PROTECT,
        related_name="expectations",
    )
    collateral_item = models.ForeignKey(
        "loans.PawnCollateralItem",
        on_delete=models.PROTECT,
        related_name="verification_expectations",
    )
    expected_location = models.ForeignKey(
        "loans.PawnStorageLocation",
        on_delete=models.PROTECT,
        related_name="verification_expectations",
    )
    custody_state_snapshot = models.CharField(max_length=32)
    loan_number_snapshot = models.CharField(max_length=96)
    item_description_snapshot = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("expected_location_id", "collateral_item_id")
        constraints = [
            models.UniqueConstraint(
                fields=("session", "collateral_item"),
                name="loans_verification_expected_item_uniq",
            )
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Verification expectations are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Verification expectations cannot be deleted.")


class PawnPhysicalVerificationObservation(models.Model):
    class Classification(models.TextChoices):
        FOUND = "FOUND", "Found"
        MISSING = "MISSING", "Missing"
        MISPLACED = "MISPLACED", "Misplaced"
        UNEXPECTED = "UNEXPECTED", "Unexpected"

    session = models.ForeignKey(
        PawnPhysicalVerificationSession,
        on_delete=models.PROTECT,
        related_name="observations",
    )
    expectation = models.OneToOneField(
        PawnPhysicalVerificationExpectation,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="observation",
    )
    collateral_item = models.ForeignKey(
        "loans.PawnCollateralItem",
        on_delete=models.PROTECT,
        related_name="verification_observations",
    )
    classification = models.CharField(max_length=12, choices=Classification.choices)
    observed_location = models.ForeignKey(
        "loans.PawnStorageLocation",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="verification_observations",
    )
    notes = models.CharField(max_length=500, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="pawn_verification_observations_recorded",
    )
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("recorded_at", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("session", "collateral_item"),
                name="loans_verification_observed_item_uniq",
            ),
            models.CheckConstraint(
                condition=(
                    Q(classification="UNEXPECTED", expectation__isnull=True)
                    | (~Q(classification="UNEXPECTED") & Q(expectation__isnull=False))
                ),
                name="loans_verification_unexpected_shape",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Verification observations are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Verification observations cannot be deleted.")


class PawnPhysicalVerificationResolution(models.Model):
    class Outcome(models.TextChoices):
        CONFIRMED_FOUND = "CONFIRMED_FOUND", "Confirmed found"
        LOCATION_CORRECTED = "LOCATION_CORRECTED", "Location corrected"
        LOST_COMPENSATED = "LOST_COMPENSATED", "Lost and compensated"
        DAMAGED = "DAMAGED", "Damaged — release policy deferred"

    observation = models.OneToOneField(
        PawnPhysicalVerificationObservation,
        on_delete=models.PROTECT,
        related_name="resolution",
    )
    outcome = models.CharField(max_length=24, choices=Outcome.choices)
    reason = models.CharField(max_length=500)
    current_market_value = models.DecimalField(
        max_digits=18, decimal_places=2, null=True, blank=True
    )
    agreed_compensation = models.DecimalField(
        max_digits=18, decimal_places=2, null=True, blank=True
    )
    compensation_reference = models.CharField(max_length=120, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="pawn_verification_resolutions_recorded",
    )
    resolved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("resolved_at", "id")

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Verification resolutions are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Verification resolutions cannot be deleted.")
