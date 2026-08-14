import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from .core import current_tenant_workspace_id


class PawnStorageLocation(models.Model):
    class Level(models.TextChoices):
        BRANCH = "BRANCH", "Branch"
        VAULT = "VAULT", "Vault"
        CABINET = "CABINET", "Cabinet"
        BOX = "BOX", "Box"
        SLOT = "SLOT", "Slot"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    workspace = models.ForeignKey(
        "orgs.Company",
        on_delete=models.PROTECT,
        related_name="pawn_storage_locations",
    )
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
    )
    level = models.CharField(max_length=12, choices=Level.choices)
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=100)
    capacity = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pawn_storage_locations_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("level", "code", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("workspace", "code"),
                name="loans_storage_workspace_code_uniq",
            ),
            models.CheckConstraint(
                condition=Q(capacity__isnull=True) | Q(capacity__gt=0),
                name="loans_storage_capacity_positive",
            ),
        ]
        indexes = [
            models.Index(
                fields=("workspace", "level", "is_active"),
                name="loans_storage_level_active_idx",
            )
        ]

    def clean(self):
        super().clean()
        tenant_id = current_tenant_workspace_id()
        if tenant_id and self.workspace_id != tenant_id:
            raise ValidationError({"workspace": "Storage location must belong to the active workspace."})
        expected_parent = {
            self.Level.BRANCH: None,
            self.Level.VAULT: self.Level.BRANCH,
            self.Level.CABINET: self.Level.VAULT,
            self.Level.BOX: self.Level.CABINET,
            self.Level.SLOT: self.Level.BOX,
        }[self.level]
        if expected_parent is None and self.parent_id:
            raise ValidationError({"parent": "A Branch cannot have a parent."})
        if expected_parent is not None:
            if not self.parent_id or self.parent.level != expected_parent:
                raise ValidationError(
                    {"parent": f"A {self.get_level_display()} requires a {self.Level(expected_parent).label} parent."}
                )
            if self.parent.workspace_id != self.workspace_id:
                raise ValidationError({"parent": "Parent location must belong to this workspace."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def path_label(self):
        nodes = [self]
        current = self.parent
        while current is not None:
            nodes.append(current)
            current = current.parent
        return " / ".join(node.code for node in reversed(nodes))

    def __str__(self):
        return f"{self.code} · {self.name}"


class PawnCollateralStorageMovement(models.Model):
    class Kind(models.TextChoices):
        PLACEMENT = "PLACEMENT", "Initial placement"
        TRANSFER = "TRANSFER", "Storage transfer"
        REMOVAL = "REMOVAL", "Workflow removal"

    collateral_item = models.ForeignKey(
        "loans.PawnCollateralItem",
        on_delete=models.PROTECT,
        related_name="storage_movements",
    )
    from_location = models.ForeignKey(
        PawnStorageLocation,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="outbound_movements",
    )
    to_location = models.ForeignKey(
        PawnStorageLocation,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="inbound_movements",
    )
    kind = models.CharField(max_length=12, choices=Kind.choices)
    reason = models.CharField(max_length=500, blank=True)
    workflow_source = models.CharField(max_length=64, default="OPERATOR")
    source_reference = models.CharField(max_length=120, blank=True)
    moved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pawn_storage_movements_recorded",
    )
    moved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("collateral_item_id", "moved_at", "id")
        constraints = [
            models.CheckConstraint(
                condition=~(
                    Q(from_location__isnull=True) & Q(to_location__isnull=True)
                ),
                name="loans_storage_movement_has_endpoint",
            ),
            models.CheckConstraint(
                condition=(
                    Q(from_location__isnull=True)
                    | Q(to_location__isnull=True)
                    | ~Q(from_location=models.F("to_location"))
                ),
                name="loans_storage_movement_changes",
            ),
        ]
        indexes = [
            models.Index(
                fields=("collateral_item", "moved_at"),
                name="loans_storage_item_time_idx",
            )
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Collateral storage movements are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Collateral storage movements cannot be deleted.")
