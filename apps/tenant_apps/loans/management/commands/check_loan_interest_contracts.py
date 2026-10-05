import json
from django.core.management.base import BaseCommand
from apps.tenant_apps.loans.management.workspace import command_workspace
from apps.tenant_apps.loans.selectors.interest_contract_inventory import interest_contract_inventory


class Command(BaseCommand):
    help = "Read-only inventory of shared and legacy loan interest contracts for rollout review."

    def add_arguments(self, parser):
        parser.add_argument("--workspace-id", type=int, required=True)

    def handle(self, *args, **options):
        with command_workspace(options["workspace_id"], read_only=True):
            rows = interest_contract_inventory()
        for row in rows:
            self.stdout.write(json.dumps(row, sort_keys=True))
