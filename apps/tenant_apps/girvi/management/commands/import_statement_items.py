# FILE: girvi/management/commands/import_statement_items.py

import re

from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from django.db import IntegrityError
from django.utils import timezone
from django_tenants.utils import schema_context

from apps.orgs.models import Company
from apps.tenant_apps.girvi.models import (
    Loan,  # Adjust the import as needed
    Statement,
    StatementItem,
)


class Command(BaseCommand):
    help = "Import statement items from an HTML file for a specific tenant"

    def add_arguments(self, parser):
        parser.add_argument("tenant", type=str, help="The schema name of the tenant")
        parser.add_argument("html_file", type=str, help="The path to the HTML file")

    def handle(self, *args, **kwargs):
        tenant = kwargs["tenant"]
        html_file = kwargs["html_file"]

        # Read the HTML content from the file
        with open(html_file, "r", encoding="utf-8") as file:
            html_content = file.read()

        # Parse the HTML content using BeautifulSoup
        soup = BeautifulSoup(html_content, "html.parser")

        # Extract the text inside each <li> element
        li_elements = soup.find_all("li")
        li_texts = [li.get_text(strip=True) for li in li_elements]

        # Regular expression to extract the loan ID
        pattern = r"([A-Z]\d{5})"

        try:
            tenant = Company.objects.get(name=tenant)
        except Company.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"Tenant with name {tenant} does not exist.")
            )
            return

        with schema_context(tenant.name):
            # Create a new Statement instance
            statement = Statement.objects.create(
                created_by=None
            )  # Adjust created_by as needed

            # Iterate over the extracted texts and create StatementItem instances
            for text in li_texts:
                match = re.search(pattern, text)
                if match:
                    loan_id = match.group(1)
                    try:
                        loan = Loan.objects.get(loan_id=loan_id)
                        if not loan.is_released:
                            try:
                                StatementItem.objects.create(
                                    statement=statement,
                                    loan=loan,
                                    verified_at=timezone.now(),
                                    descrepancy_found=False,
                                    descrepancy_note="",
                                )
                            except IntegrityError:
                                self.stdout.write(
                                    self.style.ERROR(
                                        f"Duplicate entry for loan ID {loan_id} in statement {statement.id}."
                                    )
                                )
                        else:
                            try:
                                StatementItem.objects.create(
                                    statement=statement,
                                    loan=loan,
                                    descrepancy_found=True,
                                    descrepancy_note="Loan already released",
                                )
                            except IntegrityError:
                                self.stdout.write(
                                    self.style.ERROR(
                                        f"Duplicate entry for loan ID {loan_id} in statement {statement.id}."
                                    )
                                )
                    except Loan.DoesNotExist:
                        self.stdout.write(
                            self.style.ERROR(f"Loan with ID {loan_id} does not exist.")
                        )

            self.stdout.write(
                self.style.SUCCESS("Statement and StatementItems created successfully.")
            )
