import json
from django.core.management.base import BaseCommand, CommandError
from apps.platform_mail.readiness import assess_platform_mail


class Command(BaseCommand):
    help = "Inspect dedicated SES settings without sending, networking or exposing secrets."
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument("--require-ready", action="store_true")

    def handle(self, *args, **options):
        report = assess_platform_mail()
        self.stdout.write(json.dumps(report, sort_keys=True))
        if options["require_ready"] and not report["configuration_ready"]:
            raise CommandError("Dedicated platform mail configuration is not ready.")
