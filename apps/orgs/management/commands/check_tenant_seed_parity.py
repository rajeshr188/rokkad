from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import get_public_schema_name, get_tenant_model, schema_context


class Command(BaseCommand):
    help = "Compare tenant seed baseline counts against a reference schema."

    EXPECTED_SEEDS = {
        "dea.AccountType": {
            "field": "AccountType",
            "values": ["Asset", "Liability", "Equity", "Income", "Expense"],
        },
        "dea.EntityType": {
            "field": "name",
            "values": ["Person", "Organisation"],
        },
        "dea.TransactionType_DE": {
            "field": "XactTypeCode",
            "values": ["Cr", "Dr"],
        },
        "dea.TransactionType_Ext": {
            "field": "XactTypeCode_ext",
            "values": [
                "AC",
                "AD",
                "CPU",
                "CRPU",
                "CRSL",
                "CSL",
                "IP",
                "IR",
                "LG",
                "LT",
                "LR",
                "LP",
                "PYT",
                "RCT",
                "DC",
                "CXC",
                "RP",
            ],
        },
        "dea.AccountType_Ext": {
            "field": "description",
            "values": ["Creditor", "Debtor"],
        },
        "dea.Ledger": {
            "field": "name",
            "values": [
                "CASH",
                "LOAN_RECEIVABLE",
                "LOAN_PAYABLE",
                "LOAN_PRINCIPAL_CTRL",
                "BORROWER_LOAN_CTRL",
                "BORROWING_PRINCIPAL_CTRL",
                "LENDER_ACCOUNT_CTRL",
                "INTEREST_INCOME",
                "INTEREST_EXPENSE",
                "INVENTORY",
                "GST_INPUT_CREDIT",
                "ACCOUNTS_PAYABLE",
                "TDS_PAYABLE",
            ],
        },
        "dea.VoucherType": {
            "field": "name",
            "values": [
                "GIVENLOAN_RECEIPT",
                "GIVENLOAN_PAYMENT",
                "TAKENLOAN_RECEIPT",
                "TAKENLOAN_PAYMENT",
                "GIVENLOAN_RELEASE",
                "EXPENSE_EMP_CLAIM",
                "EXPENSE_VENDOR_BILL",
                "EXPENSE_DIRECT_PAYMENT",
                "EXPENSE_REIMBURSEMENT",
                "EXPENSE_OTHER",
            ],
        },
        "product.Category": {
            "field": "name",
            "values": ["Gold", "Silver"],
        },
        "product.ProductType": {
            "field": "name",
            "values": [
                "Coin", "Kalkass", "Drops", "Ring", "Haram", "Necklace",
                "Chain", "Choker", "Dollar", "Taali", "Gundu", "Thirupadam",
                "Urupadi", "Chippe Stone", "Mattal", "Moppu", "Minimattal",
                "Crystal tongal", "Jhapka", "Mangtika", "Jhapka Mattal",
                "Neckchain", "Pendants", "Bracelet", "Kamal", "Kamal Jumki", "Stud",
            ],
        },
        "product.Movement": {
            "field": "id",
            "values": ["P", "PR", "S", "SR", "A", "AR", "AD", "R", "RM", "SS"],
        },
        "notify.NoticeTypeConfig": {
            "field": "code",
            "values": [
                "LOAN_FIRST_REMINDER",
                "LOAN_SECOND_REMINDER",
                "LOAN_FINAL_NOTICE",
                "LOAN_CREATED",
                "LOAN_MATURITY_ALERT",
                "INVOICE_REMINDER",
                "SALES_CONFIRMATION",
                "DELIVERY_UPDATE",
                "PO_CREATED",
                "PO_DELIVERY_REMINDER",
                "STOCK_LOW_ALERT",
                "STOCK_REORDER",
                "GST_FILING_REMINDER",
                "STATEMENT_DELIVERY",
                "PAYSLIP_DELIVERY",
                "LEAVE_APPROVED",
                "BIRTHDAY_WISH",
                "PROMOTIONAL_CAMPAIGN",
                "ANNOUNCEMENT",
            ],
        },
    }

    def add_arguments(self, parser):
        parser.add_argument(
            "--baseline-schema",
            required=True,
            help="Tenant schema to use as baseline for comparison.",
        )
        parser.add_argument(
            "--schema",
            help="Compare only one target schema. If omitted, compares all tenants except baseline.",
        )
        parser.add_argument(
            "--fail-on-drift",
            action="store_true",
            help="Return non-zero exit when any drift is detected.",
        )

    def handle(self, *args, **options):
        baseline_schema = options["baseline_schema"].strip()
        target_schema = (options.get("schema") or "").strip() or None

        if baseline_schema == get_public_schema_name():
            raise CommandError("Baseline schema must be a tenant schema, not public.")

        TenantModel = get_tenant_model()
        if target_schema:
            target_schemas = [target_schema]
        else:
            target_schemas = list(
                TenantModel.objects.exclude(schema_name=get_public_schema_name())
                .exclude(schema_name=baseline_schema)
                .values_list("schema_name", flat=True)
            )

        total_drift = 0
        for schema_name in target_schemas:
            drift = self._compare_schema(schema_name)
            total_drift += drift

        if total_drift == 0:
            self.stdout.write(self.style.SUCCESS("Seed parity check passed: no drift."))
            return

        self.stderr.write(self.style.WARNING(f"Seed parity drift entries: {total_drift}"))
        if options["fail_on_drift"]:
            raise CommandError("Seed parity drift detected.")

    def _compare_schema(self, schema_name):
        drift = 0
        self.stdout.write(f"Comparing schema: {schema_name}")

        with schema_context(schema_name):
            for key, cfg in self.EXPECTED_SEEDS.items():
                app_label, model_name = key.split(".")
                model = apps.get_model(app_label, model_name)
                field = cfg["field"]
                expected = set(cfg["values"])
                current = set(model.objects.filter(**{f"{field}__in": list(expected)}).values_list(field, flat=True))
                missing = sorted(expected - current)
                if missing:
                    drift += 1
                    self.stderr.write(f"  DRIFT {key}: missing={missing}")

        if drift == 0:
            self.stdout.write(self.style.SUCCESS("  OK"))
        return drift
