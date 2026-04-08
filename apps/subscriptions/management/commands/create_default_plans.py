"""
Management command to create default subscription plans for Indian SaaS market.
Usage: python manage.py create_default_plans
"""

from django.core.management.base import BaseCommand
from apps.subscriptions.models import Plan
from decimal import Decimal


class Command(BaseCommand):
    help = "Create default subscription plans for Indian SaaS market"

    def handle(self, *args, **options):
        # Delete existing plans if they exist
        if Plan.objects.filter(tier="starter").exists():
            self.stdout.write(
                self.style.WARNING("Plans already exist. Skipping creation.")
            )
            return

        # Starter Plan - ₹999/month
        Plan.objects.create(
            name="Starter",
            tier="starter",
            price=Decimal("999.00"),
            yearly_price=Decimal("9990.00"),  # 20% discount
            description="Perfect for small businesses starting their digital journey",
            billing_cycle="monthly",
            max_users=5,
            max_products=100,
            max_warehouses=1,
            max_transactions_per_month=500,
            max_invoices_per_month=500,
            has_advanced_reporting=False,
            has_multi_warehouse=False,
            has_approvals_workflow=False,
            has_api_access=False,
            has_custom_fields=False,
            trial_days=14,
            extra_user_price=Decimal("99.00"),
            is_active=True,
        )
        self.stdout.write(self.style.SUCCESS("✓ Created Starter plan (₹999/month)"))

        # Professional Plan - ₹3,999/month
        Plan.objects.create(
            name="Professional",
            tier="professional",
            price=Decimal("3999.00"),
            yearly_price=Decimal("39990.00"),  # 20% discount
            description="Ideal for growing businesses with advanced operational needs",
            billing_cycle="monthly",
            max_users=50,
            max_products=2000,
            max_warehouses=5,
            max_transactions_per_month=10000,
            max_invoices_per_month=10000,
            has_advanced_reporting=True,
            has_multi_warehouse=True,
            has_approvals_workflow=True,
            has_api_access=False,
            has_custom_fields=True,
            trial_days=14,
            extra_user_price=Decimal("99.00"),
            is_active=True,
        )
        self.stdout.write(
            self.style.SUCCESS("✓ Created Professional plan (₹3,999/month)")
        )

        # Enterprise Plan - Custom pricing
        Plan.objects.create(
            name="Enterprise",
            tier="enterprise",
            price=Decimal("0.00"),  # Custom pricing
            yearly_price=Decimal("0.00"),
            description="Full-featured solution with dedicated support and custom integrations",
            billing_cycle="yearly",
            max_users=999,
            max_products=999999,
            max_warehouses=999,
            max_transactions_per_month=999999,
            max_invoices_per_month=999999,
            has_advanced_reporting=True,
            has_multi_warehouse=True,
            has_approvals_workflow=True,
            has_api_access=True,
            has_custom_fields=True,
            trial_days=30,
            extra_user_price=Decimal("0.00"),  # Negotiable
            is_active=True,
        )
        self.stdout.write(
            self.style.SUCCESS("✓ Created Enterprise plan (Custom pricing)")
        )

        self.stdout.write(
            self.style.SUCCESS("\n✅ All default plans created successfully!")
        )
        self.stdout.write(
            self.style.WARNING(
                "\n📋 Next steps:\n"
                "1. Update RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET in settings.py\n"
                "2. Create a webhook endpoint for payment status updates\n"
                "3. Add payment processing views\n"
                "4. Create customer billing portal"
            )
        )
