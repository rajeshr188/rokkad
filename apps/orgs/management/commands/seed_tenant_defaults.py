from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django_tenants.utils import get_public_schema_name, schema_context

from apps.tenant_apps.party.services import seed_party_roles


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
            "--skip-rates",
            action="store_true",
            help="Skip rates fixture seeding.",
        )
        parser.add_argument(
            "--skip-party",
            action="store_true",
            help="Skip party role baseline seeding.",
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
            "rates": fixtures_dir / "rates" / "fixtures" / "metal_rates.json",
        }

        actions = []
        if not options["skip_rates"]:
            actions.append("seed_rates")
        if not options["skip_party"]:
            actions.append("seed_party")
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
                if "seed_rates" in actions:
                    # Keep call compatible with existing migration/fixture name.
                    self._load_fixture_if_exists(fixture_paths["rates"])

                if "seed_party" in actions:
                    self._seed_party_defaults()

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
        # Movement types â€” required for stock/inventory posting rules
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

    def _seed_notify_v2_defaults(self):
        """Retain the flag without installing retired domain defaults."""
        self.stdout.write(
            self.style.SUCCESS(
                "Notify V2 uses workflow-owned configuration; no defaults seeded."
            )
        )
