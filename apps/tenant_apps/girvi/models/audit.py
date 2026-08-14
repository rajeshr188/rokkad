from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone


class LoanChangeLog(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    loan = GenericForeignKey("content_type", "object_id")

    changed = models.DateTimeField(default=timezone.now)
    source = models.CharField(max_length=255)
    target = models.CharField(max_length=255)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    diff = models.TextField()
    notes = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-changed"]
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
        ]

    def __str__(self):
        loan_id = getattr(self.loan, "loan_id", "Unknown")
        return f"{loan_id} - {self.source} -> {self.target}"
