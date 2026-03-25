"""
Management command to seed core ledgers required by posting rules.
Run after migrations: python manage.py seed_core_ledgers
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django_tenants.utils import schema_context, get_tenant_model

from apps.tenant_apps.dea.models import Ledger, AccountType


class Command(BaseCommand):
    help = "Seed core ledgers (CASH, LOAN_RECEIVABLE, etc) required by posting rules"

    def add_arguments(self, parser):
        parser.add_argument(
            '--schema',
            type=str,
            help='Specific tenant schema to seed. If omitted, seeds all non-public tenant schemas.',
        )

    def handle(self, *args, **options):
        schema = options.get('schema')
        if schema:
            schemas = [schema]
        else:
            TenantModel = get_tenant_model()
            schemas = list(
                TenantModel.objects.exclude(schema_name='public')
                .values_list('schema_name', flat=True)
            )

        for s in schemas:
            self.stdout.write(f"\n--- Seeding schema: {s} ---")
            with schema_context(s):
                with transaction.atomic():
                    self._seed_ledgers()

    def _seed_ledgers(self):
        """Create core ledgers if they don't exist"""
        
        # Get or create account types
        asset_type, _ = AccountType.objects.get_or_create(
            AccountType="Asset",
            defaults={"description": "Asset Account", "code_prefix": "1"}
        )
        liability_type, _ = AccountType.objects.get_or_create(
            AccountType="Liability",
            defaults={"description": "Liability Account", "code_prefix": "2"}
        )
        income_type, _ = AccountType.objects.get_or_create(
            AccountType="Income",
            defaults={"description": "Income Account", "code_prefix": "4"}
        )
        expense_type, _ = AccountType.objects.get_or_create(
            AccountType="Expense",
            defaults={"description": "Expense Account", "code_prefix": "5"}
        )
        
        # Core ledgers required by posting rules
        ledger_configs = [
            ("CASH", asset_type, "1001"),
            # Legacy keys retained - historical data may reference these
            ("LOAN_RECEIVABLE", asset_type, "1201"),
            ("LOAN_PAYABLE", liability_type, "2201"),
            # Split-control asset ledgers (Given loan side)
            # LOAN_PRINCIPAL_CTRL: LT target - tracks internal principal fund flow
            ("LOAN_PRINCIPAL_CTRL", asset_type, "1203"),
            # BORROWER_LOAN_CTRL: AT target - party attribution for borrowers
            ("BORROWER_LOAN_CTRL", asset_type, "1204"),
            # Split-control liability ledgers (Taken loan side)
            # BORROWING_PRINCIPAL_CTRL: LT target - tracks internal borrowing fund flow
            ("BORROWING_PRINCIPAL_CTRL", liability_type, "2202"),
            # LENDER_ACCOUNT_CTRL: AT target - party attribution for lenders
            ("LENDER_ACCOUNT_CTRL", liability_type, "2203"),
            # Interest ledgers
            ("INTEREST_INCOME", income_type, "4001"),
            ("INTEREST_EXPENSE", expense_type, "5001"),
            ("INVENTORY", asset_type, "1111"),
            ("GST_INPUT_CREDIT", asset_type, "1502"),
            ("ACCOUNTS_PAYABLE", liability_type, "2102"),
            ("TDS_PAYABLE", liability_type, "2302"),
        ]
        
        created_count = 0
        for name, account_type, code in ledger_configs:
            # Check by name to avoid duplicates
            if not Ledger.objects.filter(name=name).exists():
                try:
                    Ledger.objects.create(
                        name=name,
                        code=code,
                        AccountType=account_type,
                        parent=None,
                    )
                    self.stdout.write(
                        self.style.SUCCESS(f"Created ledger: {name}")
                    )
                    created_count += 1
                except Exception as e:
                    # Try with adjusted code if duplicate
                    if "duplicate key" in str(e).lower() or "unique" in str(e).lower():
                        try:
                            # Generate new code
                            base_code = code[:2]
                            suffix_num = int(code[2:]) + 100
                            adjusted_code = f"{base_code}{suffix_num}"
                            Ledger.objects.create(
                                name=name,
                                code=adjusted_code,
                                AccountType=account_type,
                                parent=None,
                            )
                            self.stdout.write(
                                self.style.SUCCESS(f"Created ledger: {name} (code: {adjusted_code})")
                            )
                            created_count += 1
                        except Exception as e2:
                            self.stdout.write(
                                self.style.ERROR(f"Failed to create {name}: {e2}")
                            )
                    else:
                        self.stdout.write(
                            self.style.ERROR(f"Failed to create {name}: {e}")
                        )
            else:
                self.stdout.write(f"Ledger already exists: {name}")
        
        if created_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f"\nSuccessfully created {created_count} ledgers")
            )
        else:
            self.stdout.write("All core ledgers already exist")
