import json
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError
from apps.subscriptions.readiness import assess_billing_configuration, billing_evidence_inventory


class Command(BaseCommand):
    help = "Check billing settings and optional read-only evidence counts; never contacts Razorpay or sends mail."
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument("--include-evidence", action="store_true")
        parser.add_argument("--require-configured", action="store_true")

    def handle(self, *args, **options):
        report = assess_billing_configuration()
        if options["include_evidence"]:
            try:
                report["evidence"] = billing_evidence_inventory()
            except DatabaseError:
                report["evidence"] = {"blockers": ["Billing evidence is unavailable; check database access and migrations."]}
        self.stdout.write(json.dumps(report, sort_keys=True))
        if options["require_configured"] and (not report["configuration_ready"] or report.get("evidence", {}).get("blockers")):
            raise CommandError("Billing configuration or evidence needs review. This check never certifies launch readiness.")
