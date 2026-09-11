from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

from .core import current_tenant_workspace_id


class LoanMonitoringPolicy(models.Model):
    workspace = models.ForeignKey("orgs.Company", on_delete=models.PROTECT, related_name="loan_monitoring_policies")
    license = models.ForeignKey("loans.LoanLicense", null=True, blank=True, on_delete=models.PROTECT, related_name="monitoring_policies")
    version = models.PositiveIntegerField()
    effective_from = models.DateField()
    effective_until = models.DateField(null=True, blank=True)
    supersedes = models.OneToOneField("self", null=True, blank=True, on_delete=models.PROTECT, related_name="successor")
    amendment_reason = models.TextField(blank=True)
    compliance_profile = models.CharField(max_length=120)
    maturity_warning_days = models.PositiveSmallIntegerField(default=30)
    operational_grace_days = models.PositiveSmallIntegerField(default=3)
    dpd_watch_threshold = models.PositiveSmallIntegerField(default=1)
    dpd_substandard_threshold = models.PositiveSmallIntegerField(default=90)
    ltv_warning_ratio = models.DecimalField(max_digits=7, decimal_places=6)
    ltv_breach_ratio = models.DecimalField(max_digits=7, decimal_places=6)
    ltv_critical_ratio = models.DecimalField(max_digits=7, decimal_places=6)
    rate_freshness_days = models.PositiveSmallIntegerField(default=7)
    appraisal_freshness_days = models.PositiveSmallIntegerField(default=90)
    eligible_custody_states = models.JSONField(default=list)
    severity_mapping = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="loan_monitoring_policies_created")

    class Meta:
        ordering = ("workspace_id", "license_id", "effective_from", "version")
        constraints = [
            models.UniqueConstraint(fields=("workspace", "license", "version"), name="loans_monitor_policy_scope_version_uniq", nulls_distinct=False),
            models.CheckConstraint(condition=Q(effective_until__isnull=True) | Q(effective_until__gte=F("effective_from")), name="loans_monitor_policy_dates_valid"),
            models.CheckConstraint(condition=Q(ltv_warning_ratio__gt=0) & Q(ltv_warning_ratio__lte=1), name="loans_monitor_ltv_warning_range"),
            models.CheckConstraint(condition=Q(ltv_breach_ratio__gt=0) & Q(ltv_breach_ratio__lte=1), name="loans_monitor_ltv_breach_range"),
            models.CheckConstraint(condition=Q(ltv_critical_ratio__gt=0), name="loans_monitor_ltv_critical_positive"),
        ]
        indexes = [models.Index(fields=("workspace", "license", "effective_from", "effective_until"), name="loans_monitor_policy_asof_idx")]

    def clean(self):
        errors = {}
        if current_tenant_workspace_id() and self.workspace_id != current_tenant_workspace_id():
            errors["workspace"] = "Monitoring policy must belong to the active workspace."
        if self.license_id and self.license.workspace_id != self.workspace_id:
            errors["license"] = "License override must belong to the policy workspace."
        if (all(value is not None for value in (self.ltv_warning_ratio, self.ltv_breach_ratio, self.ltv_critical_ratio))
                and not self.ltv_warning_ratio <= self.ltv_breach_ratio <= self.ltv_critical_ratio):
            errors["ltv_breach_ratio"] = "LTV thresholds must be ordered warning, breach, critical."
        if (self.dpd_watch_threshold is not None and self.dpd_substandard_threshold is not None
                and self.dpd_watch_threshold > self.dpd_substandard_threshold):
            errors["dpd_substandard_threshold"] = "DPD thresholds must be ordered."
        if self.workspace_id and self.effective_from:
            ancestors = set()
            prior = self.supersedes if self.supersedes_id else None
            if prior:
                if (prior.workspace_id != self.workspace_id or prior.license_id != self.license_id
                        or prior.effective_until is not None or self.effective_until is not None
                        or self.effective_from < prior.effective_from):
                    errors["supersedes"] = "Amend the latest open-ended policy in the same scope, from its start date or later."
                if not self.created_by_id or not self.amendment_reason.strip():
                    errors["amendment_reason"] = "An amendment requires its author and reason."
                while prior and prior.pk not in ancestors:
                    ancestors.add(prior.pk)
                    prior = prior.supersedes
            overlaps = type(self).objects.filter(
                workspace_id=self.workspace_id,
                license_id=self.license_id,
            ).exclude(pk=self.pk).exclude(pk__in=ancestors).filter(
                Q(effective_until__isnull=True) | Q(effective_until__gte=self.effective_from)
            )
            if self.effective_until:
                overlaps = overlaps.filter(effective_from__lte=self.effective_until)
            if overlaps.exists():
                errors["effective_from"] = "Monitoring policy periods cannot overlap within a scope."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("LoanMonitoringPolicy is immutable; create a new version.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("LoanMonitoringPolicy is immutable and cannot be deleted.")
