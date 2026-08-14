from django.core.management.base import BaseCommand

from apps.subscriptions.models import Subscription
from apps.subscriptions.services import (
    ensure_billing_account_for_subscription,
    ensure_entitlements_for_subscription,
)


class Command(BaseCommand):
    help = "Backfill billing accounts and entitlements for existing subscriptions"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be created or updated without writing to the database.",
        )

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)
        subscriptions = Subscription.objects.select_related("company", "plan").all()
        created_accounts = 0
        created_entitlements = 0
        updated_accounts = 0
        updated_entitlements = 0

        for subscription in subscriptions:
            account, account_created = ensure_billing_account_for_subscription(
                subscription,
                dry_run=dry_run,
            )
            if dry_run:
                if account_created:
                    created_accounts += 1
                elif account is not None:
                    updated_accounts += 1
            else:
                if account_created:
                    created_accounts += 1
                elif account is not None:
                    updated_accounts += 1

            entitlements = ensure_entitlements_for_subscription(
                subscription,
                dry_run=dry_run,
            )
            if entitlements:
                created_entitlement_count = sum(1 for _, created in entitlements if created)
                created_entitlements += created_entitlement_count
                updated_entitlements += len(entitlements) - created_entitlement_count

        self.stdout.write(
            self.style.SUCCESS(
                f"Backfill complete: accounts created={created_accounts}, accounts updated={updated_accounts}, entitlements created={created_entitlements}, entitlements updated={updated_entitlements}"
            )
        )
