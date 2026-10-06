from django.conf import settings
from django.db import models
from django.core.validators import MaxValueValidator
from apps.tenancy.models import WorkspaceOwnedModel


class LoanOriginationSettings(WorkspaceOwnedModel):
    """Workspace choices; the applied rule is frozen at approval."""
    require_collateral_photos = models.BooleanField(default=False)
    maximum_quote_age_days = models.PositiveSmallIntegerField(default=7,
        validators=[MaxValueValidator(32767)])
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("workspace",), name="loans_origination_settings_ws_uniq"),
            models.CheckConstraint(condition=models.Q(maximum_quote_age_days__lte=32767),
                name="loans_origination_quote_age_range")]
