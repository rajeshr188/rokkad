import uuid

from django.contrib.auth import get_user_model
from django.db import connection
from django_tenants.test.cases import TenantTestCase

from apps.tenant_apps.notify_v2.models import NotificationRecipient
from apps.tenant_apps.party.models import Party


User = get_user_model()


class OperationalPartyLinkTests(TenantTestCase):
    test_schema_name = f"party_ops_{uuid.uuid4().hex[:8]}"
    test_domain = f"{test_schema_name}.test.com"

    @classmethod
    def get_test_schema_name(cls):
        return cls.test_schema_name

    @classmethod
    def get_test_tenant_domain(cls):
        return cls.test_domain

    @classmethod
    def setup_tenant(cls, tenant):
        user, _ = User.objects.get_or_create(
            username="party-ops-owner",
            defaults={"email": "party-ops-owner@example.com"},
        )
        user.set_password("testpass123")
        user.save(update_fields=["password"])
        tenant.name = f"party-ops-tenant-{uuid.uuid4().hex[:8]}"
        tenant.owner = user
        tenant.creator = user

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        self.party = Party.objects.create(display_name="Linked Customer")

    def test_notify_v2_recipient_is_party_owned(self):
        recipient = NotificationRecipient.objects.create(
            party=self.party,
            name_snapshot=self.party.display_name,
        )

        self.assertEqual(recipient.party, self.party)
