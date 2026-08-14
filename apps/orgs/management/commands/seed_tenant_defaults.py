from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django_tenants.utils import get_public_schema_name, schema_context

from apps.tenant_apps.dea.services.voucher_type_seed import seed_voucher_types
from apps.tenant_apps.notify.models import NoticeTypeConfig, NotificationTemplate as LegacyNotificationTemplate
from apps.tenant_apps.notify_v2.models import (
    NotificationEventType as NotifyV2EventType,
    NotificationPolicy as NotifyV2Policy,
    NotificationTemplate as NotifyV2Template,
)
from apps.tenant_apps.notify_v2.services.batch_service import seed_girvi_batch_defaults
from apps.tenant_apps.party.services import seed_party_roles
from apps.tenant_apps.product.models import Attribute, Category, Movement, ProductType


class Command(BaseCommand):
    help = "Seed tenant-schema defaults for a specific schema."

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema",
            required=True,
            help="Tenant schema name to seed.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print actions without applying changes.",
        )
        parser.add_argument(
            "--skip-dea-core",
            action="store_true",
            help="Skip DEA core ledger seeding.",
        )
        parser.add_argument(
            "--skip-terms",
            action="store_true",
            help="Skip terms fixture seeding.",
        )
        parser.add_argument(
            "--skip-rates",
            action="store_true",
            help="Skip rates fixture seeding.",
        )
        parser.add_argument(
            "--skip-product",
            action="store_true",
            help="Skip product fixture seeding.",
        )
        parser.add_argument(
            "--skip-party",
            action="store_true",
            help="Skip party role baseline seeding.",
        )
        parser.add_argument(
            "--skip-notify",
            action="store_true",
            help="Skip notify fixture seeding.",
        )
        parser.add_argument(
            "--skip-notify-v2",
            action="store_true",
            help="Skip notify_v2 baseline seeding.",
        )

    def handle(self, *args, **options):
        schema_name = options["schema"].strip()
        dry_run = options["dry_run"]

        if schema_name == get_public_schema_name():
            raise CommandError(
                "seed_tenant_defaults does not operate on public schema. "
                "Use seed_public_defaults for public data."
            )

        fixtures_dir = Path("apps/tenant_apps")
        fixture_paths = {
            "terms": fixtures_dir / "terms" / "fixtures" / "data.json",
            "rates": fixtures_dir / "rates" / "fixtures" / "metal_rates.json",
        }

        actions = []
        if not options["skip_dea_core"]:
            actions.append("seed_dea_core")
            actions.append("seed_dea_voucher_types")
        if not options["skip_terms"]:
            actions.append("seed_terms")
        if not options["skip_rates"]:
            actions.append("seed_rates")
        if not options["skip_product"]:
            actions.append("seed_product")
        if not options["skip_party"]:
            actions.append("seed_party")
        if not options["skip_notify"]:
            actions.append("seed_notify")
        if not options["skip_notify_v2"]:
            actions.append("seed_notify_v2")

        self.stdout.write(
            self.style.NOTICE(
                f"Tenant seed start: schema={schema_name}, actions={', '.join(actions) or 'none'}"
            )
        )

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run mode. No changes applied."))
            return

        with schema_context(schema_name):
            with transaction.atomic():
                if "seed_dea_core" in actions:
                    # Existing idempotent command for account types + required ledgers.
                    call_command("seed_core_ledgers", schema=schema_name)

                if "seed_dea_voucher_types" in actions:
                    self._seed_dea_voucher_types()

                if "seed_terms" in actions:
                    self._load_fixture_if_exists(fixture_paths["terms"])

                if "seed_rates" in actions:
                    # Keep call compatible with existing migration/fixture name.
                    self._load_fixture_if_exists(fixture_paths["rates"])

                if "seed_product" in actions:
                    self._seed_product_defaults()

                if "seed_party" in actions:
                    self._seed_party_defaults()

                if "seed_notify" in actions:
                    self._seed_notify_defaults()

                if "seed_notify_v2" in actions:
                    self._seed_notify_v2_defaults()

        self.stdout.write(self.style.SUCCESS(f"Tenant seed completed for schema={schema_name}"))

    def _load_fixture_if_exists(self, fixture_path):
        if not fixture_path.exists():
            self.stdout.write(
                self.style.WARNING(f"Fixture not found, skipped: {fixture_path}")
            )
            return

        self.stdout.write(f"Loading fixture: {fixture_path}")
        call_command("loaddata", str(fixture_path), verbosity=0)

    def _seed_dea_voucher_types(self):
        """Extracted from dea migration RunPython seeds (idempotent)."""
        seed_voucher_types()

    def _seed_party_defaults(self):
        result = seed_party_roles()
        self.stdout.write(
            self.style.SUCCESS(
                "Party roles ready: "
                f"created={result['created']} updated={result['updated']} total={result['total']}"
            )
        )

    def _seed_product_defaults(self):
        """
        Seed canonical product reference data extracted from product/0003_auto_fixture.py.
        Idempotent: uses get_or_create throughout.
        """
        # Movement types — required for stock/inventory posting rules
        movements = [
            ("P", "Purchase", "+"),
            ("PR", "Purchase Return", "-"),
            ("S", "Sales", "-"),
            ("SR", "Sales Return", "+"),
            ("A", "Approval", "-"),
            ("AR", "Approval Return", "+"),
            ("AD", "Add", "+"),
            ("R", "Remove", "-"),
            ("RM", "Merge Remove", "-"),
            ("SS", "Split Separate", "-"),
        ]
        for pk, name, direction in movements:
            Movement.objects.get_or_create(
                id=pk,
                defaults={"name": name, "direction": direction},
            )

        # Product categories (top-level defaults)
        for cat_name in ("Gold", "Silver"):
            Category.objects.get_or_create(name=cat_name)

        # Product types
        product_types = [
            "Coin", "Kalkass", "Drops", "Ring", "Haram", "Necklace",
            "Chain", "Choker", "Dollar", "Taali", "Gundu", "Thirupadam",
            "Urupadi", "Chippe Stone", "Mattal", "Moppu", "Minimattal",
            "Crystal tongal", "Jhapka", "Mangtika", "Jhapka Mattal",
            "Neckchain", "Pendants", "Bracelet", "Kamal", "Kamal Jumki", "Stud",
        ]
        for name in product_types:
            ProductType.objects.get_or_create(name=name)

        # Attributes
        attributes = [
            ("Purity", "purity"),
            ("Design", "design"),
            ("Size", "size"),
            ("Length", "length"),
            ("Gender", "gender"),
            ("Weight", "weight"),
            ("Initial", "initial"),
        ]
        for attr_name, attr_slug in attributes:
            Attribute.objects.get_or_create(
                name=attr_name,
                defaults={"slug": attr_slug},
            )

    def _seed_notification_template_defaults(self, notice_configs):
        """
        Seed explicit NotificationTemplate rows for the core loan reminder
        and auction workflows.

        Uses get_or_create so tenant-edited templates are preserved on reseed.
        """
        loan_notice_codes = (
            "LOAN_FIRST_REMINDER",
            "LOAN_SECOND_REMINDER",
            "LOAN_FINAL_NOTICE",
            "LOAN_AUCTION_NOTICE",
        )

        for code in loan_notice_codes:
            notice_type = notice_configs.get(code) or NoticeTypeConfig.objects.filter(
                code=code
            ).first()
            if not notice_type:
                continue

            template_rows = [
                {
                    "name": "Default Letter PDF",
                    "medium_type": "L",
                    "renderer": LegacyNotificationTemplate.RendererType.PDF,
                    "pdf_template_key": code.lower(),
                    "sort_order": 10,
                },
                {
                    "name": "Default Post PDF",
                    "medium_type": "P",
                    "renderer": LegacyNotificationTemplate.RendererType.PDF,
                    "pdf_template_key": code.lower(),
                    "sort_order": 20,
                },
                {
                    "name": "Default Email Template",
                    "medium_type": "E",
                    "renderer": LegacyNotificationTemplate.RendererType.DJANGO,
                    "subject_template": (
                        notice_type.email_subject_template or notice_type.name
                    ),
                    "body_template": (
                        notice_type.email_template or notice_type.postal_template
                    ),
                    "sort_order": 30,
                },
                {
                    "name": "Default SMS Template",
                    "medium_type": "S",
                    "renderer": LegacyNotificationTemplate.RendererType.DJANGO,
                    "body_template": (
                        notice_type.sms_template or notice_type.email_template
                    ),
                    "sort_order": 40,
                },
                {
                    "name": "Default WhatsApp Template",
                    "medium_type": "W",
                    "renderer": LegacyNotificationTemplate.RendererType.DJANGO,
                    "body_template": (
                        notice_type.whatsapp_template
                        or notice_type.sms_template
                        or notice_type.email_template
                    ),
                    "sort_order": 50,
                },
            ]

            for template_data in template_rows:
                LegacyNotificationTemplate.objects.get_or_create(
                    notice_type_config=notice_type,
                    medium_type=template_data["medium_type"],
                    name=template_data["name"],
                    defaults={
                        "renderer": template_data["renderer"],
                        "subject_template": template_data.get("subject_template", ""),
                        "body_template": template_data.get("body_template", ""),
                        "pdf_template_key": template_data.get("pdf_template_key", ""),
                        "sort_order": template_data["sort_order"],
                        "is_active": True,
                    },
                )

    def _seed_notify_v2_defaults(self):
        """Seed baseline notify_v2 configuration for Girvi reminder and recovery flows."""
        event_keys = (
            "loan.first_reminder_due",
            "loan.second_reminder_due",
            "loan.final_notice_due",
            "loan.auction_notice_due",
        )
        seed_girvi_batch_defaults(event_keys=event_keys)

        self.stdout.write(
            self.style.SUCCESS(
                "Notify V2 defaults ready: "
                f"event_types={NotifyV2EventType.objects.filter(key__in=event_keys).count()} "
                f"policies={NotifyV2Policy.objects.filter(event_type__key__in=event_keys).count()} "
                f"templates={NotifyV2Template.objects.filter(event_type__key__in=event_keys).count()}"
            )
        )

    def _seed_notify_defaults(self):
        """
        Seed default NoticeTypeConfig and NotificationTemplate records for notify.
        Idempotent for all records; `LOAN_AUCTION_NOTICE` is refreshed via update_or_create
        so existing tenants pick up the dedicated auction template text on reseed.
        """
        default_types = [
            {
                "code": "LOAN_FIRST_REMINDER",
                "name": "First Reminder",
                "category": "LOAN",
                "description": "First reminder for loan payment or renewal",
                "sort_order": 1,
                "sms_template": "Dear {{customer.name}}, this is a first reminder for your loan {{items.0.reference}}. Amount: {{items.0.amount}}. Please contact us.",
                "email_subject_template": "First Reminder - Loan {{items.0.reference}}",
                "email_template": "Dear {{customer.name}},\n\nThis is a first reminder regarding your loan:\n{% for item in items %}\n- Loan ID: {{item.reference}}, Amount: \u20b9{{item.amount}}, Due: {{item.due_date}}\n{% endfor %}\n\nPlease contact us for repayment or renewal.",
                "postal_template": "Dear {{customer.name}},\n\nThis is a first reminder regarding your loan(s):\n{% for item in items %}\nLoan ID: {{item.reference}}\nAmount: \u20b9{{item.amount}}\nDue Date: {{item.due_date}}\n{% endfor %}\n\nPlease visit our office or contact us for repayment.",
            },
            {
                "code": "LOAN_SECOND_REMINDER",
                "name": "Second Reminder",
                "category": "LOAN",
                "description": "Second reminder for overdue loan with urgency",
                "sort_order": 2,
                "sms_template": "URGENT: Second reminder for loan {{items.0.reference}}. Amount: \u20b9{{items.0.amount}}. Please visit immediately.",
                "email_subject_template": "URGENT: Second Reminder - Loan {{items.0.reference}}",
                "email_template": "Dear {{customer.name}},\n\nThis is your SECOND reminder. Your loan(s) are overdue:\n{% for item in items %}\n- Loan ID: {{item.reference}}, Amount: \u20b9{{item.amount}}, Overdue Since: {{item.due_date}}\n{% endfor %}\n\nImmediate action required. Please contact us.",
                "postal_template": "Dear {{customer.name}},\n\nSECOND REMINDER - URGENT\n\nYour loan(s) are now overdue:\n{% for item in items %}\nLoan ID: {{item.reference}}\nAmount: \u20b9{{item.amount}}\nOverdue Since: {{item.due_date}}\n{% endfor %}\n\nPlease visit immediately.",
            },
            {
                "code": "LOAN_FINAL_NOTICE",
                "name": "Final Notice",
                "category": "LOAN",
                "description": "Final notice before legal action or auction",
                "sort_order": 3,
                "sms_template": "FINAL NOTICE: Loan {{items.0.reference}} overdue. Legal action pending. Visit immediately.",
                "email_subject_template": "FINAL NOTICE - Loan {{items.0.reference}}",
                "email_template": "Dear {{customer.name}},\n\nFINAL NOTICE\n\nYour loan(s) are severely overdue:\n{% for item in items %}\n- Loan ID: {{item.reference}}, Amount: \u20b9{{item.amount}}, Overdue Since: {{item.due_date}}\n{% endfor %}\n\nFinal opportunity to clear dues before legal proceedings.",
                "postal_template": "Dear {{customer.name}},\n\nFINAL NOTICE\n\nThis is your final notice before legal action.\n\nOverdue Loans:\n{% for item in items %}\nLoan ID: {{item.reference}}\nAmount: \u20b9{{item.amount}}\nOverdue Since: {{item.due_date}}\n{% endfor %}\n\nPlease settle immediately.",
            },
            {
                "code": "LOAN_AUCTION_NOTICE",
                "name": "Auction Notice",
                "category": "LOAN",
                "description": "Notice issued when a defaulted loan is moved into the auction recovery path",
                "sort_order": 4,
                "sms_template": "AUCTION NOTICE: Loan {{items.0.reference}} is in the auction recovery process. Please contact us immediately.",
                "email_subject_template": "Auction Notice - Loan {{items.0.reference}}",
                "email_template": "Dear {{customer.name}},\n\nYour loan has entered the auction recovery process:\n{% for item in items %}\n- Loan ID: {{item.reference}}\n- Amount: \u20b9{{item.amount}}\n- Auction / due date: {{item.due_date}}\n{% endfor %}\n\nPlease contact us immediately if you wish to settle the dues before completion.",
                "postal_template": "Dear {{customer.name}},\n\nAUCTION NOTICE\n\nThis notice is to inform you that the following loan has entered the auction recovery process:\n{% for item in items %}\nLoan ID: {{item.reference}}\nAmount: \u20b9{{item.amount}}\nAuction / due date: {{item.due_date}}\n{% endfor %}\n\nPlease contact our office immediately if you wish to regularise the account.",
            },
            {
                "code": "LOAN_CREATED",
                "name": "Loan Created/Disbursed",
                "category": "LOAN",
                "description": "Welcome notification when new loan is created",
                "sort_order": 5,
                "sms_template": "Your loan {{items.0.reference}} of \u20b9{{items.0.amount}} has been approved. Thank you!",
                "email_subject_template": "Loan Approved - {{items.0.reference}}",
                "email_template": "Dear {{customer.name}},\n\nYour loan has been successfully approved:\n{% for item in items %}\n- Loan ID: {{item.reference}}\n- Amount: \u20b9{{item.amount}}\n- Due Date: {{item.due_date}}\n{% endfor %}\n\nThank you for choosing our services.",
                "postal_template": "Dear {{customer.name}},\n\nLoan Approval Confirmation\n\n{% for item in items %}\nLoan ID: {{item.reference}}\nAmount: \u20b9{{item.amount}}\nDue Date: {{item.due_date}}\n{% endfor %}\n\nThank you!",
            },
            {
                "code": "LOAN_MATURITY_ALERT",
                "name": "Loan Maturity Alert",
                "category": "LOAN",
                "description": "Proactive alert before loan matures",
                "sort_order": 6,
                "sms_template": "Your loan {{items.0.reference}} matures on {{items.0.due_date}}. Please plan repayment.",
                "email_subject_template": "Loan Maturity Alert - {{items.0.reference}}",
                "email_template": "Dear {{customer.name}},\n\nYour loan will mature soon:\n{% for item in items %}\n- Loan ID: {{item.reference}}\n- Amount: \u20b9{{item.amount}}\n- Maturity Date: {{item.due_date}}\n{% endfor %}\n\nPlease plan for repayment or renewal.",
            },
            {
                "code": "INVOICE_REMINDER",
                "name": "Invoice Payment Reminder",
                "category": "SALES",
                "description": "Reminder for unpaid invoices",
                "sort_order": 10,
                "sms_template": "Invoice {{items.0.reference}} of \u20b9{{items.0.amount}} is pending. Due: {{items.0.due_date}}",
                "email_subject_template": "Payment Reminder - Invoice {{items.0.reference}}",
                "email_template": "Dear {{customer.name}},\n\nYour invoice(s) are pending payment:\n{% for item in items %}\n- Invoice #: {{item.reference}}\n- Amount: \u20b9{{item.amount}}\n- Due Date: {{item.due_date}}\n{% endfor %}\n\nPlease pay at your earliest convenience.",
            },
            {
                "code": "SALES_CONFIRMATION",
                "name": "Sale/Order Confirmation",
                "category": "SALES",
                "description": "Confirmation after successful sale",
                "sort_order": 11,
                "sms_template": "Order confirmed! Order #{{items.0.reference}} for \u20b9{{items.0.amount}}. Thank you!",
                "email_subject_template": "Order Confirmation - {{items.0.reference}}",
                "email_template": "Dear {{customer.name}},\n\nThank you for your order!\n\nOrder Details:\n{% for item in items %}\n- Order #: {{item.reference}}\n- Amount: \u20b9{{item.amount}}\n{% endfor %}\n\nWe will process your order shortly.",
            },
            {
                "code": "DELIVERY_UPDATE",
                "name": "Delivery Status Update",
                "category": "SALES",
                "description": "Notification about delivery or shipment",
                "sort_order": 12,
                "sms_template": "Your order {{items.0.reference}} is out for delivery. Track your shipment.",
                "email_subject_template": "Delivery Update - Order {{items.0.reference}}",
                "email_template": "Dear {{customer.name}},\n\nYour order is on its way:\n{% for item in items %}\n- Order #: {{item.reference}}\n{% endfor %}\n\nExpected delivery soon.",
            },
            {
                "code": "PO_CREATED",
                "name": "Purchase Order Created",
                "category": "PURCHASE",
                "description": "Notification to vendor when PO is created",
                "sort_order": 20,
                "sms_template": "PO {{items.0.reference}} created for \u20b9{{items.0.amount}}. Please confirm.",
                "email_subject_template": "Purchase Order - {{items.0.reference}}",
                "email_template": "Dear Vendor,\n\nWe have created a purchase order:\n{% for item in items %}\n- PO #: {{item.reference}}\n- Amount: \u20b9{{item.amount}}\n{% endfor %}\n\nPlease confirm receipt and delivery schedule.",
            },
            {
                "code": "PO_DELIVERY_REMINDER",
                "name": "PO Delivery Reminder",
                "category": "PURCHASE",
                "description": "Reminder to vendor about pending delivery",
                "sort_order": 21,
                "sms_template": "Reminder: PO {{items.0.reference}} delivery pending. Expected: {{items.0.due_date}}",
                "email_subject_template": "Delivery Reminder - PO {{items.0.reference}}",
                "email_template": "Dear Vendor,\n\nThis is a reminder for pending delivery:\n{% for item in items %}\n- PO #: {{item.reference}}\n- Expected Date: {{item.due_date}}\n{% endfor %}\n\nPlease update us on the status.",
            },
            {
                "code": "STOCK_LOW_ALERT",
                "name": "Low Stock Alert",
                "category": "INVENTORY",
                "description": "Alert when stock falls below threshold",
                "sort_order": 30,
                "sms_template": "Low stock alert for {{items.0.reference}}. Current: {{items.0.amount}} units.",
                "email_subject_template": "Low Stock Alert - {{items.0.reference}}",
                "email_template": "Dear Team,\n\nThe following items are running low:\n{% for item in items %}\n- Item: {{item.reference}}\n- Current Stock: {{item.amount}} units\n{% endfor %}\n\nPlease reorder.",
            },
            {
                "code": "STOCK_REORDER",
                "name": "Stock Reorder Notification",
                "category": "INVENTORY",
                "description": "Notification to supplier for reordering",
                "sort_order": 31,
                "sms_template": "Reorder request for {{items.0.reference}}. Quantity: {{items.0.amount}}",
                "email_subject_template": "Reorder Request - {{items.0.reference}}",
                "email_template": "Dear Supplier,\n\nWe need to reorder:\n{% for item in items %}\n- Item: {{item.reference}}\n- Quantity: {{item.amount}}\n{% endfor %}\n\nPlease confirm delivery schedule.",
            },
            {
                "code": "GST_FILING_REMINDER",
                "name": "GST Filing Reminder",
                "category": "ACCOUNTING",
                "description": "Reminder for upcoming GST filing deadline",
                "sort_order": 40,
                "sms_template": "GST filing due on {{items.0.due_date}}. Please prepare documents.",
                "email_subject_template": "GST Filing Reminder - Due {{items.0.due_date}}",
                "email_template": "Dear Customer,\n\nYour GST filing is due on {{items.0.due_date}}.\n\nPlease ensure all documents are ready.\n\nContact us if you need assistance.",
            },
            {
                "code": "STATEMENT_DELIVERY",
                "name": "Account Statement",
                "category": "ACCOUNTING",
                "description": "Monthly or periodic account statement",
                "sort_order": 41,
                "sms_template": "Your account statement for {{items.0.reference}} is ready.",
                "email_subject_template": "Account Statement - {{items.0.reference}}",
                "email_template": "Dear {{customer.name}},\n\nYour account statement is attached.\n\nPeriod: {{items.0.reference}}\n\nPlease review and contact us for any queries.",
            },
            {
                "code": "PAYSLIP_DELIVERY",
                "name": "Salary Slip Delivery",
                "category": "HR",
                "description": "Monthly salary slip delivery to employees",
                "sort_order": 50,
                "sms_template": "Your salary for {{items.0.reference}} has been credited. Amount: \u20b9{{items.0.amount}}",
                "email_subject_template": "Salary Slip - {{items.0.reference}}",
                "email_template": "Dear Employee,\n\nYour salary slip for {{items.0.reference}} is attached.\n\nNet Pay: \u20b9{{items.0.amount}}\n\nPlease check and confirm receipt.",
            },
            {
                "code": "LEAVE_APPROVED",
                "name": "Leave Approval Notification",
                "category": "HR",
                "description": "Notification when leave is approved",
                "sort_order": 51,
                "sms_template": "Your leave request for {{items.0.reference}} has been approved.",
                "email_subject_template": "Leave Approved - {{items.0.reference}}",
                "email_template": "Dear Employee,\n\nYour leave request has been approved:\n- Dates: {{items.0.reference}}\n- Duration: {{items.0.amount}} days\n\nEnjoy your time off!",
            },
            {
                "code": "BIRTHDAY_WISH",
                "name": "Birthday Greeting",
                "category": "GENERAL",
                "description": "Automated birthday wishes to customers",
                "sort_order": 60,
                "sms_template": "Happy Birthday {{customer.name}}! Wishing you a wonderful year ahead!",
                "email_subject_template": "Happy Birthday {{customer.name}}!",
                "email_template": "Dear {{customer.name}},\n\nWishing you a very Happy Birthday!\n\nMay this year bring you joy, success, and prosperity.\n\nWith best wishes,\nYour Team",
            },
            {
                "code": "PROMOTIONAL_CAMPAIGN",
                "name": "Promotional Campaign",
                "category": "GENERAL",
                "description": "Marketing and promotional messages",
                "sort_order": 61,
                "sms_template": "Special offer! {{items.0.reference}}. Visit us today!",
                "email_subject_template": "Special Offer - {{items.0.reference}}",
                "email_template": "Dear {{customer.name}},\n\nWe have an exciting offer for you!\n\n{{items.0.reference}}\n\nVisit us to avail this limited-time offer.",
            },
            {
                "code": "ANNOUNCEMENT",
                "name": "General Announcement",
                "category": "GENERAL",
                "description": "Company announcements and updates",
                "sort_order": 62,
                "sms_template": "Announcement: {{items.0.reference}}",
                "email_subject_template": "Important Announcement - {{items.0.reference}}",
                "email_template": "Dear {{customer.name}},\n\nWe have an important announcement:\n\n{{items.0.reference}}\n\nThank you for your attention.",
            },
        ]
        seeded_notice_types = {}
        for notice_data in default_types:
            code = notice_data["code"]
            if code == "LOAN_AUCTION_NOTICE":
                notice_type, _created = NoticeTypeConfig.objects.update_or_create(
                    code=code,
                    defaults=notice_data,
                )
            else:
                notice_type, _created = NoticeTypeConfig.objects.get_or_create(
                    code=code,
                    defaults=notice_data,
                )
            seeded_notice_types[code] = notice_type

        self._seed_notification_template_defaults(seeded_notice_types)
