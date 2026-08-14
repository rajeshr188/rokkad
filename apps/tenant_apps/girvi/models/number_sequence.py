from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class GirviNumberSequence(models.Model):
    class DocumentKind(models.TextChoices):
        GIVEN_LOAN = "GIVEN_LOAN", _("Given Loan")
        TAKEN_LOAN = "TAKEN_LOAN", _("Taken Loan")
        GIVEN_LOAN_RELEASE = "GIVEN_LOAN_RELEASE", _("Given Loan Release")
        TAKEN_LOAN_SETTLEMENT = "TAKEN_LOAN_SETTLEMENT", _("Taken Loan Settlement")

    series = models.ForeignKey(
        "girvi.Series",
        on_delete=models.CASCADE,
        related_name="number_sequences",
    )
    document_kind = models.CharField(max_length=32, choices=DocumentKind.choices)
    prefix = models.CharField(max_length=16)
    width = models.PositiveIntegerField(default=5)
    next_number = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    last_allocated_number = models.PositiveIntegerField(null=True, blank=True)
    last_allocated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="girvi_number_sequences_updated",
    )
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ("series_id", "document_kind")
        constraints = [
            models.UniqueConstraint(
                fields=["series", "document_kind"],
                name="unique_girvi_number_sequence_per_kind",
            ),
            models.CheckConstraint(
                condition=models.Q(width__gt=0),
                name="girvi_number_sequence_width_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(next_number__gt=0),
                name="girvi_number_sequence_next_positive",
            ),
        ]
        indexes = [
            models.Index(fields=["document_kind", "is_active"]),
            models.Index(fields=["series", "document_kind", "is_active"]),
        ]

    def __str__(self):
        return f"{self.series} {self.document_kind}: {self.preview_value}"

    @property
    def preview_value(self):
        return self.format_number(self.next_number)

    def format_number(self, number):
        return f"{self.prefix}{int(number):0{self.width}d}"

    def mark_allocated(self, allocated_number, *, updated_by=None):
        self.last_allocated_number = allocated_number
        self.last_allocated_at = timezone.now()
        self.next_number = allocated_number + 1
        if updated_by is not None:
            self.updated_by = updated_by
        self.save(
            update_fields=[
                "last_allocated_number",
                "last_allocated_at",
                "next_number",
                "updated_by",
                "updated_at",
            ]
        )
