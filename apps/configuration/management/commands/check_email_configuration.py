import json

from django.core.management.base import BaseCommand, CommandError

from apps.configuration.email_readiness import assess_email_configuration


class Command(BaseCommand):
    help = "Inspect effective email configuration without sending mail or exposing credentials."
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument("--format", choices=("text", "json"), default="text")
        parser.add_argument("--require-external-config", action="store_true")

    def handle(self, *args, **options):
        report = assess_email_configuration()
        if options["format"] == "json":
            self.stdout.write(json.dumps(report, sort_keys=True))
        else:
            self.stdout.write(f"Effective backend ({report['configuration_source']}): {report['backend']}")
            for blocker in report["blockers"]:
                self.stdout.write(f"BLOCKER: {blocker}")
            self.stdout.write("Delivery is unverified. This offline check does not send mail or inspect DNS/provider accounts.")
        if options["require_external_config"] and not report["configuration_valid_for_external_mail"]:
            raise CommandError("External email configuration is not ready.")
