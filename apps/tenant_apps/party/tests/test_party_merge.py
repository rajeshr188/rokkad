import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection
from django_tenants.test.cases import TenantTestCase

from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.dea.models import (
    Account,
    AccountType_Ext,
    EntityType,
    PartyAccountMapping,
    PartyAccountPurpose,
    TransactionType_DE,
)
from apps.tenant_apps.party.models import (
    Party,
    PartyAddress,
    PartyContactMethod,
    PartyDocument,
    PartyIdentifier,
    PartyRelationship,
    PartyRole,
    PartyRoleType,
)
from apps.tenant_apps.party.services.customer_bridge import ensure_customer_party
from apps.tenant_apps.party.services.party_merge import merge_parties


User = get_user_model()


class PartyMergeTests(TenantTestCase):
    test_schema_name = f"party_merge_{uuid.uuid4().hex[:8]}"
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
            username="party-merge-owner",
            defaults={"email": "party-merge-owner@example.com"},
        )
        user.set_password("testpass123")
        user.save(update_fields=["password"])
        tenant.name = f"party-merge-tenant-{uuid.uuid4().hex[:8]}"
        tenant.owner = user
        tenant.creator = user

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)

    def test_merge_moves_profile_children_and_archives_source(self):
        target = Party.objects.create(
            party_code="P-MERGE-T",
            display_name="Target Party",
            primary_phone="+919999999999",
        )
        source = Party.objects.create(
            party_code="P-MERGE-S",
            display_name="Source Party",
            primary_email="source@example.com",
        )
        role_type = PartyRoleType.objects.create(key="CUSTOMER", label="Customer")
        PartyRole.objects.create(party=source, role_type=role_type)
        PartyContactMethod.objects.create(
            party=source,
            contact_type=PartyContactMethod.ContactType.EMAIL,
            value="source@example.com",
            is_primary=True,
        )
        PartyAddress.objects.create(
            party=source,
            address_type=PartyAddress.AddressType.HOME,
            line1="Source Street",
            city="Chennai",
            is_default=True,
        )
        identifier = PartyIdentifier.objects.create(
            party=source,
            identifier_type=PartyIdentifier.IdentifierType.PAN,
            value="ABCDE1234F",
        )
        PartyDocument.objects.create(
            party=source,
            document_type=PartyDocument.DocumentType.KYC,
            title="PAN Copy",
            identifier=identifier,
        )
        related = Party.objects.create(party_code="P-REL", display_name="Related")
        PartyRelationship.objects.create(
            from_party=source,
            to_party=related,
            relationship_type=PartyRelationship.RelationshipType.FAMILY,
        )

        result = merge_parties(target=target, source=source)
        target.refresh_from_db()
        source.refresh_from_db()

        self.assertEqual(source.status, Party.PartyStatus.ARCHIVED)
        self.assertEqual(target.primary_email, "source@example.com")
        self.assertEqual(result.roles_moved, 1)
        self.assertEqual(target.contact_methods.count(), 1)
        self.assertEqual(target.addresses.count(), 1)
        self.assertEqual(target.identifiers.count(), 1)
        self.assertEqual(target.documents.count(), 1)
        self.assertEqual(target.relationships_from.count(), 1)
        self.assertIn(source.pk, target.metadata["merged_from_party_ids"])
        self.assertEqual(source.metadata["merged_into_party_id"], target.pk)

    def test_merge_repoints_documents_when_identifier_already_exists(self):
        target = Party.objects.create(party_code="P-ID-T", display_name="Target")
        source = Party.objects.create(party_code="P-ID-S", display_name="Source")
        target_identifier = PartyIdentifier.objects.create(
            party=target,
            identifier_type=PartyIdentifier.IdentifierType.PAN,
            value="ABCDE1234F",
        )
        source_identifier = PartyIdentifier.objects.create(
            party=source,
            identifier_type=PartyIdentifier.IdentifierType.PAN,
            value="ABCDE1234F",
        )
        document = PartyDocument.objects.create(
            party=source,
            document_type=PartyDocument.DocumentType.KYC,
            title="PAN Copy",
            identifier=source_identifier,
        )

        merge_parties(target=target, source=source)
        document.refresh_from_db()

        self.assertEqual(document.party, target)
        self.assertEqual(document.identifier, target_identifier)

    def test_merge_refuses_two_legacy_customer_links(self):
        target_customer = Customer.objects.create(firstname="Target", lastname="Customer")
        source_customer = Customer.objects.create(firstname="Source", lastname="Customer")
        ensure_customer_party(target_customer)
        ensure_customer_party(source_customer)
        target_customer.refresh_from_db()
        source_customer.refresh_from_db()

        with self.assertRaises(ValidationError):
            merge_parties(target=target_customer.party, source=source_customer.party)

    def test_merge_refuses_conflicting_account_mapping(self):
        self._seed_account_masters()
        customer = Customer.objects.create(firstname="Account", lastname="Holder")
        account_type = AccountType_Ext.objects.get(description="Debtor")
        entity = EntityType.objects.get(name="Person")
        first_account = Account.objects.create(
            contact=customer,
            AccountType_Ext=account_type,
            entity=entity,
        )
        second_account = Account.objects.create(
            contact=customer,
            AccountType_Ext=account_type,
            entity=entity,
        )
        target = Party.objects.create(party_code="P-ACCT-T", display_name="Target")
        source = Party.objects.create(party_code="P-ACCT-S", display_name="Source")
        PartyAccountMapping.objects.create(
            party=target,
            role_key="CUSTOMER",
            purpose=PartyAccountPurpose.CUSTOMER_RECEIVABLE,
            account=first_account,
        )
        PartyAccountMapping.objects.create(
            party=source,
            role_key="CUSTOMER",
            purpose=PartyAccountPurpose.CUSTOMER_RECEIVABLE,
            account=second_account,
        )

        with self.assertRaises(ValidationError):
            merge_parties(target=target, source=source)

    def _seed_account_masters(self):
        debtor_code, _ = TransactionType_DE.objects.get_or_create(
            XactTypeCode="Dr",
            defaults={"name": "Debit"},
        )
        AccountType_Ext.objects.get_or_create(
            description="Debtor",
            defaults={"XactTypeCode": debtor_code},
        )
        EntityType.objects.get_or_create(name="Person")
