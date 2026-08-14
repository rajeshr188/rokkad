from io import StringIO
import uuid

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection
from django_tenants.test.cases import TenantTestCase
from moneyed import Money

from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.dea.models import (
    Account,
    AccountStatement,
    AccountType,
    AccountType_Ext,
    EntityType,
    Ledger,
    LedgerStatement,
    TransactionType_DE,
)


User = get_user_model()


class CurrencyCodeAuditCommandTests(TenantTestCase):
    test_schema_name = f"dea_currency_audit_{uuid.uuid4().hex[:8]}"
    test_domain = f"{test_schema_name}.test.com"

    @classmethod
    def get_test_schema_name(cls):
        return cls.test_schema_name

    @classmethod
    def get_test_tenant_domain(cls):
        return cls.test_domain

    @classmethod
    def setup_tenant(cls, tenant):
        owner, _ = User.objects.get_or_create(
            username="dea-currency-audit-owner",
            defaults={"email": "dea-currency-audit-owner@example.com"},
        )
        owner.set_password("testpass123")
        owner.save(update_fields=["password"])
        tenant.name = f"dea-currency-audit-tenant-{uuid.uuid4().hex[:8]}"
        tenant.owner = owner
        tenant.creator = owner

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        self._seed_account_masters()

    def test_command_flags_metal_like_statement_currency_codes(self):
        ledger = self._ledger("Currency Audit Ledger")
        LedgerStatement.objects.create(
            ledgerno=ledger,
            ClosingBalance=Money(1, "XAU"),
        )

        customer = Customer.objects.create(
            firstname="Audit",
            lastname="Customer",
            customer_type=Customer.CustomerType.Retail,
        )
        account = Account.objects.create(
            contact=customer,
            entity=EntityType.objects.get(name="Person"),
            AccountType_Ext=AccountType_Ext.objects.get(description="Debtor"),
        )
        statement = AccountStatement.objects.create(
            AccountNo=account,
            ClosingBalance=Money(2, "INR"),
            TotalCredit=Money(0, "INR"),
            TotalDebit=Money(0, "INR"),
        )
        AccountStatement.objects.filter(pk=statement.pk).update(
            ClosingBalance_currency="SLV",
            TotalCredit_currency="SLV",
            TotalDebit_currency="SLV",
        )

        output = StringIO()
        call_command("audit_dea_currency_codes", stdout=output)

        command_output = output.getvalue()
        self.assertIn("DEA currency-code audit", command_output)
        self.assertIn("LedgerStatement.ClosingBalance_currency", command_output)
        self.assertIn("XAU(1) SUSPICIOUS", command_output)
        self.assertIn("AccountStatement.ClosingBalance_currency", command_output)
        self.assertIn("SLV(1) SUSPICIOUS", command_output)
        self.assertIn("Suspicious metal-like currency code occurrences", command_output)

    def test_command_reports_clean_schema_without_suspicious_codes(self):
        ledger = self._ledger("Clean Currency Audit Ledger")
        LedgerStatement.objects.create(
            ledgerno=ledger,
            ClosingBalance=Money(1, "INR"),
        )

        output = StringIO()
        call_command("audit_dea_currency_codes", stdout=output)

        command_output = output.getvalue()
        self.assertIn("INR(1)", command_output)
        self.assertIn("No suspicious metal-like currency codes found.", command_output)

    def _ledger(self, name):
        account_type, _ = AccountType.objects.get_or_create(
            AccountType="Asset",
            defaults={"description": "Asset", "code_prefix": "1"},
        )
        ledger, _ = Ledger.objects.get_or_create(
            name=name,
            defaults={
                "AccountType": account_type,
                "code": f"1.AUDIT.{uuid.uuid4().hex[:8]}",
            },
        )
        return ledger

    def _seed_account_masters(self):
        debit_code, _ = TransactionType_DE.objects.get_or_create(
            XactTypeCode="Dr",
            defaults={"name": "Debit"},
        )
        AccountType_Ext.objects.get_or_create(
            description="Debtor",
            defaults={"XactTypeCode": debit_code},
        )
        EntityType.objects.get_or_create(name="Person")
