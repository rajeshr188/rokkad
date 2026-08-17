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
        parser.add_argument("--workspace-id", type=int, required=True)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--skip-rates", action="store_true")
        parser.add_argument("--skip-party", action="store_true")
        parser.add_argument("--skip-notify-v2", action="store_true")

    def handle(self, *args, **options):
        workspace_id = options["workspace_id"]
        try:
            workspace = Company.all_objects.get(pk=workspace_id)
        except Company.DoesNotExist as exc:
            raise CommandError(f"Workspace {workspace_id} does not exist.") from exc

        actions = []
        if not options["skip_rates"]:
            actions.append("seed_rates")
        if not options["skip_party"]:
            actions.append("seed_party")
        if not options["skip_notify_v2"]:
            actions.append("seed_notify_v2")

        self.stdout.write(
            self.style.NOTICE(
                f"Workspace seed start: workspace={workspace_id}, "
                f"actions={', '.join(actions) or 'none'}"
            )
        )
        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry run mode. No changes applied."))
            return

        with workspace_context(workspace_id), transaction.atomic():
            if "seed_rates" in actions:
                self._load_fixture_if_exists(
                    Path("apps/tenant_apps/rates/fixtures/metal_rates.json")
                )
            if "seed_party" in actions:
                self._seed_party_defaults(workspace)
            if "seed_notify_v2" in actions:
                self._seed_notify_v2_defaults()

        self.stdout.write(
            self.style.SUCCESS(
                f"Workspace seed completed for workspace={workspace_id}"
            )
        )

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
                f"created={result['created']} updated={result['updated']} "
                f"total={result['total']}"
            )
        )

    def _seed_notify_v2_defaults(self):
        self.stdout.write(
            self.style.SUCCESS(
                "Notify v2 uses workflow-owned configuration; no defaults seeded."
            )
        )
