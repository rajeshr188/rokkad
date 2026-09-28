from django.conf import settings
from django.db import models
from apps.tenancy.models import WorkspaceOwnedModel


class LoanOriginationSettings(WorkspaceOwnedModel):
    """Workspace choices; the applied rule is frozen at approval."""
    require_collateral_photos = models.BooleanField(default=False)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("workspace",), name="loans_origination_settings_ws_uniq")]
