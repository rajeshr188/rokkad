from django.core.management.base import BaseCommand, CommandError

from apps.tenant_apps.loans.documents.integrity import get_document_integrity_findings


class Command(BaseCommand):
    help = "Check configurable loan document layouts, assets, and issued artifacts in the active tenant schema."

    def add_arguments(self, parser):
        parser.add_argument("--fail-on-findings", action="store_true")

    def handle(self, *args, **options):
        findings = get_document_integrity_findings()
        for finding in findings:
            self.stdout.write(f"{finding.category}\t{finding.object_type}:{finding.object_id}\t{finding.message}")
        self.stdout.write(f"Loan document integrity findings: {len(findings)}")
        if findings and options["fail_on_findings"]:
            raise CommandError("Loan document integrity check failed.")
