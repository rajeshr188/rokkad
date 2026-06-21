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
from apps.tenant_apps.girvi.models import GivenLoan, License, Series, TakenLoan
from apps.tenant_apps.party.services.customer_bridge import ensure_customer_party


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
        self.customer = Customer.objects.create(
            firstname="Linked",
            lastname="Customer",
            customer_type=Customer.CustomerType.Retail,
        )
        self.supplier = Customer.objects.create(
            firstname="Linked",
            lastname="Supplier",
            customer_type=Customer.CustomerType.Supplier,
        )
        ensure_customer_party(self.customer)
        ensure_customer_party(self.supplier)
        self.customer.refresh_from_db()
        self.supplier.refresh_from_db()

    def test_girvi_loans_sync_party_shadow_fields(self):
        license_record = License.objects.create(
            name="Test License",
            license_number=f"LIC-{uuid.uuid4().hex[:8]}",
        )
        given_series = Series.objects.create(
            license=license_record,
            name="Given",
            prefix="G",
            loan_type=Series.LoanType.GIVEN,
        )
        taken_series = Series.objects.create(
            license=license_record,
            name="Taken",
            prefix="T",
            loan_type=Series.LoanType.TAKEN,
        )

        given_loan = GivenLoan.objects.create(
            loan_id="G00001",
            series=given_series,
            borrower=self.customer,
        )
        taken_loan = TakenLoan.objects.create(
            loan_id="T00001",
            series=taken_series,
            lender=self.supplier,
        )

        self.assertEqual(given_loan.borrower_party, self.customer.party)
        self.assertEqual(taken_loan.lender_party, self.supplier.party)

    def test_dea_invoice_vouchers_sync_party_shadow_fields(self):
        sales_invoice = SalesInvoiceVoucher.objects.create(
            customer=self.customer,
            subtotal=Money(100, "INR"),
            taxable_amount=Money(100, "INR"),
            total_amount=Money(100, "INR"),
            description="Sales invoice",
            auto_post_to_accounting=False,
        )
        purchase_invoice = PurchaseInvoiceVoucher.objects.create(
            vendor=self.supplier,
            subtotal=Money(100, "INR"),
            taxable_amount=Money(100, "INR"),
            total_amount=Money(100, "INR"),
            net_payable=Money(100, "INR"),
            description="Purchase invoice",
            auto_post_to_accounting=False,
        )

        self.assertEqual(sales_invoice.party, self.customer.party)
        self.assertEqual(purchase_invoice.party, self.supplier.party)

    def test_resolver_prefers_explicit_party_mapping(self):
        self._seed_account_masters()
        party = self.customer.party
        account = Account.objects.create(
            contact=self.customer,
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
            customer=self.customer,
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
