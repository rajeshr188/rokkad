"""Produce a consistent, read-only legacy role inventory on stdout."""
import json

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from apps.orgs.services.role_preflight import build_role_preflight


class Command(BaseCommand):
    help = "Read-only JSON inventory of roles, grants and migration risks (AP-06)."

    def handle(self, *args, **options):
        if connection.vendor != "postgresql" or connection.in_atomic_block:
            raise CommandError("Run preflight on PostgreSQL outside an existing transaction.")
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            report = build_role_preflight()
        self.stdout.write(json.dumps(report, indent=2, sort_keys=True))
