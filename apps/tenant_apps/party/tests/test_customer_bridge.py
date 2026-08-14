import uuid

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection
from django_tenants.test.cases import TenantTestCase

from apps.tenant_apps.contact.models import Address, Contact, Customer, Proof
from apps.tenant_apps.party.models import (
    Party,
    PartyAddress,
    PartyContactMethod,
    PartyIdentifier,
    PartyRoleType,
)
from apps.tenant_apps.party.services.customer_bridge import (
    backfill_customer_parties,
    ensure_customer_party,
    ensure_party_customer,
)


User = get_user_model()


class CustomerPartyBridgeTests(TenantTestCase):
    test_schema_name = f"party_bridge_{uuid.uuid4().hex[:8]}"
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
            username="party-bridge-owner",
            defaults={"email": "party-bridge-owner@example.com"},
        )
        user.set_password("testpass123")
        user.save(update_fields=["password"])
        tenant.name = f"party-bridge-tenant-{uuid.uuid4().hex[:8]}"
        tenant.owner = user
        tenant.creator = user

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)

    def test_customer_backfill_creates_party_and_customer_role(self):
        customer = Customer.objects.create(
            firstname="Retail",
            lastname="Customer",
            customer_type=Customer.CustomerType.Retail,
            email="retail@example.com",
        )

        result = ensure_customer_party(customer)
        customer.refresh_from_db()

        self.assertTrue(result["created"])
        self.assertIsNotNone(customer.party_id)
        self.assertEqual(customer.party.party_code, f"CUST-{customer.id:06d}")
        self.assertEqual(customer.party.display_name, "Retail Customer")
        role = customer.party.roles.select_related("role_type").get()
        self.assertEqual(role.role_type.key, "CUSTOMER")
        self.assertEqual(role.segment, "RETAIL")

    def test_supplier_customer_type_maps_to_supplier_role(self):
        customer = Customer.objects.create(
            firstname="Supplier",
            lastname="Person",
            customer_type=Customer.CustomerType.Supplier,
        )

        ensure_customer_party(customer)
        customer.refresh_from_db()

        self.assertTrue(
            customer.party.roles.filter(role_type__key="SUPPLIER", segment="").exists()
        )

    def test_party_customer_bridge_creates_compatibility_customer_and_borrower_role(self):
        party = Party.objects.create(
            display_name="Party Borrower",
            primary_email="borrower@example.com",
            relation_label=Party.RelationLabel.SON_OF,
            relation_name="Ramesh",
        )

        result = ensure_party_customer(party)

        self.assertTrue(result["created"])
        customer = result["customer"]
        self.assertEqual(customer.party, party)
        self.assertEqual(customer.firstname, "Party")
        self.assertEqual(customer.lastname, "Borrower")
        self.assertEqual(customer.relatedas, "s")
        self.assertEqual(customer.relatedto, "Ramesh")
        self.assertTrue(party.roles.filter(role_type__key="BORROWER").exists())
        self.assertTrue(party.roles.filter(role_type__key="CUSTOMER").exists())

    def test_backfill_is_idempotent(self):
        Customer.objects.create(firstname="Idempotent", lastname="One")

        first = backfill_customer_parties()
        second = backfill_customer_parties()

        self.assertEqual(first.created, 1)
        self.assertEqual(second.created, 0)
        self.assertEqual(Party.objects.count(), 1)
        self.assertEqual(PartyRoleType.objects.filter(is_system=True).count(), 14)

    def test_backfill_copies_profile_details(self):
        customer = Customer.objects.create(
            firstname="Profile",
            lastname="Customer",
            relatedas="w",
            relatedto="Arjun",
            email="profile@example.com",
        )
        Contact.objects.create(
            customer=customer,
            phone_number="+919999999999",
            contact_type=Contact.ContactType.Mobile,
            is_default=True,
            is_verified=True,
        )
        Address.objects.create(
            customer=customer,
            door_number="10",
            street="Main Street",
            area="Market",
            city="Chennai",
            state="TN",
            zip_code="600001",
            is_default=True,
        )
        Proof.objects.create(
            customer=customer,
            proof_type=Proof.DocType.PAN,
            proof_number="ABCDE1234F",
            is_verified=True,
        )

        ensure_customer_party(customer)
        customer.refresh_from_db()

        self.assertTrue(customer.party.primary_phone)
        self.assertEqual(customer.party.relation_label, Party.RelationLabel.WIFE_OF)
        self.assertEqual(customer.party.relation_name, "Arjun")
        self.assertEqual(customer.party.relation_display, "W/o Arjun")
        self.assertTrue(
            PartyContactMethod.objects.filter(
                party=customer.party,
                contact_type=PartyContactMethod.ContactType.MOBILE,
                is_primary=True,
            ).exists()
        )
        self.assertTrue(
            PartyAddress.objects.filter(
                party=customer.party,
                address_type=PartyAddress.AddressType.BILLING,
                is_default=True,
                city="Chennai",
            ).exists()
        )
        identifier = PartyIdentifier.objects.get(party=customer.party)
        self.assertEqual(identifier.identifier_type, PartyIdentifier.IdentifierType.PAN)
        self.assertEqual(identifier.masked_value, "******234F")
        self.assertTrue(identifier.is_verified)

    def test_management_command_backfills_customers(self):
        Customer.objects.create(firstname="Command", lastname="Customer")

        call_command("backfill_parties_from_customers", verbosity=0)

        self.assertEqual(Party.objects.count(), 1)
