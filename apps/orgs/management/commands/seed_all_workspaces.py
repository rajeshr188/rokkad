from django.core.management import call_command
from django.core.management.base import BaseCommand
from apps.orgs.models import Company


class Command(BaseCommand):
    help = "Seed defaults for all active Workspaces."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print target Workspaces without applying seeds.",
        )
        parser.add_argument(
            "--continue-on-error",
            action="store_true",
            help="Continue seeding remaining Workspaces if one fails.",
        )
        parser.add_argument(
            "--skip-rates",
            action="store_true",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        continue_on_error = options["continue_on_error"]

        workspace_ids = list(
            Company.objects.values_list("pk", flat=True)
        )

        self.stdout.write(self.style.NOTICE(f"Found {len(workspace_ids)} Workspaces"))

        if dry_run:
            for workspace_id in workspace_ids:
                self.stdout.write(f"Would seed Workspace: {workspace_id}")
            return

        seeded = 0
        failed = []

        for workspace_id in workspace_ids:
            self.stdout.write(f"Seeding Workspace: {workspace_id}")
            try:
                call_command(
                    "seed_workspace_defaults",
                    workspace_id=workspace_id,
                    skip_rates=options["skip_rates"],
                )
                seeded += 1
            except Exception as exc:  # noqa: BLE001
                failed.append((workspace_id, str(exc)))
                self.stderr.write(self.style.ERROR(f"Failed: {workspace_id} -> {exc}"))
                if not continue_on_error:
                    break

        self.stdout.write(self.style.SUCCESS(f"Seeded Workspaces: {seeded}"))
        if failed:
            self.stderr.write(self.style.ERROR(f"Failed Workspaces: {len(failed)}"))
            for workspace_id, error in failed:
                self.stderr.write(f"- {workspace_id}: {error}")
