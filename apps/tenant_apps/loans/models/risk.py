from django.db import models
from django.db.models import Q
from django.core.exceptions import ValidationError


class LoanRiskSnapshot(models.Model):
    class Status(models.TextChoices):
        CURRENT = "CURRENT", "Current"
        STALE = "STALE", "Stale"
        ERROR = "ERROR", "Error"

    workspace = models.ForeignKey("orgs.Company", on_delete=models.CASCADE, related_name="loan_risk_snapshots")
    loan = models.OneToOneField("loans.PawnLoan", on_delete=models.CASCADE, related_name="risk_snapshot")
    as_of_date = models.DateField()
    exposure = models.DecimalField(max_digits=18, decimal_places=4, null=True)
    due = models.DecimalField(max_digits=18, decimal_places=4, null=True)
    overdue = models.DecimalField(max_digits=18, decimal_places=4, null=True)
    days_past_due = models.PositiveIntegerField(null=True)
    days_to_maturity = models.IntegerField(null=True)
    collateral_value = models.DecimalField(max_digits=18, decimal_places=4, null=True)
    ltv_ratio = models.DecimalField(max_digits=12, decimal_places=8, null=True)
    performance_class = models.CharField(max_length=24, blank=True)
    severity = models.CharField(max_length=16, blank=True)
    action_hint = models.CharField(max_length=32, blank=True)
    flags = models.JSONField(default=list)
    explanations = models.JSONField(default=list)
    policy_identity = models.CharField(max_length=255, blank=True)
    source_provenance = models.JSONField(default=dict)
    assessment_fingerprint = models.CharField(max_length=64, blank=True)
    input_fingerprint = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.STALE, db_index=True)
    error_message = models.TextField(blank=True)
    assessed_at = models.DateTimeField(null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("workspace", "loan"), name="loans_risk_snapshot_workspace_loan_uniq"),
            models.CheckConstraint(condition=Q(status="ERROR") | ~Q(assessment_fingerprint=""), name="loans_risk_current_has_assessment"),
        ]
        indexes = [
            models.Index(fields=("workspace", "status", "severity"), name="loans_risk_portfolio_idx"),
            models.Index(fields=("workspace", "days_past_due", "ltv_ratio"), name="loans_risk_metrics_idx"),
        ]


class LoanRiskEvent(models.Model):
    workspace = models.ForeignKey("orgs.Company", on_delete=models.PROTECT, related_name="loan_risk_events")
    loan = models.ForeignKey("loans.PawnLoan", on_delete=models.PROTECT, related_name="risk_events")
    snapshot = models.ForeignKey(LoanRiskSnapshot, on_delete=models.PROTECT, related_name="transition_events")
    event_type = models.CharField(max_length=40)
    occurred_at = models.DateTimeField(auto_now_add=True)
    as_of_date = models.DateField()
    old_value = models.JSONField(default=dict)
    new_value = models.JSONField(default=dict)
    old_fingerprint = models.CharField(max_length=64, blank=True)
    new_fingerprint = models.CharField(max_length=64, blank=True)
    policy_identity = models.CharField(max_length=255, blank=True)
    trigger_key = models.CharField(max_length=64)
    metadata = models.JSONField(default=dict)

    class Meta:
        ordering = ("occurred_at", "pk")
        constraints = [models.UniqueConstraint(fields=("workspace", "loan", "trigger_key"), name="loans_risk_event_trigger_uniq")]
        indexes = [models.Index(fields=("workspace", "as_of_date", "event_type"), name="loans_risk_event_portfolio_idx")]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("LoanRiskEvent is immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("LoanRiskEvent is immutable.")


class LoanRiskAlert(models.Model):
    class Kind(models.TextChoices):
        DPD_WORSENING = "DPD_WORSENING", "Worsening delinquency"
        LTV_BREACH = "LTV_BREACH", "LTV breach"
        MATURITY = "MATURITY", "Maturity attention"
        ASSESSMENT_FAILURE = "ASSESSMENT_FAILURE", "Assessment failure"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        RESOLVED = "RESOLVED", "Resolved"

    workspace = models.ForeignKey(
        "orgs.Company", on_delete=models.PROTECT, related_name="loan_risk_alerts"
    )
    loan = models.ForeignKey(
        "loans.PawnLoan", on_delete=models.PROTECT, related_name="risk_alerts"
    )
    source_event = models.ForeignKey(
        LoanRiskEvent, on_delete=models.PROTECT, related_name="operational_alerts"
    )
    resolved_by_event = models.ForeignKey(
        LoanRiskEvent, null=True, blank=True, on_delete=models.PROTECT,
        related_name="resolved_operational_alerts",
    )
    alert_kind = models.CharField(max_length=24, choices=Kind.choices)
    severity = models.CharField(max_length=16)
    message = models.CharField(max_length=500)
    recommended_action = models.CharField(max_length=255)
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.OPEN, db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at", "-pk")
        constraints = [
            models.UniqueConstraint(
                fields=("source_event", "alert_kind"),
                name="loans_risk_alert_event_kind_uniq",
            ),
            models.UniqueConstraint(
                fields=("workspace", "loan", "alert_kind"),
                condition=Q(status="OPEN"),
                name="loans_risk_alert_one_open_kind",
            ),
        ]
        indexes = [
            models.Index(
                fields=("workspace", "status", "severity"),
                name="loans_risk_alert_work_idx",
            )
        ]
