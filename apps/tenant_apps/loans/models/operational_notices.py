from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class LoanOperationalNotice(models.Model):
    class Kind(models.TextChoices):
        LICENSE_EXPIRY = "LICENSE_EXPIRY", "Regulatory license expiry"
        VERIFICATION_DISCREPANCY = (
            "VERIFICATION_DISCREPANCY",
            "Physical-verification discrepancy",
        )

    workspace = models.ForeignKey(
        "orgs.Company",
        on_delete=models.PROTECT,
        related_name="loan_operational_notices",
    )
    notice_kind = models.CharField(max_length=32, choices=Kind.choices)
    request_key = models.CharField(max_length=120)
    scheduled_for = models.DateTimeField(db_index=True)
    recipient_name = models.CharField(max_length=255)
    recipient_email = models.EmailField()
    payload_snapshot = models.JSONField(default=dict)
    notification_event_id = models.PositiveBigIntegerField(null=True, blank=True)
    notification_job_id = models.PositiveBigIntegerField(null=True, blank=True)
    source_license = models.ForeignKey(
        "loans.LoanLicense",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="operational_notices",
    )
    source_verification_observation = models.ForeignKey(
        "loans.PawnPhysicalVerificationObservation",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="operational_notices",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="loan_operational_notices_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("workspace", "request_key"),
                name="loans_operational_notice_request_uniq",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        notice_kind="LICENSE_EXPIRY",
                        source_license__isnull=False,
                        source_verification_observation__isnull=True,
                    )
                    | Q(
                        notice_kind="VERIFICATION_DISCREPANCY",
                        source_license__isnull=True,
                        source_verification_observation__isnull=False,
                    )
                ),
                name="loans_operational_notice_source_shape",
            ),
        ]
        indexes = [
            models.Index(
                fields=("workspace", "scheduled_for"),
                name="loans_oper_notice_due_idx",
            )
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Operational notice intents are immutable.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Operational notice intents cannot be deleted.")
