# your_app_name/management/commands/update_loans.py
import re

from django.core.management.base import BaseCommand
from django_tenants.utils import tenant_context

from apps.orgs.models import Company
from apps.tenant_apps.girvi.models import \
    Loan  # Replace 'your_app_name' with the actual app name


class Command(BaseCommand):
    help = "Update loan instances across all tenants"

    def handle(self, *args, **kwargs):
        # Get all tenants
        tenants = Company.objects.exclude(schema_name="public")

        for tenant in tenants:
            self.stdout.write(f"Updating loans for tenant: {tenant.schema_name}")
            # Switch to the tenant's schema
            with tenant_context(tenant):
                # Update each loan instance
                loans = Loan.objects.all()
                for loan in loans:
                    match = re.match(r"^([A-Z]*)(\d+)$", loan.loan_id)
                    if match:
                        series = match.group(1)
                        number = int(match.group(2))
                        # Update loan_id with zero padding
                        new_loan_id = f"{series}{number:05d}"  # Adjust the padding length as needed
                        loan.loan_id = new_loan_id
                        loan.save()
                        # self.stdout.write(
                        #     self.style.SUCCESS(
                        #         f"Updated loan_id for Loan {loan.id}: {new_loan_id}"
                        #     )
                        # )
                    else:
                        self.stdout.write(
                            self.style.WARNING(
                                f"Invalid loan_id format for Loan {loan.id}: {loan.loan_id}"
                            )
                        )
                # for loan in loans:
                #     loan.update()
                # self.stdout.write(f'Updated loan ID: {loan.id}')
                self.stdout.write(
                    f"Finished updating {loans.count()} loans for tenant: {tenant.schema_name}"
                )
