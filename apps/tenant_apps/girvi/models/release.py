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

    # fixed a critical bug here where the release_id was not being generated correctly due to empty series name not being distinguishedfrom other series name
    # this is probably better way to generate release_id suggested by chatgpt
    # def generate_release_id(self, series):
    #     default_prefix = 'RL'  # Define a default prefix
    #     delimiter = '-'  # Define a delimiter to separate the prefix and the sequence number

    #     # Use the series name if it's not empty, otherwise use the default prefix
    #     prefix = series.name if series.name else default_prefix

    #     with transaction.atomic():
    #         last_release = (
    #             Release.objects.filter(loan__series__name=series.name)
    #             .order_by("-release_id")
    #             .select_for_update()
    #             .first()
    #         )
    #         if last_release:
    #             release_id = last_release.release_id
    #             # Extract the sequence number
    #             match = re.match(rf"^{re.escape(prefix)}{re.escape(delimiter)}(\d+)$", release_id)
    #             if match:
    #                 sequence_number = int(match.group(1)) + 1
    #             else:
    #                 sequence_number = 1
    #         else:
    #             sequence_number = 1

    #         new_release_id = f"{prefix}{delimiter}{sequence_number:0{series.max_limit}d}"
    #         return new_release_id

    def generate_release_id(self, series):
        print("series name", series.name)
        with transaction.atomic():
            last_release = (
                Release.objects.filter(loan__series__name=series.name)
                .order_by("-release_id")
                .select_for_update()
                .first()
            )
            print("last_release", last_release)
            if last_release:
                release_id = last_release.release_id
                print("release_id", release_id)
                # Extract the sequence number
                match = re.match(rf"^{re.escape(series.name)}(\d+)$", release_id)
                print("match", match)
                if match:
                    print("match.group(1)", match.group(1))
                    sequence_number = int(match.group(1)) + 1
                else:
                    print("else")
                    sequence_number = 1
            else:
                print("no last release")
                sequence_number = 1

            new_release_id = f"{series.name}{sequence_number:0{series.max_limit}d}"
            print("new_release_id", new_release_id)
            return new_release_id

    def save(self, *args, **kwargs):
        if not self.release_id:
            self.release_id = self.generate_release_id(series=self.loan.series)
        super().save(*args, **kwargs)


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
