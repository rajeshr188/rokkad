import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection
from django_tenants.test.cases import TenantTestCase

from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.dea.facade import (
    ensure_customer_account,
    resolve_customer_account,
    resolve_party_account,
)
from apps.tenant_apps.dea.models import (
    Account,
    AccountType,
    AccountType_Ext,
    EntityType,
    Ledger,
    PartyAccountMapping,
    PartyAccountPurpose,
    TransactionType_DE,
)
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.party.services.customer_bridge import ensure_customer_party


User = get_user_model()


class PartyAccountResolutionTests(TenantTestCase):
    test_schema_name = f"dea_party_account_{uuid.uuid4().hex[:8]}"
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
            username="dea-party-account-owner",
            defaults={"email": "dea-party-account-owner@example.com"},
        )
        user.set_password("testpass123")
        user.save(update_fields=["password"])
        tenant.name = f"dea-party-account-tenant-{uuid.uuid4().hex[:8]}"
        tenant.owner = user
        tenant.creator = user

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        self._seed_account_masters()

    def test_ensure_customer_account_keeps_legacy_read_compatibility(self):
        customer = Customer.objects.create(
            firstname="Retail",
            lastname="Buyer",
            customer_type=Customer.CustomerType.Retail,
        )

        account = ensure_customer_account(customer)

        self.assertEqual(account.contact, customer)
        self.assertEqual(account.AccountType_Ext.description, "Debtor")
        self.assertEqual(customer.account, account)
        self.assertEqual(Account.objects.filter(contact=customer).count(), 1)

    def test_party_can_have_distinct_accounts_by_role_and_purpose(self):
        customer = Customer.objects.create(
            firstname="Rajesh",
            lastname="Trader",
            customer_type=Customer.CustomerType.Retail,
        )
        ensure_customer_party(customer)
        customer.refresh_from_db()

        receivable = resolve_party_account(
            customer.party,
            role_key="CUSTOMER",
            purpose=PartyAccountPurpose.CUSTOMER_RECEIVABLE,
        )
        payable = resolve_party_account(
            customer.party,
            role_key="SUPPLIER",
            purpose=PartyAccountPurpose.SUPPLIER_PAYABLE,
        )

        self.assertNotEqual(receivable.account.id, payable.account.id)
        self.assertEqual(receivable.account.AccountType_Ext.description, "Debtor")
        self.assertEqual(payable.account.AccountType_Ext.description, "Creditor")
        self.assertEqual(
            PartyAccountMapping.objects.filter(party=customer.party).count(),
            2,
        )

    def test_resolve_customer_account_uses_party_mapping_when_customer_is_bridged(self):
        customer = Customer.objects.create(
            firstname="Loan",
            lastname="Borrower",
            customer_type=Customer.CustomerType.Retail,
        )
        ensure_customer_party(customer)
        customer.refresh_from_db()

        account = resolve_customer_account(
            customer,
            role_key="BORROWER",
            purpose=PartyAccountPurpose.BORROWER_LOAN_RECEIVABLE,
        )

        mapping = PartyAccountMapping.objects.get(
            party=customer.party,
            role_key="BORROWER",
            purpose=PartyAccountPurpose.BORROWER_LOAN_RECEIVABLE,
        )
        self.assertEqual(mapping.account, account)
        self.assertEqual(mapping.control_ledger.name, "BORROWER_LOAN_CTRL")

    def test_party_account_creation_requires_legacy_customer_bridge_for_now(self):
        party = Party.objects.create(party_code="P-UNBRIDGED", display_name="Unbridged")

        with self.assertRaises(ValidationError):
            resolve_party_account(
                party,
                role_key="CUSTOMER",
                purpose=PartyAccountPurpose.CUSTOMER_RECEIVABLE,
            )

    def test_resolve_without_create_returns_none(self):
        party = Party.objects.create(party_code="P-NO-CREATE", display_name="No Create")

        self.assertIsNone(
            resolve_party_account(
                party,
                role_key="CUSTOMER",
                purpose=PartyAccountPurpose.CUSTOMER_RECEIVABLE,
                create=False,
            )
        )

    def _seed_account_masters(self):
        debtor_code, _ = TransactionType_DE.objects.get_or_create(
            XactTypeCode="Dr",
            defaults={"name": "Debit"},
        )
        creditor_code, _ = TransactionType_DE.objects.get_or_create(
            XactTypeCode="Cr",
            defaults={"name": "Credit"},
        )
        AccountType_Ext.objects.get_or_create(
            description="Debtor",
            defaults={"XactTypeCode": debtor_code},
        )
        AccountType_Ext.objects.get_or_create(
            description="Creditor",
            defaults={"XactTypeCode": creditor_code},
        )
        EntityType.objects.get_or_create(name="Person")
        EntityType.objects.get_or_create(name="Organisation")
        asset_type, _ = AccountType.objects.get_or_create(
            AccountType="Asset",
            defaults={"description": "Asset Account", "code_prefix": "1"},
        )
        liability_type, _ = AccountType.objects.get_or_create(
            AccountType="Liability",
            defaults={"description": "Liability Account", "code_prefix": "2"},
        )
        Ledger.objects.get_or_create(
            name="Accounts Receivable",
            defaults={"AccountType": asset_type},
        )
        Ledger.objects.get_or_create(
            name="BORROWER_LOAN_CTRL",
            defaults={"AccountType": asset_type},
        )
        Ledger.objects.get_or_create(
            name="ACCOUNTS_PAYABLE",
            defaults={"AccountType": liability_type},
        )
