from django.core.management.base import BaseCommand, CommandError

from apps.tenant_apps.data_portability.opening_review import read_documents, write_review
from apps.tenant_apps.data_portability.parsers import PortabilityError


class Command(BaseCommand):
    help = "Reconcile offline opening review JSONL; no database access or financial commit."
    requires_system_checks = []
    requires_migrations_checks = False

    def add_arguments(self, parser):
        parser.add_argument("--input", required=True)
        parser.add_argument("--output-dir", required=True)

    def handle(self, *args, **options):
        try:
            summary = write_review(options["output_dir"], read_documents(options["input"]))
        except PortabilityError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(f"Opening review complete: {summary['loans']} loans; "
                          f"{summary['document_reconciled']} documents reconciled. Nothing imported. "
                          "See opening-review.html and opening-results.jsonl in the output directory.")
