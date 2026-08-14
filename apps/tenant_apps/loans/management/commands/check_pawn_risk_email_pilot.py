import json

from django.core.management.base import BaseCommand, CommandError

from apps.tenant_apps.loans.services.risk_email_pilot import assess_risk_email_pilot


class Command(BaseCommand):
    help = "Check real-provider readiness and evidence reconciliation for PawnLoan risk email."

    def add_arguments(self, parser):
        parser.add_argument("--format", choices=("text", "json"), default="text")
        parser.add_argument("--fail-on-blocker", action="store_true")

    def handle(self, *args, **options):
        report = assess_risk_email_pilot()
        payload = {
            "ready": report.ready,
            "provider_ready": report.provider.ready,
            "backend": report.provider.backend,
            "sender": report.provider.sender,
            "notice_count": report.notice_count,
            "sent_count": report.sent_count,
            "failed_count": report.failed_count,
            "pending_count": report.pending_count,
            "evidence_issues": list(report.evidence_issues),
        }
        if options["format"] == "json":
            self.stdout.write(json.dumps(payload, sort_keys=True))
        else:
            self.stdout.write(
                f"ready={str(report.ready).lower()} provider_ready={str(report.provider.ready).lower()} "
                f"notices={report.notice_count} sent={report.sent_count} failed={report.failed_count} "
                f"pending={report.pending_count} evidence_issues={len(report.evidence_issues)}"
            )
            self.stdout.write(report.provider.message)
            for issue in report.evidence_issues:
                self.stdout.write(f"BLOCKER: {issue}")
        if options["fail_on_blocker"] and not report.ready:
            raise CommandError("PawnLoan risk email pilot is not ready.")
