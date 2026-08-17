"""Create or reconcile the development subscription plan catalog."""

from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.subscriptions.models import Plan


PLAN_CATALOG = (
    {
        "tier": Plan.PlanTierChoices.STARTER,
        "name": "Starter",
        "price": Decimal("999.00"),
        "yearly_price": Decimal("9990.00"),
        "description": "Core pawn-lending operations for a small team.",
        "max_users": 5,
        "max_transactions_per_month": 500,
        "has_advanced_reporting": False,
        "has_approvals_workflow": False,
        "has_api_access": False,
        "has_custom_fields": False,
        "trial_days": 14,
    },
    {
        "tier": Plan.PlanTierChoices.PROFESSIONAL,
        "name": "Professional",
        "price": Decimal("3999.00"),
        "yearly_price": Decimal("39990.00"),
        "description": "Higher team capacity and advanced operational workflows.",
        "max_users": 50,
        "max_transactions_per_month": 10000,
        "has_advanced_reporting": True,
        "has_approvals_workflow": True,
        "has_api_access": False,
        "has_custom_fields": True,
        "trial_days": 14,
    },
    {
        "tier": Plan.PlanTierChoices.ENTERPRISE,
        "name": "Enterprise",
        "price": Decimal("0.00"),
        "yearly_price": Decimal("0.00"),
        "description": "Custom capacity, integrations, and support.",
        "max_users": 999,
        "max_transactions_per_month": 999999,
        "has_advanced_reporting": True,
        "has_approvals_workflow": True,
        "has_api_access": True,
        "has_custom_fields": True,
        "trial_days": 30,
    },
)


class Command(BaseCommand):
    help = "Create or reconcile the default development subscription plans"

    def handle(self, *args, **options):
        for definition in PLAN_CATALOG:
            tier = definition["tier"]
            defaults = {
                **definition,
                "billing_cycle": Plan.BillingCycleChoices.MONTHLY,
                "extra_user_price": Decimal("99.00"),
                "is_active": True,
                # Retired inventory-era fields remain in the schema temporarily
                # but must not advertise or grant a current product capability.
                "max_products": 0,
                "max_warehouses": 0,
                "max_invoices_per_month": 0,
                "has_multi_warehouse": False,
            }
            defaults.pop("tier")
            _, created = Plan.objects.update_or_create(tier=tier, defaults=defaults)
            action = "Created" if created else "Updated"
            self.stdout.write(self.style.SUCCESS(f"{action} {definition['name']} plan"))
