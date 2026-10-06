import json
from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection, transaction
from django.utils import timezone

from apps.tenant_apps.loans.management.workspace import command_workspace
from apps.tenant_apps.loans.selectors.release_inventory import loan_release_inventory


class Command(BaseCommand):
    help = "Read-only Workspace release inventory; neither financial adoption nor staff acceptance."

    def add_arguments(self, parser):
        parser.add_argument("--workspace-id", required=True, type=int)
        parser.add_argument("--as-of", type=date.fromisoformat)
        parser.add_argument("--summary-only", action="store_true")

    def handle(self, *args, **options):
        if connection.vendor != "postgresql" or connection.in_atomic_block:
            raise CommandError("Run this operator command on PostgreSQL outside an existing transaction.")
        on = options["as_of"] or timezone.localdate()
        if on > timezone.localdate():
            raise CommandError("The reporting date cannot be in the future.")
        # A consistent physical read-only snapshot, including the Workspace lookup.
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            with command_workspace(options["workspace_id"], read_only=True):
                report = loan_release_inventory(as_of_date=on, summary_only=options["summary_only"])
        self.stdout.write(json.dumps(report, cls=DjangoJSONEncoder, sort_keys=True))
