import csv

from django.core.management.base import BaseCommand
from django.db import transaction
from django_tenants.utils import schema_context

from apps.tenant_apps.girvi.models import Loan


class Command(BaseCommand):
    help = "Import a specific column from a CSV file into a specific schema"

    def add_arguments(self, parser):
        parser.add_argument("csv_file", type=str, help="The path to the CSV file")
        parser.add_argument("schema", type=str, help="The schema to import into")

    def handle(self, *args, **kwargs):
        csv_file = kwargs["csv_file"]
        schema = kwargs["schema"]

        with open(csv_file, "r") as f:
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
                    except Loan.DoesNotExist:
                        self.stdout.write(
                            self.style.ERROR(
                                f"Record with id={row['id']} does not exist."
                            )
                        )
