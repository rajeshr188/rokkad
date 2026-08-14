"""
Immutable audit event log for tracking all financial transactions.
All audit records are append-only and can only be viewed, not modified or deleted.
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.utils.translation import gettext_lazy as _

User = get_user_model()


class ImmutableAuditEventQuerySet(models.QuerySet):
    def delete(self):
        raise PermissionDenied("Accounting audit events are immutable and cannot be deleted.")


class ImmutableAuditEventManager(models.Manager):
    def get_queryset(self):
        return ImmutableAuditEventQuerySet(self.model, using=self._db)


class AccountingAuditEvent(models.Model):
    """
    Immutable audit event log for financial transaction tracking.
    
    Records:
    - Who performed the action (actor)
    - What action was performed (event_type)
    - When it happened (occurred_at)
    - What object was affected (object_type, object_id)
    - State before and after (payload_before, payload_after)
    - From where (ip_address)
    
    This model is append-only with restricted permissions (view only).
    """

    objects = ImmutableAuditEventManager()
    
    class EventType(models.TextChoices):
        """Event types for accounting transactions."""
        VOUCHER_CREATED = 'VOUCHER_CREATED', _('Voucher Created')
        VOUCHER_POSTED = 'VOUCHER_POSTED', _('Voucher Posted')
        VOUCHER_REVERSED = 'VOUCHER_REVERSED', _('Voucher Reversed')
        JOURNAL_ENTRY_CREATED = 'JOURNAL_ENTRY_CREATED', _('Journal Entry Created')
        PERIOD_CLOSED = 'PERIOD_CLOSED', _('Period Closed')
        PERIOD_LOCKED = 'PERIOD_LOCKED', _('Period Locked')
        PERIOD_UNLOCKED = 'PERIOD_UNLOCKED', _('Period Unlocked')
        LEDGER_CREATED = 'LEDGER_CREATED', _('Ledger Created')
        OPENING_BALANCE_SET = 'OPENING_BALANCE_SET', _('Opening Balance Set')
        SETTLEMENT_CREATED = 'SETTLEMENT_CREATED', _('Settlement Created')
        BANK_RECONCILIATION_MATCHED = 'BANK_RECONCILIATION_MATCHED', _('Bank Line Matched')
        BANK_RECONCILIATION_UNMATCHED = 'BANK_RECONCILIATION_UNMATCHED', _('Bank Line Unmatched')
        APPROVAL_REQUESTED = 'APPROVAL_REQUESTED', _('Approval Requested')
        APPROVAL_APPROVED = 'APPROVAL_APPROVED', _('Approval Granted')
        APPROVAL_REJECTED = 'APPROVAL_REJECTED', _('Approval Rejected')
    
    # Event identification
    event_type = models.CharField(
        max_length=40,
        choices=EventType.choices,
        db_index=True,
        help_text="Type of accounting event"
    )
    
    # Actor (who)
    actor = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='accounting_audit_events',
        help_text="User who performed the action"
    )
    
    # Object (what)
    object_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        help_text="Type of object affected (e.g., Voucher, JournalEntry)"
    )
    object_id = models.PositiveIntegerField(
        help_text="ID of the object affected"
    )
    
    # State (before/after)
    payload_before = models.JSONField(
        null=True,
        blank=True,
        help_text="Object state before the action (null for creates)"
    )
    payload_after = models.JSONField(
        help_text="Object state after the action"
    )
    
    # Metadata
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address from which the action was performed"
    )
    
    description = models.TextField(
        blank=True,
        help_text="Human-readable description of the action"
    )
    
    occurred_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Timestamp when the event occurred"
    )
    
    class Meta:
        # Append-only: only 'view' permission, no add/change/delete
        default_permissions = ('view',)
        permissions = [
            ('view_accounting_audit_event', 'Can view accounting audit events'),
        ]
        
        # Indices for common queries
        indexes = [
            models.Index(fields=['event_type', 'occurred_at']),
            models.Index(fields=['actor', 'occurred_at']),
            models.Index(fields=['object_type', 'object_id']),
            models.Index(fields=['occurred_at']),
        ]
        
        verbose_name = _('Accounting Audit Event')
        verbose_name_plural = _('Accounting Audit Events')
        ordering = ['-occurred_at']
    
    def __str__(self):
        return f"{self.get_event_type_display()} by {self.actor} on {self.occurred_at.date()}"

    def save(self, *args, **kwargs):
        # Allow insert once; block subsequent updates.
        if self.pk and AccountingAuditEvent.objects.filter(pk=self.pk).exists():
            raise PermissionDenied("Accounting audit events are immutable and cannot be updated.")
        return super().save(*args, **kwargs)

    def delete(self, using=None, keep_parents=False):
        raise PermissionDenied("Accounting audit events are immutable and cannot be deleted.")
    
    def get_object_display(self):
        """Return human-readable representation of the affected object."""
        return f"{self.object_type.model}.{self.object_id}"
