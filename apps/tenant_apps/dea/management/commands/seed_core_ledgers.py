"""Seed DEA baseline masters and chart of accounts in tenant schemas."""

from django.core.management.base import BaseCommand
from django.db import transaction
from django_tenants.utils import get_tenant_model, schema_context

from apps.tenant_apps.dea.models import (
    AccountType,
    AccountType_Ext,
    EntityType,
    Ledger,
    TransactionType_DE,
    TransactionType_Ext,
)


class Command(BaseCommand):
    help = "Seed DEA baseline masters + standard chart of accounts for tenant schemas"

    def add_arguments(self, parser):
        parser.add_argument(
            '--schema',
            type=str,
            help='Specific tenant schema to seed. If omitted, seeds all non-public tenant schemas.',
        )

    def handle(self, *args, **options):
        schema = options.get("schema")
        if schema:
            schemas = [schema]
        else:
            TenantModel = get_tenant_model()
            schemas = list(
                TenantModel.objects.exclude(schema_name="public").values_list(
                    "schema_name", flat=True
                )
            )

        for s in schemas:
            self.stdout.write(f"\n--- Seeding schema: {s} ---")
            with schema_context(s):
                with transaction.atomic():
                    summary = self._seed_dea_baseline()

            self.stdout.write(
                self.style.SUCCESS(
                    "Seeded DEA baseline: "
                    f"account_types={summary['account_types']}, "
                    f"entities={summary['entities']}, "
                    f"txn_de={summary['txn_de']}, "
                    f"txn_ext={summary['txn_ext']}, "
                    f"account_type_ext={summary['account_type_ext']}, "
                    f"ledgers={summary['ledgers']}"
                )
            )

    def _seed_dea_baseline(self):
        account_types = self._seed_account_types()
        entities = self._seed_entity_types()
        txn_de = self._seed_transaction_types_de()
        txn_ext = self._seed_transaction_types_ext()
        account_type_ext = self._seed_account_type_ext()
        ledgers = self._seed_standard_ledgers(account_types)

        return {
            "account_types": account_types,
            "entities": entities,
            "txn_de": txn_de,
            "txn_ext": txn_ext,
            "account_type_ext": account_type_ext,
            "ledgers": ledgers,
        }

    def _seed_account_types(self):
        seeds = [
            ("Asset", "Asset Account", "1"),
            ("Liability", "Liability Account", "2"),
            ("Equity", "Equity Account", "3"),
            ("Income", "Income Account", "4"),
            ("Expense", "Expense Account", "5"),
        ]
        created = 0
        for name, description, prefix in seeds:
            _, was_created = AccountType.objects.update_or_create(
                AccountType=name,
                defaults={"description": description, "code_prefix": prefix},
            )
            if was_created:
                created += 1
        return created

    def _seed_entity_types(self):
        created = 0
        for name in ["Person", "Organisation"]:
            _, was_created = EntityType.objects.get_or_create(name=name)
            if was_created:
                created += 1
        return created

    def _seed_transaction_types_de(self):
        seeds = [("Cr", "Credit"), ("Dr", "Debit")]
        created = 0
        for code, name in seeds:
            _, was_created = TransactionType_DE.objects.update_or_create(
                XactTypeCode=code,
                defaults={"name": name},
            )
            if was_created:
                created += 1
        return created

    def _seed_transaction_types_ext(self):
        seeds = [
            ("AC", "Adjust Credit"),
            ("AD", "Adjust Debit"),
            ("CPU", "Cash Purchase"),
            ("CRPU", "Credit Purchase"),
            ("CRSL", "Credit Sale"),
            ("CSL", "Cash Sale"),
            ("IP", "Interest Paid"),
            ("IR", "Interest Received"),
            ("LG", "Loan Given"),
            ("LT", "Loan Taken"),
            ("LR", "Loan Released"),
            ("LP", "Loan Paid"),
            ("PYT", "Payment"),
            ("RCT", "Receipt"),
            ("DC", "Document Charge"),
            ("CXC", "Currency Exchange"),
            ("RP", "Repayment"),
        ]
        created = 0
        for code, description in seeds:
            _, was_created = TransactionType_Ext.objects.update_or_create(
                XactTypeCode_ext=code,
                defaults={"description": description},
            )
            if was_created:
                created += 1
        return created

    def _seed_account_type_ext(self):
        creditor_code = TransactionType_DE.objects.get(XactTypeCode="Cr")
        debtor_code = TransactionType_DE.objects.get(XactTypeCode="Dr")
        seeds = [
            ("Creditor", creditor_code),
            ("Debtor", debtor_code),
        ]
        created = 0
        for description, txn_code in seeds:
            _, was_created = AccountType_Ext.objects.update_or_create(
                description=description,
                defaults={"XactTypeCode": txn_code},
            )
            if was_created:
                created += 1
        return created

    def _seed_standard_ledgers(self, account_type_created_count):
        del account_type_created_count  # retained for future extension hooks

        account_types = {
            at.AccountType: at
            for at in AccountType.objects.filter(
                AccountType__in=["Asset", "Liability", "Equity", "Income", "Expense"]
            )
        }

        def ensure(name, account_type_name, sort_order, parent=None, **flags):
            defaults = {
                "AccountType": account_types[account_type_name],
                "sort_order": sort_order,
                "parent": parent,
                **flags,
            }
            ledger, created = Ledger.objects.get_or_create(name=name, defaults=defaults)

            # Keep reruns convergent, but never rewrite an already assigned code.
            updates = []
            if ledger.AccountType_id != defaults["AccountType"].id:
                ledger.AccountType = defaults["AccountType"]
                updates.append("AccountType")
            if ledger.sort_order != sort_order:
                ledger.sort_order = sort_order
                updates.append("sort_order")
            if ledger.parent_id != (parent.id if parent else None):
                ledger.parent = parent
                updates.append("parent")
            for key, value in flags.items():
                if getattr(ledger, key) != value:
                    setattr(ledger, key, value)
                    updates.append(key)
            if updates:
                ledger.save(update_fields=updates)

            return ledger, created

        created_count = 0

        # ASSETS
        current_assets, created = ensure("Current Assets", "Asset", 10)
        created_count += int(created)
        fixed_assets, created = ensure("Fixed Assets", "Asset", 20)
        created_count += int(created)

        cash_in_hand, created = ensure(
            "Cash In Hand", "Asset", 10, parent=current_assets
        )
        created_count += int(created)
        for name, order in [("Cash", 10), ("CASH", 20)]:
            _, created = ensure(name, "Asset", order, parent=cash_in_hand)
            created_count += int(created)

        bank_accounts, created = ensure(
            "Bank Accounts", "Asset", 15, parent=current_assets
        )
        created_count += int(created)
        for name, order in [("Bank Current Account", 10), ("Bank OD Account", 20)]:
            _, created = ensure(name, "Asset", order, parent=bank_accounts)
            created_count += int(created)

        loans_adv, created = ensure("Loans & Advances", "Asset", 20, parent=current_assets)
        created_count += int(created)
        for name, order in [
            ("LOAN_RECEIVABLE", 10),
            ("LOAN_PRINCIPAL_CTRL", 20),
            ("BORROWER_LOAN_CTRL", 30),
        ]:
            _, created = ensure(name, "Asset", order, parent=loans_adv)
            created_count += int(created)

        for name, order in [("Sundry Debtors", 30), ("Accounts Receivable", 35)]:
            _, created = ensure(name, "Asset", order, parent=current_assets)
            created_count += int(created)

        inventory, created = ensure("Inventory", "Asset", 40, parent=current_assets)
        created_count += int(created)
        for name, order in [("GST INV", 10), ("Non-GST INV", 20), ("INVENTORY", 30)]:
            _, created = ensure(name, "Asset", order, parent=inventory)
            created_count += int(created)

        for name, order in [
            ("Interest Receivables", 45),
            ("GST_INPUT_CREDIT", 50),
            ("Prepaid Expenses", 55),
        ]:
            _, created = ensure(name, "Asset", order, parent=current_assets)
            created_count += int(created)

        for name, order in [
            ("Plant & Machinery", 10),
            ("Furniture & Fixtures", 20),
            ("Office Equipment", 30),
            ("Vehicles", 40),
            ("Computer & Peripherals", 50),
        ]:
            _, created = ensure(name, "Asset", order, parent=fixed_assets)
            created_count += int(created)

        # LIABILITIES
        current_liabilities, created = ensure("Current Liabilities", "Liability", 10)
        created_count += int(created)
        non_current_liabilities, created = ensure(
            "Non-Current Liabilities", "Liability", 20
        )
        created_count += int(created)

        loans, created = ensure("Loans", "Liability", 10, parent=current_liabilities)
        created_count += int(created)
        for name, order in [
            ("LOAN_PAYABLE", 10),
            ("BORROWING_PRINCIPAL_CTRL", 20),
            ("LENDER_ACCOUNT_CTRL", 30),
        ]:
            _, created = ensure(name, "Liability", order, parent=loans)
            created_count += int(created)

        for name, order in [
            ("Interest Payable", 20),
            ("Sundry Creditors", 30),
            ("ACCOUNTS_PAYABLE", 35),
        ]:
            _, created = ensure(name, "Liability", order, parent=current_liabilities)
            created_count += int(created)

        duties_taxes, created = ensure(
            "Duties & Taxes", "Liability", 40, parent=current_liabilities
        )
        created_count += int(created)
        cgst, created = ensure("CGST", "Liability", 10, parent=duties_taxes)
        created_count += int(created)
        sgst, created = ensure("SGST", "Liability", 20, parent=duties_taxes)
        created_count += int(created)
        igst, created = ensure("IGST", "Liability", 30, parent=duties_taxes)
        created_count += int(created)

        for name, order, parent in [
            ("Input CGST", 10, cgst),
            ("Output CGST", 20, cgst),
            ("Input SGST", 10, sgst),
            ("Output SGST", 20, sgst),
            ("Input IGST", 10, igst),
            ("Output IGST", 20, igst),
            ("TDS_PAYABLE", 40, duties_taxes),
        ]:
            _, created = ensure(name, "Liability", order, parent=parent)
            created_count += int(created)

        for name, order in [
            ("Tax Liability", 50),
            ("Salary Payable", 55),
            ("Rent Payable", 60),
            ("Accrued Expenses", 65),
            ("Unearned Revenue", 70),
        ]:
            _, created = ensure(name, "Liability", order, parent=current_liabilities)
            created_count += int(created)

        _, created = ensure("Term Loan", "Liability", 10, parent=non_current_liabilities)
        created_count += int(created)
        _, created = ensure(
            "Security Deposits",
            "Liability",
            20,
            parent=non_current_liabilities,
            is_current_liability=False,
        )
        created_count += int(created)

        # EQUITY
        capital, created = ensure("Capital", "Equity", 10)
        created_count += int(created)
        for name, order in [
            ("Capital A/c", 10),
            ("Drawings", 20),
            ("Retained Earnings", 30),
            ("Opening Balance Equity", 40),
        ]:
            _, created = ensure(name, "Equity", order, parent=capital)
            created_count += int(created)

        # INCOME
        for name, order, flags in [
            ("Interest Received", 10, {}),
            ("INTEREST_INCOME", 12, {}),
            ("Sales", 20, {"is_operating_revenue": True}),
            ("Service Income", 30, {"is_operating_revenue": True}),
            ("Commission Income", 40, {"is_operating_revenue": True}),
            ("Other Income", 50, {}),
            ("Trading", 60, {}),
        ]:
            _, created = ensure(name, "Income", order, **flags)
            created_count += int(created)

        # EXPENSES
        for name, order, flags in [
            ("Interest Paid", 10, {}),
            ("INTEREST_EXPENSE", 12, {}),
            ("Purchase", 20, {"is_operating_expense": True}),
        ]:
            _, created = ensure(name, "Expense", order, **flags)
            created_count += int(created)

        cogs, created = ensure("COGS", "Expense", 30, is_direct_expense=True)
        created_count += int(created)
        for name, order in [("GST COGS", 10), ("Non-GST COGS", 20)]:
            _, created = ensure(
                name,
                "Expense",
                order,
                parent=cogs,
                is_direct_expense=True,
            )
            created_count += int(created)

        expenses, created = ensure("Expenses", "Expense", 99)
        created_count += int(created)
        expense_children = [
            "Travel & Transportation",
            "Food & Meals",
            "Accommodation",
            "Professional Services",
            "Office & Supplies",
            "Utilities & Communications",
            "Maintenance & Repair",
            "Marketing & Advertising",
            "Bank Charges",
            "Salary & Wages",
            "Rent Expense",
            "Insurance Expense",
            "Depreciation Expense",
            "Bad Debts",
            "Other Expense",
        ]
        for index, ledger_name in enumerate(expense_children, start=1):
            _, created = ensure(
                ledger_name,
                "Expense",
                index * 10,
                parent=expenses,
                is_operating_expense=True,
            )
            created_count += int(created)

        return created_count
