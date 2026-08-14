import json

from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import get_public_schema_name, schema_context, schema_exists

from apps.tenant_apps.accounting.evidence import accountant_evidence_pack
from apps.tenant_apps.accounting.models import AccountingBook


class Command(BaseCommand):
    help = "Render a read-only accountant evidence pack for one tenant book."

    def add_arguments(self, parser):
        parser.add_argument("--schema", required=True)
        parser.add_argument("--book", required=True)

    def handle(self, *args, **options):
        schema = options["schema"].strip()
        if schema == get_public_schema_name() or not schema_exists(schema):
            raise CommandError("A valid non-public tenant schema is required.")
        with schema_context(schema):
            try:
                book = AccountingBook.objects.get(book_key=options["book"])
            except AccountingBook.DoesNotExist as exc:
                raise CommandError("Accounting book was not found.") from exc
            payload = accountant_evidence_pack(book=book)
        self.stdout.write(json.dumps(payload, indent=2, sort_keys=True))
