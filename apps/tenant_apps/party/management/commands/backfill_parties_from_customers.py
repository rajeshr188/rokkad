from django.core.management.base import BaseCommand
from django_tenants.utils import schema_context

from apps.tenant_apps.party.services.customer_bridge import backfill_customer_parties


class Command(BaseCommand):
    help = "Backfill Party records and roles from legacy contact.Customer rows."

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema",
            help="Tenant schema name. If omitted, uses the current connection schema.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report how many customers would be processed without applying changes.",
        )
        parser.add_argument(
            "--only-missing",
            action="store_true",
            help="Only process customers that do not yet have a linked party.",
        )

    def handle(self, *args, **options):
        schema_name = options.get("schema")

        if options["dry_run"]:
            count = self._count_customers(schema_name)
            self.stdout.write(f"Would process {count} customer(s).")
            return

        if schema_name:
            with schema_context(schema_name):
                result = self._backfill(only_missing=options["only_missing"])
        else:
            result = self._backfill(only_missing=options["only_missing"])

        self.stdout.write(
            self.style.SUCCESS(
                "Customer party backfill complete: "
                f"processed={result.processed} linked={result.linked} "
                f"created={result.created} roles_created={result.roles_created}"
            )
        )

    def _backfill(self, only_missing=False):
        from apps.tenant_apps.contact.models import Customer

        queryset = Customer.objects.all()
        if only_missing:
            queryset = queryset.filter(party__isnull=True)
        return backfill_customer_parties(queryset=queryset)

    def _count_customers(self, schema_name):
        from apps.tenant_apps.contact.models import Customer

        if schema_name:
            with schema_context(schema_name):
                return Customer.objects.count()
        return Customer.objects.count()
