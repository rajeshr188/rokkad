"""Read-only owner preflight for migration 0072; never repair or reassign evidence."""
import json
from importlib import import_module

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction


class Command(BaseCommand):
    help = "Check retained risk-reference integrity using owner-only migration settings."
    requires_system_checks = []

    def handle(self, *args, **options):
        upgrade = import_module("apps.tenant_apps.loans.migrations.0072_risk_evidence_guards")
        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                report = upgrade.read_preflight(connection)
        except RuntimeError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(report, sort_keys=True))
        if any(report["violations"].values()):
            raise CommandError("Risk references need explicit review; no evidence was changed.")
        self.stdout.write("Risk reference preflight passed; retained evidence is unchanged.")
