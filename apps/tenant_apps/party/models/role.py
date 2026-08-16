from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from apps.tenancy.models import WorkspaceOwnedModel


class PartyRoleType(WorkspaceOwnedModel):
    key = models.CharField(max_length=64, db_index=True)
    label = models.CharField(max_length=128)
    description = models.TextField(blank=True)
    is_system = models.BooleanField(default=False, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("sort_order", "label")
        verbose_name = _("Party Role Type")
        verbose_name_plural = _("Party Role Types")
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "key"],
                name="party_role_type_workspace_key_uniq",
            ),
        ]

    def __str__(self):
        return self.label

    def save(self, *args, **kwargs):
        self.key = (self.key or "").strip().upper()
        super().save(*args, **kwargs)


class PartyRole(WorkspaceOwnedModel):
    class RoleStatus(models.TextChoices):
        ACTIVE = "ACTIVE", _("Active")
        INACTIVE = "INACTIVE", _("Inactive")
        ENDED = "ENDED", _("Ended")

    party = models.ForeignKey(
        "party.Party",
        on_delete=models.CASCADE,
        related_name="roles",
    )
    role_type = models.ForeignKey(
        "party.PartyRoleType",
        on_delete=models.PROTECT,
        related_name="party_roles",
    )
    status = models.CharField(
        max_length=16,
        choices=RoleStatus.choices,
        default=RoleStatus.ACTIVE,
        db_index=True,
    )
    segment = models.CharField(
        max_length=64,
        blank=True,
        help_text="Optional role-specific segment such as RETAIL or WHOLESALE.",
    )
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("party", "role_type")
        constraints = [
            models.UniqueConstraint(
                fields=["party", "role_type"],
                condition=Q(status="ACTIVE"),
                name="party_one_active_role_per_type",
            ),
        ]
        indexes = [
            models.Index(fields=["party", "status"]),
            models.Index(fields=["role_type", "status"]),
        ]
        verbose_name = _("Party Role")
        verbose_name_plural = _("Party Roles")

    def __str__(self):
        return f"{self.party} - {self.role_type}"

    def save(self, *args, **kwargs):
        if self.party.workspace_id != self.role_type.workspace_id:
            raise ValidationError("Party role type must belong to the same Workspace.")
        self.workspace_id = self.party.workspace_id
        super().save(*args, **kwargs)
