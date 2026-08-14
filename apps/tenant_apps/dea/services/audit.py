"""
Audit logging service for recording accounting events.
"""
import json
import logging
from typing import Any, Optional, Dict
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.serializers.json import DjangoJSONEncoder
from ..models.audit import AccountingAuditEvent

User = get_user_model()
logger = logging.getLogger(__name__)


class AuditService:
    """
    Service for logging immutable audit events.
    
    Usage:
        service = AuditService()
        service.log_event(
            event_type=AccountingAuditEvent.EventType.VOUCHER_POSTED,
            actor=request.user,
            obj=voucher,
            payload_before={'status': 'DRAFT'},
            payload_after={'status': 'POSTED'},
            ip_address=get_client_ip(request),
            description="Posted voucher for invoice #INV001"
        )
    """
    
    @staticmethod
    def log_event(
        event_type: str,
        actor: User,
        obj: Any,
        payload_after: Dict[str, Any],
        payload_before: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        description: str = "",
    ) -> AccountingAuditEvent:
        """
        Log an accounting audit event.
        
        Args:
            event_type: Type of event (from AccountingAuditEvent.EventType)
            actor: User who performed the action
            obj: The model instance affected
            payload_after: State of the object after the action
            payload_before: State of the object before the action (optional)
            ip_address: IP address from which the action was performed (optional)
            description: Human-readable description (optional)
        
        Returns:
            AccountingAuditEvent: The created audit event record
        """
        try:
            content_type = ContentType.objects.get_for_model(obj)
            
            event = AccountingAuditEvent.objects.create(
                event_type=event_type,
                actor=actor,
                object_type=content_type,
                object_id=obj.pk,
                payload_before=payload_before,
                payload_after=payload_after,
                ip_address=ip_address,
                description=description,
            )
            
            logger.info(
                f"Audit event logged: {event_type} for {content_type.model} "
                f"#{obj.pk} by {actor.username}"
            )
            return event
        except Exception as e:
            logger.exception(
                f"Failed to log audit event {event_type} for {obj}: {e}"
            )
            # Don't raise - audit failure should not block the operation
            return None
    
    @staticmethod
    def serialize_obj(obj: Any) -> Dict[str, Any]:
        """
        Serialize a model instance to a JSON-serializable dictionary.
        
        Includes all fields except sensitive data like passwords.
        
        Args:
            obj: Model instance to serialize
        
        Returns:
            Dictionary representation of the object
        """
        data = {}
        for field in obj._meta.get_fields():
            # Skip many-to-many and reverse relations
            if field.many_to_one or field.one_to_one:
                try:
                    value = getattr(obj, field.name)
                    # For FK, store the ID and string representation
                    if value:
                        data[field.name] = {
                            'id': value.pk,
                            'repr': str(value)
                        }
                    else:
                        data[field.name] = None
                except AttributeError:
                    pass
            elif not (field.many_to_many or field.one_to_many):
                try:
                    value = getattr(obj, field.name)
                    # Convert non-serializable types
                    if hasattr(value, 'isoformat'):
                        data[field.name] = value.isoformat()
                    elif hasattr(value, '__dict__'):
                        data[field.name] = str(value)
                    else:
                        data[field.name] = value
                except AttributeError:
                    pass
        
        return data
    
    @staticmethod
    def get_events_for_object(obj: Any, limit: int = 10) -> list:
        """
        Get audit events for a specific object.
        
        Args:
            obj: Model instance to get audit history for
            limit: Maximum number of recent events to return
        
        Returns:
            List of AccountingAuditEvent records for this object
        """
        content_type = ContentType.objects.get_for_model(obj)
        return AccountingAuditEvent.objects.filter(
            object_type=content_type,
            object_id=obj.pk
        ).order_by('-occurred_at')[:limit]
    
    @staticmethod
    def get_events_by_actor(actor: User, limit: int = 10) -> list:
        """
        Get audit events performed by a specific user.
        
        Args:
            actor: User to get events for
            limit: Maximum number of recent events to return
        
        Returns:
            List of AccountingAuditEvent records
        """
        return AccountingAuditEvent.objects.filter(
            actor=actor
        ).order_by('-occurred_at')[:limit]
    
    @staticmethod
    def get_events_by_type(
        event_type: str,
        limit: int = 10
    ) -> list:
        """
        Get audit events of a specific type.
        
        Args:
            event_type: Type of event to filter by
            limit: Maximum number of recent events to return
        
        Returns:
            List of AccountingAuditEvent records
        """
        return AccountingAuditEvent.objects.filter(
            event_type=event_type
        ).order_by('-occurred_at')[:limit]
