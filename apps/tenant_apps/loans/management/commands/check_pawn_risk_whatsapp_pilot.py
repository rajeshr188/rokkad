import json

from django.core.management.base import BaseCommand, CommandError

from apps.tenant_apps.loans.services.risk_whatsapp_pilot import assess_risk_whatsapp_pilot


class Command(BaseCommand):
    help = "Reconcile manual PawnLoan risk WhatsApp notices with authenticated Meta callbacks."

    def add_arguments(self, parser):
        parser.add_argument("--format", choices=("text", "json"), default="text")
        parser.add_argument("--fail-on-blocker", action="store_true")

    def handle(self, *args, **options):
        report = assess_risk_whatsapp_pilot()
        payload = {
            "accepted": report.accepted,
            "provider_ready": report.readiness.ready,
            "submitted_count": report.submitted_count,
            "delivered_count": report.delivered_count,
            "read_count": report.read_count,
            "failed_count": report.failed_count,
            "unresolved_count": report.unresolved_count,
            "duplicate_count": report.duplicate_count,
            "unknown_receipt_count": len(report.unknown_receipts),
            "blockers": list(report.readiness.blockers),
        }
        if options["format"] == "json":
            self.stdout.write(json.dumps(payload, sort_keys=True))
        else:
            self.stdout.write(" ".join(f"{key}={str(value).lower() if isinstance(value, bool) else value}" for key, value in payload.items() if key != "blockers"))
            for blocker in payload["blockers"]:
                self.stdout.write(f"BLOCKER: {blocker}")
        if options["fail_on_blocker"] and not report.accepted:
            raise CommandError("PawnLoan risk WhatsApp pilot is not accepted.")
