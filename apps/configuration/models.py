from django.conf import settings
from django.db import models
from dynamic_preferences.models import PerInstancePreferenceModel


class WorkspacePreferenceModel(PerInstancePreferenceModel):
    instance = models.ForeignKey(
        "orgs.Company",
        related_name="configuration_preferences",
        on_delete=models.CASCADE,
    )

    class Meta(PerInstancePreferenceModel.Meta):
        app_label = "configuration"
        verbose_name = "workspace preference"
        verbose_name_plural = "workspace preferences"


class PreferenceAuditLog(models.Model):
    class Scope(models.TextChoices):
        GLOBAL = "global", "Global"
        WORKSPACE = "workspace", "Workspace"
        USER = "user", "User"

    scope = models.CharField(max_length=20, choices=Scope.choices)
    key = models.CharField(max_length=300, db_index=True)
    old_value = models.TextField(blank=True, null=True)
    new_value = models.TextField(blank=True, null=True)
    workspace = models.ForeignKey(
        "orgs.Company",
        related_name="preference_audit_logs",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
    )
    subject_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="preference_audit_subjects",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="preference_audit_changes",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "configuration"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["scope", "key"]),
            models.Index(fields=["workspace", "scope"]),
            models.Index(fields=["subject_user", "scope"]),
        ]

    def __str__(self):
        return f"{self.scope}:{self.key}"
