"""Preserved statutory auction notices and append-only handling evidence."""
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django_cleanup import cleanup

from apps.tenancy.models import WorkspaceOwnedModel


def statutory_upload(instance, filename):
    extension = filename.rsplit('.', 1)[-1].lower()
    return f"loans/statutory/workspace-{instance.workspace_id}/{uuid.uuid4().hex}.{extension}"


class StatutoryImmutableModel(WorkspaceOwnedModel):
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError('Statutory evidence cannot be edited. Record a follow-up instead.')
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Statutory evidence cannot be deleted.')


@cleanup.ignore
class StatutoryAuctionNotice(StatutoryImmutableModel):
    auction = models.OneToOneField('loans.PawnLoanAuction', on_delete=models.PROTECT, related_name='statutory_notice')
    snapshot = models.JSONField()
    snapshot_sha256 = models.CharField(max_length=64)
    artifact = models.FileField(upload_to=statutory_upload)
    artifact_sha256 = models.CharField(max_length=64)
    template_version = models.CharField(max_length=60, default='tn-rule12-catalogue-v1')
    request_key = models.CharField(max_length=120)

    def clean(self):
        if self.auction_id and self.workspace_id != self.auction.workspace_id:
            raise ValidationError('Notice and auction must belong to the same Workspace.')


@cleanup.ignore
class StatutoryNoticeEvidence(StatutoryImmutableModel):
    class Kind(models.TextChoices):
        PRINTED = 'PRINTED', 'Printed and signed by the auctioneer'
        POSTED = 'POSTED', 'Posted with registration and acknowledgement/POD'
        ACKNOWLEDGED = 'ACKNOWLEDGED', 'Acknowledgement / proof of delivery received'
        RETURNED = 'RETURNED', 'Undelivered cover received back'
        REFERRED = 'REFERRED', 'Referred to the Village Administrative Officer'
        OFFICER_RECEIVED = 'OFFICER_RECEIVED', 'Village Officer receipt confirmed'
        CERTIFIED = 'CERTIFIED', 'Official affixture and proclamation certificate received'
        REVIEWED = 'REVIEWED', 'Readiness evidence reviewed'
        WITHDRAWN = 'WITHDRAWN', 'Notice withdrawn / correction required'

    notice = models.ForeignKey(StatutoryAuctionNotice, on_delete=models.PROTECT, related_name='evidence')
    kind = models.CharField(max_length=20, choices=Kind.choices)
    occurred_on = models.DateField()
    details = models.JSONField(default=dict)
    attachment = models.FileField(upload_to=statutory_upload, blank=True)
    attachment_sha256 = models.CharField(max_length=64, blank=True)
    request_key = models.CharField(max_length=120)

    class Meta:
        ordering = ('created_at', 'pk')
        constraints = [models.UniqueConstraint(fields=('notice', 'request_key'), name='loans_stat_evidence_request_uniq')]

    def clean(self):
        if self.notice_id and self.workspace_id != self.notice.workspace_id:
            raise ValidationError('Evidence and notice must belong to the same Workspace.')
