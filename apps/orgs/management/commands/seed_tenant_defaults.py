from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.orgs.models import Company
from apps.tenancy.context import workspace_context
from apps.tenant_apps.party.services import seed_party_roles


class Command(BaseCommand):
    help = "Seed Workspace-owned defaults for one Workspace."

    def add_arguments(self, parser):
        parser.add_argument(
            "--workspace-id",
            type=int,
            required=True,
            help="Workspace primary key to seed.",
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
        workspace_id = options["workspace_id"]
        dry_run = options["dry_run"]
        try:
            workspace = Company.all_objects.get(pk=workspace_id)
        except Company.DoesNotExist as exc:
            raise CommandError(f"Workspace {workspace_id} does not exist.") from exc

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
                f"Workspace seed start: workspace={workspace_id}, actions={', '.join(actions) or 'none'}"
            )
        )

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run mode. No changes applied."))
            return

        with workspace_context(workspace_id):
            with transaction.atomic():
                if "seed_rates" in actions:
                    # Keep call compatible with existing migration/fixture name.
                    self._load_fixture_if_exists(fixture_paths["rates"])

                if "seed_party" in actions:
                    self._seed_party_defaults(workspace)

                if "seed_notify_v2" in actions:
                    self._seed_notify_v2_defaults()

        self.stdout.write(self.style.SUCCESS(f"Workspace seed completed for workspace={workspace_id}"))

    def _load_fixture_if_exists(self, fixture_path):
        if not fixture_path.exists():
            self.stdout.write(
                self.style.WARNING(f"Fixture not found, skipped: {fixture_path}")
            )
            return

        self.stdout.write(f"Loading fixture: {fixture_path}")
        call_command("loaddata", str(fixture_path), verbosity=0)

    def _seed_party_defaults(self, workspace):
        result = seed_party_roles(workspace=workspace)
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
