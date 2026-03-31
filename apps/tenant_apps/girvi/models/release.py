import logging

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.shortcuts import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.girvi.services import ReleaseIDGenerator
from apps.tenant_apps.girvi.payment_service import record_loan_release

logger = logging.getLogger(__name__)


class ReleaseManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().select_related("loan")


class Release(models.Model):
    # Fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    release_date = models.DateTimeField(default=timezone.now)
    release_id = models.CharField(
        max_length=255, unique=True, null=True, blank=True, verbose_name=_("Release ID")
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.DO_NOTHING,
        null=True,
        verbose_name=_("Created By"),
        related_name="releases_created",
    )
    released_by = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL,
        related_name="released_by",
        null=True,
        blank=True,
        verbose_name=_("Released By"),
    )
    # Relationship Fields
    loan = models.OneToOneField(
        "girvi.GivenLoan", on_delete=models.CASCADE, related_name="release"
    )
    objects = ReleaseManager()

    class Meta:
        ordering = ("-id",)

    def __str__(self):
        return f"{self.release_id}"

    def get_absolute_url(self):
        return reverse("girvi:girvi_release_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("girvi:girvi_release_update", args=(self.pk,))

    def save(self, *args, **kwargs):
        is_create = self._state.adding

        if is_create and not self.release_id:
            self.release_id = ReleaseIDGenerator.generate(self.loan.series)

        # Updates should not retrigger lifecycle transitions or accounting posts.
        if not is_create:
            return super().save(*args, **kwargs)

        if not self.created_by:
            raise ValidationError("created_by is required for release creation.")

        with transaction.atomic():
            super().save(*args, **kwargs)

            # Transition the loan status to RELEASED and post release accounting
            # in the same transaction so failure in either step rolls back.
            from ..flows import LoanFlow

            flow = LoanFlow(
                self.loan, self.created_by, self.created_by.profile.workspace
            )
            if not flow.deliver.can_proceed():
                raise ValidationError(
                    f"Loan {self.loan.loan_id} cannot be released in status {self.loan.status}."
                )

            flow.deliver(
                created_by=self.created_by,
                released_by=self.released_by,
                release_date=self.release_date,
            )
            record_loan_release(self, created_by=self.created_by)


# with schema_context(jcl):
#     releases = Release.objects.all().order_by('created_at')

#     # Track processed releases per series
#     series_counters = {}

#     for release in releases:
#         series = release.loan.series
#         series_name = series.name or 'RL'

#         # Initialize counter for new series
#         if series_name not in series_counters:
#             series_counters[series_name] = 1

#         # Generate new release ID
#         new_release_id = f"{series_name}{series_counters[series_name]:0{series.max_limit}d}"

#         # Update counter
#         series_counters[series_name] += 1

#         # Update release ID
#         print(f'Updating release {release.pk}: {release.release_id} → {new_release_id}')
#         release.release_id = new_release_id
#         release.save(update_fields=['release_id'])
