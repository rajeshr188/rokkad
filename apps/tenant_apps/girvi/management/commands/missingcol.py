import csv
import os

from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import schema_context

from apps.tenant_apps.girvi.models.legacy import Loan


class Command(BaseCommand):
    help = (
        "LEGACY REPAIR (OPT-IN): import lid values from CSV into deprecated Loan rows "
        "for import/rehearsal use only."
    )

    def add_arguments(self, parser):
        parser.add_argument("csv_file", type=str, help="The path to the CSV file")
        parser.add_argument("schema", type=str, help="The schema to import into")

    def handle(self, *args, **kwargs):
        if os.environ.get("GIRVI_ENABLE_LEGACY_IMPORT_COMMANDS") != "1":
            raise CommandError(
                "Legacy command 'missingcol' is disabled by default. "
                "Set GIRVI_ENABLE_LEGACY_IMPORT_COMMANDS=1 only for controlled "
                "import/rehearsal operations."
            )

        csv_file = kwargs["csv_file"]
        schema = kwargs["schema"]
        processed = 0

        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                with schema_context(schema):
                    try:
                        obj = Loan.objects.get(
                            id=row["id"]
                        )  # replace 'id' with your unique field
                        # print(f"id: {row['id']}, lid: {row['lid']} ,loan_id:{obj.loan_id}")
                        obj.lid = row[
                            "lid"
                        ]  # replace 'missing_column' with your column name
                        obj.save()
                        processed += 1
                    except Loan.DoesNotExist:
                        self.stdout.write(
                            self.style.ERROR(
                                f"Record with id={row['id']} does not exist."
                            )
                        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Legacy lid import completed for schema '{schema}' (updated {processed} rows)."
            )
        )
