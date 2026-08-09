import json
from dataclasses import asdict

from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import get_public_schema_name, schema_context, schema_exists

from apps.tenant_apps.accounting.diagnostics import accounting_integrity_findings


class Command(BaseCommand):
    help = "Run read-only standalone-accounting integrity diagnostics for one tenant."

    def add_arguments(self, parser):
        parser.add_argument("--schema", required=True)
        parser.add_argument("--json", action="store_true")

    def handle(self, *args, **options):
        schema = options["schema"].strip()
        if schema == get_public_schema_name() or not schema_exists(schema):
            raise CommandError("A valid non-public tenant schema is required.")
        with schema_context(schema):
            findings = accounting_integrity_findings()
        payload = [asdict(finding) for finding in findings]
        if options["json"]:
            self.stdout.write(json.dumps(payload, indent=2, sort_keys=True))
        elif findings:
            for finding in findings:
                self.stdout.write(f"{finding.code} [{finding.book_key}] {finding.message}")
        else:
            self.stdout.write(self.style.SUCCESS(f"Accounting integrity passed for {schema}."))
        if findings:
            raise CommandError(f"Accounting integrity failed with {len(findings)} finding(s).")
