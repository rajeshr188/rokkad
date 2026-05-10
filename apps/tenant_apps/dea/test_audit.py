"""Tests for accounting audit event logging system."""

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.db import connection
from django_tenants.test.cases import TenantTestCase
from uuid import uuid4

from apps.tenant_apps.dea.models.audit import AccountingAuditEvent
from apps.tenant_apps.dea.services.audit import AuditService


User = get_user_model()


class AuditEventModelSmokeTests(TenantTestCase):
    @staticmethod
    def get_test_schema_name():
        return f"test_dea_audit_{uuid4().hex[:8]}"

    @classmethod
    def setup_tenant(cls, tenant):
        owner, _ = User.objects.get_or_create(
            username="dea-audit-owner",
            defaults={"email": "dea-audit-owner@example.com"},
        )
        owner.set_password("testpass123")
        owner.save(update_fields=["password"])
        tenant.name = f"dea-audit-tenant-{uuid4().hex[:8]}"
        tenant.owner = owner
        tenant.creator = owner

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        self.actor, _ = User.objects.get_or_create(
            username="actor_user",
            defaults={"email": "actor@example.com"},
        )
        self.actor.set_password("testpass123")
        self.actor.save(update_fields=["password"])
        self.target, _ = User.objects.get_or_create(
            username="target_user",
            defaults={"email": "target@example.com"},
        )
        self.target.set_password("testpass123")
        self.target.save(update_fields=["password"])

    def test_audit_event_creation_smoke(self):
        content_type = ContentType.objects.get_for_model(User)
        event = AccountingAuditEvent.objects.create(
            event_type=AccountingAuditEvent.EventType.VOUCHER_POSTED,
            actor=self.actor,
            object_type=content_type,
            object_id=self.target.pk,
            payload_after={"status": "POSTED"},
        )
        self.assertIsNotNone(event.pk)
        self.assertEqual(event.object_id, self.target.pk)

    def test_audit_event_permissions_smoke(self):
        self.assertEqual(list(AccountingAuditEvent._meta.default_permissions), ["view"])

    def test_audit_event_delete_blocked(self):
        content_type = ContentType.objects.get_for_model(User)
        event = AccountingAuditEvent.objects.create(
            event_type=AccountingAuditEvent.EventType.VOUCHER_POSTED,
            actor=self.actor,
            object_type=content_type,
            object_id=self.target.pk,
            payload_after={"status": "POSTED"},
        )
        with self.assertRaises(PermissionDenied):
            event.delete()

    def test_audit_event_update_blocked(self):
        content_type = ContentType.objects.get_for_model(User)
        event = AccountingAuditEvent.objects.create(
            event_type=AccountingAuditEvent.EventType.VOUCHER_POSTED,
            actor=self.actor,
            object_type=content_type,
            object_id=self.target.pk,
            payload_after={"status": "POSTED"},
        )
        event.description = "mutated"
        with self.assertRaises(PermissionDenied):
            event.save()


class AuditServiceSmokeTests(TenantTestCase):
    @staticmethod
    def get_test_schema_name():
        return f"test_dea_audit_service_{uuid4().hex[:8]}"

    @classmethod
    def setup_tenant(cls, tenant):
        owner, _ = User.objects.get_or_create(
            username="dea-audit-service-owner",
            defaults={"email": "dea-audit-service-owner@example.com"},
        )
        owner.set_password("testpass123")
        owner.save(update_fields=["password"])
        tenant.name = f"dea-audit-service-tenant-{uuid4().hex[:8]}"
        tenant.owner = owner
        tenant.creator = owner

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        self.actor, _ = User.objects.get_or_create(
            username="actor_user",
            defaults={"email": "actor@example.com"},
        )
        self.actor.set_password("testpass123")
        self.actor.save(update_fields=["password"])
        self.target, _ = User.objects.get_or_create(
            username="target_user",
            defaults={"email": "target@example.com"},
        )
        self.target.set_password("testpass123")
        self.target.save(update_fields=["password"])
        self.service = AuditService()

    def test_log_event_smoke(self):
        event = self.service.log_event(
            event_type=AccountingAuditEvent.EventType.PERIOD_CLOSED,
            actor=self.actor,
            obj=self.target,
            payload_after={"status": "CLOSED"},
            payload_before={"status": "OPEN"},
            ip_address="127.0.0.1",
        )
        self.assertIsNotNone(event)
        self.assertEqual(event.actor, self.actor)
        self.assertEqual(event.ip_address, "127.0.0.1")

    def test_get_events_for_object_smoke(self):
        self.service.log_event(
            event_type=AccountingAuditEvent.EventType.PERIOD_LOCKED,
            actor=self.actor,
            obj=self.target,
            payload_after={"status": "LOCKED"},
        )
        events = self.service.get_events_for_object(self.target)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].object_id, self.target.pk)
