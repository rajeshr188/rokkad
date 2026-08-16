from django.core.management.base import BaseCommand
from django.db import transaction
from apps.orgs.models import Company
from apps.tenancy.context import workspace_context
from apps.tenant_apps.party.services import seed_party_roles


class Command(BaseCommand):
    help = "Seed canonical PartyRoleType records in a tenant schema."

    def add_arguments(self, parser):
        parser.add_argument(
            "--workspace-id",
            type=int,
            required=True,
            help="Workspace id that owns the canonical Party roles.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be seeded without applying changes.",
        )

    def handle(self, *args, **options):
        workspace = Company.objects.get(pk=options["workspace_id"])

        if options["dry_run"]:
            self.stdout.write("Would seed canonical party roles.")
            return

        with workspace_context(workspace.id):
            result = self._seed(workspace)

        self.stdout.write(
            self.style.SUCCESS(
                "Party roles ready: "
                f"created={result['created']} updated={result['updated']} total={result['total']}"
            )
        )

    def _seed(self, workspace):
        with transaction.atomic():
            return seed_party_roles(workspace=workspace)
