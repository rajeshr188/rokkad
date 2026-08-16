import uuid

from django.contrib.auth import get_user_model
from django.db import connection
from django_tenants.test.cases import TenantTestCase
from moneyed import Money

from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.dea.models import (
    Account,
    AccountType_Ext,
    EntityType,
    PartyAccountMapping,
    PartyAccountPurpose,
    PurchaseInvoiceVoucher,
    SalesInvoiceVoucher,
    TransactionType_DE,
)
from apps.tenant_apps.dea.posting.rules.party_accounts import (
    resolve_sales_customer_account,
)
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.notify_v2.models import NotificationRecipient


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
        customer_party = Party.objects.create(display_name="Linked Customer")
        supplier_party = Party.objects.create(display_name="Linked Supplier")
        self.customer = Customer.objects.create(
            firstname="Linked",
            lastname="Customer",
            customer_type=Customer.CustomerType.Retail,
            party=customer_party,
        )
        self.supplier = Customer.objects.create(
            firstname="Linked",
            lastname="Supplier",
            customer_type=Customer.CustomerType.Supplier,
            party=supplier_party,
        )

    def test_dea_invoice_vouchers_are_party_owned(self):
        sales_invoice = SalesInvoiceVoucher.objects.create(
            party=self.customer.party,
            subtotal=Money(100, "INR"),
            taxable_amount=Money(100, "INR"),
            total_amount=Money(100, "INR"),
            description="Sales invoice",
            auto_post_to_accounting=False,
        )
        purchase_invoice = PurchaseInvoiceVoucher.objects.create(
            party=self.supplier.party,
            subtotal=Money(100, "INR"),
            taxable_amount=Money(100, "INR"),
            total_amount=Money(100, "INR"),
            net_payable=Money(100, "INR"),
            description="Purchase invoice",
            auto_post_to_accounting=False,
        )

        self.assertEqual(sales_invoice.party, self.customer.party)
        self.assertEqual(purchase_invoice.party, self.supplier.party)

    def test_notify_v2_recipient_is_party_owned(self):
        recipient = NotificationRecipient.objects.create(
            party=self.customer.party,
            name_snapshot=self.customer.name,
        )

        self.assertEqual(recipient.party, self.customer.party)

    def test_resolver_prefers_explicit_party_mapping(self):
        self._seed_account_masters()
        party = self.customer.party
        account = Account.objects.create(
            party=party,
            entity=EntityType.objects.get(name="Person"),
            AccountType_Ext=AccountType_Ext.objects.get(description="Debtor"),
        )
        PartyAccountMapping.objects.create(
            party=party,
            role_key="CUSTOMER",
            purpose=PartyAccountPurpose.CUSTOMER_RECEIVABLE,
            account=account,
        )
        invoice = SalesInvoiceVoucher.objects.create(
            party=party,
            subtotal=Money(100, "INR"),
            taxable_amount=Money(100, "INR"),
            total_amount=Money(100, "INR"),
            description="Sales invoice",
            auto_post_to_accounting=False,
        )

        self.assertEqual(resolve_sales_customer_account(invoice), account)

    def _seed_account_masters(self):
        debtor_code, _ = TransactionType_DE.objects.get_or_create(
            XactTypeCode="Dr",
            defaults={"name": "Debit"},
        )
        account_type, _ = AccountType_Ext.objects.get_or_create(
            description="Debtor",
            defaults={"XactTypeCode": debtor_code},
        )
        EntityType.objects.get_or_create(name="Person")
        return account_type
