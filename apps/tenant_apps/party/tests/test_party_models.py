import uuid

from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection, transaction
from django_tenants.test.cases import TenantTestCase

from apps.tenant_apps.party.models import (
    Party,
    PartyAddress,
    PartyCodeSequence,
    PartyContactMethod,
    PartyRole,
    PartyRoleType,
)

User = get_user_model()


class PartyModelTests(TenantTestCase):
    test_schema_name = f"party_models_{uuid.uuid4().hex[:8]}"
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
            username="party-model-owner",
            defaults={"email": "party-model-owner@example.com"},
        )
        user.set_password("testpass123")
        user.save(update_fields=["password"])
        tenant.name = f"party-model-tenant-{uuid.uuid4().hex[:8]}"
        tenant.owner = user
        tenant.creator = user

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)

    def test_create_individual_party(self):
        party = Party.objects.create(
            party_code="P0001",
            display_name="Rajesh",
            party_type=Party.PartyType.INDIVIDUAL,
        )

        self.assertEqual(str(party), "Rajesh (P0001)")
        self.assertEqual(party.status, Party.PartyStatus.ACTIVE)
        self.assertEqual(party.normalized_name, "rajesh")

    def test_party_code_is_auto_generated_when_blank(self):
        first = Party.objects.create(display_name="Auto One")
        second = Party.objects.create(display_name="Auto Two")

        self.assertEqual(first.party_code, "P-000001")
        self.assertEqual(second.party_code, "P-000002")
        self.assertEqual(
            PartyCodeSequence.objects.get(key="PARTY").next_number,
            3,
        )

    def test_manual_party_code_is_preserved(self):
        party = Party.objects.create(party_code="MANUAL-001", display_name="Manual")

        self.assertEqual(party.party_code, "MANUAL-001")
        self.assertFalse(PartyCodeSequence.objects.filter(key="PARTY").exists())

    def test_create_organization_party(self):
        party = Party.objects.create(
            party_code="P0002",
            display_name="Rokkad Traders",
            legal_name="Rokkad Traders Private Limited",
            party_type=Party.PartyType.ORGANIZATION,
        )

        self.assertEqual(party.party_type, Party.PartyType.ORGANIZATION)
        self.assertEqual(party.legal_name, "Rokkad Traders Private Limited")

    def test_party_can_have_multiple_roles(self):
        party = Party.objects.create(party_code="P0003", display_name="Rajesh")
        customer = PartyRoleType.objects.create(key="CUSTOMER", label="Customer")
        supplier = PartyRoleType.objects.create(key="SUPPLIER", label="Supplier")

        PartyRole.objects.create(party=party, role_type=customer)
        PartyRole.objects.create(party=party, role_type=supplier)

        self.assertEqual(party.roles.count(), 2)

    def test_duplicate_active_role_is_rejected(self):
        party = Party.objects.create(party_code="P0004", display_name="Rajesh")
        customer = PartyRoleType.objects.create(key="CUSTOMER", label="Customer")
        PartyRole.objects.create(party=party, role_type=customer)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PartyRole.objects.create(party=party, role_type=customer)

    def test_one_primary_contact_per_type(self):
        party = Party.objects.create(party_code="P0005", display_name="Rajesh")
        PartyContactMethod.objects.create(
            party=party,
            contact_type=PartyContactMethod.ContactType.MOBILE,
            value="9999999999",
            is_primary=True,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PartyContactMethod.objects.create(
                    party=party,
                    contact_type=PartyContactMethod.ContactType.MOBILE,
                    value="8888888888",
                    is_primary=True,
                )

    def test_one_default_address_per_type(self):
        party = Party.objects.create(party_code="P0006", display_name="Rajesh")
        PartyAddress.objects.create(
            party=party,
            address_type=PartyAddress.AddressType.BILLING,
            line1="First Street",
            city="Chennai",
            is_default=True,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PartyAddress.objects.create(
                    party=party,
                    address_type=PartyAddress.AddressType.BILLING,
                    line1="Second Street",
                    city="Chennai",
                    is_default=True,
                )
