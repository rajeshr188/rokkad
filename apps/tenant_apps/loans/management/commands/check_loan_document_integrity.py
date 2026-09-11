from django.core.management.base import BaseCommand, CommandError

from apps.tenant_apps.loans.documents.integrity import get_document_integrity_findings
from apps.tenant_apps.loans.management.workspace import command_workspace


class Command(BaseCommand):
    help = "Read-only document integrity check for one explicit Workspace, including archived Workspaces."

    def add_arguments(self, parser):
        parser.add_argument("--workspace-id", type=int, required=True)
        parser.add_argument("--fail-on-findings", action="store_true")

    def handle(self, *args, **options):
        with command_workspace(options["workspace_id"], read_only=True):
            findings = get_document_integrity_findings()
        for finding in findings:
            self.stdout.write(f"{finding.category}\t{finding.object_type}:{finding.object_id}\t{finding.message}")
        self.stdout.write(f"Workspace {options['workspace_id']} loan document integrity findings: {len(findings)}")
        if findings and options["fail_on_findings"]:
            raise CommandError("Loan document integrity check failed.")
