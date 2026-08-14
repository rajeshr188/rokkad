from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.tenant_apps.loans.domain import PawnLoanNoticeChannel
from .core import current_tenant_workspace_id, enum_choices


class PawnLoanCommunicationConsent(models.Model):
    """Explicit Party consent for PawnLoan service notices on one channel."""

    workspace = models.ForeignKey("orgs.Company", on_delete=models.PROTECT, related_name="pawn_loan_communication_consents")
    party = models.ForeignKey("party.Party", on_delete=models.PROTECT, related_name="pawn_loan_communication_consents")
    channel = models.CharField(max_length=16, choices=enum_choices(PawnLoanNoticeChannel))
    service_notices_allowed = models.BooleanField(default=False)
    opted_out_at = models.DateTimeField(null=True, blank=True)
    evidence = models.CharField(max_length=255, blank=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="pawn_loan_communication_consents_updated")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("workspace", "party", "channel"), name="loans_pawn_notice_consent_uniq")]

    def clean(self):
        workspace_id = current_tenant_workspace_id()
        if workspace_id and self.workspace_id != workspace_id:
            raise ValidationError("Communication consent must belong to the active workspace.")

    @property
    def permits_service_notice(self):
        return self.service_notices_allowed and self.opted_out_at is None

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class PawnLoanCommunicationPolicy(models.Model):
    """One workspace policy for manual PawnLoan borrower communication."""

    workspace = models.OneToOneField(
        "orgs.Company", on_delete=models.PROTECT, related_name="pawn_loan_communication_policy"
    )
    preferred_channel = models.CharField(
        max_length=16,
        choices=(("EMAIL", "Email"), ("WHATSAPP", "WhatsApp")),
        default="EMAIL",
    )
    quiet_hours_start = models.TimeField(null=True, blank=True)
    quiet_hours_end = models.TimeField(null=True, blank=True)
    cooldown_days = models.PositiveSmallIntegerField(default=0)
    escalation_dpd = models.PositiveSmallIntegerField(default=30)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="pawn_loan_communication_policies_updated",
    )
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        workspace_id = current_tenant_workspace_id()
        if workspace_id and self.workspace_id != workspace_id:
            raise ValidationError("Communication policy must belong to the active workspace.")
        if bool(self.quiet_hours_start) != bool(self.quiet_hours_end):
            raise ValidationError("Quiet hours require both start and end times.")
        if self.quiet_hours_start and self.quiet_hours_start == self.quiet_hours_end:
            raise ValidationError("Quiet-hours start and end must differ.")
        if self.cooldown_days > 90:
            raise ValidationError("Cooldown cannot exceed 90 days.")
        if not 1 <= self.escalation_dpd <= 365:
            raise ValidationError("Escalation DPD must be between 1 and 365 days.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
