"""Preserved administrative lists; never auction or postal-service authority."""
from django.core.exceptions import ValidationError
from django.db import models

from .statutory import StatutoryImmutableModel


class AuctioneerHandover(StatutoryImmutableModel):
    license = models.ForeignKey('loans.LoanLicense', on_delete=models.PROTECT, related_name='+')
    title = models.CharField(max_length=160)
    auctioneer = models.CharField(max_length=200)
    loan_ids = models.JSONField()
    request_key = models.CharField(max_length=64)

    class Meta:
        constraints = [models.UniqueConstraint(fields=('workspace', 'request_key'), name='loans_handover_request_uniq')]

    def clean(self):
        if self.license_id and self.license.workspace_id != self.workspace_id:
            raise ValidationError('Handover licence must belong to this Workspace.')

    @property
    def reference(self):
        return f'AH-{self.pk}'


class AuctioneerHandoverRevision(StatutoryImmutableModel):
    handover = models.ForeignKey(AuctioneerHandover, on_delete=models.PROTECT, related_name='revisions')
    number = models.PositiveIntegerField()
    snapshot = models.JSONField()
    snapshot_sha256 = models.CharField(max_length=64)
    request_key = models.CharField(max_length=64)
    request_sha256 = models.CharField(max_length=64)

    class Meta:
        ordering = ('number',)
        constraints = [
            models.UniqueConstraint(fields=('handover', 'number'), name='loans_handover_revision_uniq'),
            models.UniqueConstraint(fields=('workspace', 'request_key'), name='loans_handover_revision_req_uniq'),
        ]

    def clean(self):
        if self.handover_id and self.handover.workspace_id != self.workspace_id:
            raise ValidationError('Revision must belong to the handover Workspace.')
