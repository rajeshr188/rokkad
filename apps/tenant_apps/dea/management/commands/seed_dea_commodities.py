from django.core.management.base import BaseCommand
from django.db import transaction
from django_tenants.utils import schema_context

from apps.tenant_apps.dea.services.commodity_seed import (
    CANONICAL_COMMODITIES,
    seed_default_commodities,
)


class Command(BaseCommand):
    help = "Seed DEA default commodity master records in a tenant schema."

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema",
            help="Tenant schema name. If omitted, uses the current connection schema.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be seeded without applying changes.",
        )

    def handle(self, *args, **options):
        schema_name = options.get("schema")

        if options["dry_run"]:
            codes = ", ".join(commodity.code for commodity in CANONICAL_COMMODITIES)
            self.stdout.write(f"Would seed DEA commodities: {codes}")
            return

        if schema_name:
            with schema_context(schema_name):
                result = self._seed()
        else:
            result = self._seed()

        self.stdout.write(
            self.style.SUCCESS(
                "DEA commodities ready: "
                f"created={result['created']} "
                f"updated={result['updated']} "
                f"total={result['total']}"
            )
        )

    def _seed(self):
        with transaction.atomic():
            return seed_default_commodities()
