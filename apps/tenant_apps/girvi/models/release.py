import re

from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models, transaction
from django.shortcuts import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from moneyed import Money

from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.dea.models import JournalEntry

from ..models import LoanPayment


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
        "girvi.Loan", on_delete=models.CASCADE, related_name="release"
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

    def generate_release_id(self, series):
        with transaction.atomic():
            last_release = (
                Release.objects.filter(release_id__startswith=series.name)
                .order_by("-release_id")
                .select_for_update()
                .first()
            )
            if last_release:
                release_id = last_release.release_id
                # Extract the sequence number
                match = re.match(rf"^{re.escape(series.name)}(\d+)$", release_id)
                if match:
                    sequence_number = int(match.group(1)) + 1
                else:
                    sequence_number = 1
            else:
                sequence_number = 1

            new_release_id = f"{series.name}{sequence_number:0{series.max_limit}d}"
            return new_release_id

    def save(self, *args, **kwargs):
        if not self.release_id:
            self.release_id = self.generate_release_id(self.loan.series)
        super().save(*args, **kwargs)
