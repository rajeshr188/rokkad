from django.core.exceptions import ValidationError
from django.db import models

from .context import current_workspace_id


class WorkspaceOwnedModel(models.Model):
    """Base for every row isolated by Workspace in the shared schema."""

    workspace = models.ForeignKey(
        "orgs.Company",
        on_delete=models.PROTECT,
        related_name="+",
        editable=False,
    )

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        active_workspace_id = current_workspace_id()
        if self.workspace_id is None:
            if active_workspace_id is None:
                raise ValidationError("An explicit Workspace context is required.")
            self.workspace_id = active_workspace_id
        elif (
            active_workspace_id is not None
            and self.workspace_id != active_workspace_id
        ):
            raise ValidationError("Object Workspace conflicts with active context.")
        super().save(*args, **kwargs)
