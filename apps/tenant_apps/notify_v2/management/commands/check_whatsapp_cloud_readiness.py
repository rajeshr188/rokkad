import json

from django.core.management.base import BaseCommand, CommandError

from apps.tenant_apps.notify_v2.services.whatsapp_readiness import assess_whatsapp_cloud_readiness


class Command(BaseCommand):
    help = "Check tenant-scoped WhatsApp Cloud configuration and callback reconciliation."

    def add_arguments(self, parser):
        parser.add_argument("--format", choices=("text", "json"), default="text")
        parser.add_argument("--fail-on-blocker", action="store_true")

    def handle(self, *args, **options):
        report = assess_whatsapp_cloud_readiness()
        payload = {
            "ready": report.ready,
            "receipt_count": report.receipt_count,
            "unknown_receipt_count": report.unknown_receipt_count,
            "unreconciled_job_count": report.unreconciled_job_count,
            "blockers": list(report.blockers),
        }
        if options["format"] == "json":
            self.stdout.write(json.dumps(payload, sort_keys=True))
        else:
            self.stdout.write(
                f"ready={str(report.ready).lower()} receipts={report.receipt_count} "
                f"unknown={report.unknown_receipt_count} unreconciled={report.unreconciled_job_count}"
            )
            for blocker in report.blockers:
                self.stdout.write(f"BLOCKER: {blocker}")
        if options["fail_on_blocker"] and not report.ready:
            raise CommandError("WhatsApp Cloud is not ready.")
