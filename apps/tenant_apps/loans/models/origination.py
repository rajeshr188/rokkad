from django.conf import settings
from django.db import models
from django.core.validators import MaxValueValidator
from django.core.exceptions import ValidationError
from apps.tenancy.models import WorkspaceOwnedModel


class LoanEntryPreference(WorkspaceOwnedModel):
    """Current screen default; never an agreement term or lending authority."""

    license = models.ForeignKey(
        "loans.LoanLicense", null=True, blank=True, on_delete=models.PROTECT
    )
    series = models.ForeignKey(
        "loans.LoanSeries", null=True, blank=True, on_delete=models.PROTECT
    )
    purpose = models.CharField(
        max_length=12,
        choices=(
            ("INHERIT", "Follow broader default"),
            ("DIRECT", "Create and pay now"),
            ("PAPER", "Record from paper"),
        ),
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("workspace", "license", "series"),
                nulls_distinct=False,
                name="loans_entry_preference_scope_uniq",
            ),
            models.CheckConstraint(
                condition=models.Q(purpose__in=("INHERIT", "DIRECT", "PAPER")),
                name="loans_entry_preference_purpose",
            ),
            models.CheckConstraint(
                condition=models.Q(series__isnull=True)
                | models.Q(license__isnull=False),
                name="loans_entry_preference_series_scope",
            ),
        ]

    def clean(self):
        super().clean()
        if self.license_id and self.license.workspace_id != self.workspace_id:
            raise ValidationError("Choose a licence in this Workspace.")
        if self.series_id and (
            self.series.workspace_id != self.workspace_id
            or self.series.license_id != self.license_id
        ):
            raise ValidationError(
                "Choose a register under the selected licence in this Workspace."
            )


class LoanOriginationSettings(WorkspaceOwnedModel):
    """Workspace choices; the applied rule is frozen at approval."""

    require_collateral_photos = models.BooleanField(default=False)
    maximum_quote_age_days = models.PositiveSmallIntegerField(
        default=7, validators=[MaxValueValidator(32767)]
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("workspace",), name="loans_origination_settings_ws_uniq"
            ),
            models.CheckConstraint(
                condition=models.Q(maximum_quote_age_days__lte=32767),
                name="loans_origination_quote_age_range",
            ),
        ]
