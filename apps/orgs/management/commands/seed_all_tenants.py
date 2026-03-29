from django.core.management import call_command
from django.core.management.base import BaseCommand
from django_tenants.utils import get_public_schema_name, get_tenant_model


class Command(BaseCommand):
    help = "Seed defaults for all tenant schemas using seed_tenant_defaults."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print target schemas without applying seeds.",
        )
        parser.add_argument(
            "--continue-on-error",
            action="store_true",
            help="Continue seeding remaining schemas if one fails.",
        )
        parser.add_argument(
            "--skip-dea-core",
            action="store_true",
        )
        parser.add_argument(
            "--skip-terms",
            action="store_true",
        )
        parser.add_argument(
            "--skip-rates",
            action="store_true",
        )
        parser.add_argument(
            "--skip-product",
            action="store_true",
        )
        parser.add_argument(
            "--skip-notify",
            action="store_true",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        continue_on_error = options["continue_on_error"]

        TenantModel = get_tenant_model()
        schemas = list(
            TenantModel.objects.exclude(schema_name=get_public_schema_name())
            .values_list("schema_name", flat=True)
        )

        self.stdout.write(self.style.NOTICE(f"Found {len(schemas)} tenant schemas"))

        if dry_run:
            for schema_name in schemas:
                self.stdout.write(f"Would seed schema: {schema_name}")
            return

        seeded = 0
        failed = []

        for schema_name in schemas:
            self.stdout.write(f"Seeding schema: {schema_name}")
            try:
                call_command(
                    "seed_tenant_defaults",
                    schema=schema_name,
                    skip_dea_core=options["skip_dea_core"],
                    skip_terms=options["skip_terms"],
                    skip_rates=options["skip_rates"],
                    skip_product=options["skip_product"],
                    skip_notify=options["skip_notify"],
                )
                seeded += 1
            except Exception as exc:  # noqa: BLE001
                failed.append((schema_name, str(exc)))
                self.stderr.write(self.style.ERROR(f"Failed: {schema_name} -> {exc}"))
                if not continue_on_error:
                    break

        self.stdout.write(self.style.SUCCESS(f"Seeded schemas: {seeded}"))
        if failed:
            self.stderr.write(self.style.ERROR(f"Failed schemas: {len(failed)}"))
            for schema_name, error in failed:
                self.stderr.write(f"- {schema_name}: {error}")
