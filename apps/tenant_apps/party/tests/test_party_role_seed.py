import uuid

from django.contrib.auth import get_user_model
from django.core.management import call_command
from apps.tenancy.testing import WorkspaceTestCase

from apps.tenant_apps.party.models import PartyRoleType
from apps.tenant_apps.party.services import CANONICAL_PARTY_ROLES, seed_party_roles


User = get_user_model()


class PartyRoleSeedTests(WorkspaceTestCase):
    test_schema_name = f"party_roles_{uuid.uuid4().hex[:8]}"
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
            username="party-role-seed-owner",
            defaults={"email": "party-role-seed-owner@example.com"},
        )
        user.set_password("testpass123")
        user.save(update_fields=["password"])
        tenant.name = f"party-role-seed-tenant-{uuid.uuid4().hex[:8]}"
        tenant.owner = user
        tenant.creator = user

    def setUp(self):
        super().setUp()

    def test_seed_party_roles_is_idempotent(self):
        first = seed_party_roles(workspace=self.tenant)
        second = seed_party_roles(workspace=self.tenant)

        self.assertEqual(first["created"], len(CANONICAL_PARTY_ROLES))
        self.assertEqual(second["created"], 0)
        self.assertEqual(PartyRoleType.objects.count(), len(CANONICAL_PARTY_ROLES))

    def test_seed_creates_all_canonical_roles_as_system_roles(self):
        seed_party_roles(workspace=self.tenant)

        for role in CANONICAL_PARTY_ROLES:
            role_type = PartyRoleType.objects.get(key=role.key)
            self.assertEqual(role_type.label, role.label)
            self.assertTrue(role_type.is_system)
            self.assertTrue(role_type.is_active)

    def test_management_command_seeds_roles(self):
        call_command("seed_party_roles", workspace_id=self.tenant.pk, verbosity=0)

        self.assertEqual(PartyRoleType.objects.count(), len(CANONICAL_PARTY_ROLES))
