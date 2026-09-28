import json

from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_datetime
from django.utils.timezone import is_aware

from apps.platform_mail.operations import queue_health


class Command(BaseCommand):
    help = "Read-only private queue health; prints counts, IDs and codes, never recipients."

    def add_arguments(self, parser):
        parser.add_argument("--since", help="Aware ISO timestamp of the last reviewed terminal events.")
        parser.add_argument("--require-healthy", action="store_true")

    def handle(self, *args, **options):
        since = None
        if options["since"]:
            try:
                since = parse_datetime(options["since"])
            except ValueError:
                since = None
            if not since or not is_aware(since):
                raise CommandError("--since requires an ISO timestamp with timezone.")
        report = queue_health(since=since)
        self.stdout.write(json.dumps(report, sort_keys=True))
        if options["require_healthy"] and report["flags"]:
            raise CommandError("Platform mail requires operator review.")
