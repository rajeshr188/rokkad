import re

from django.core.management.base import BaseCommand
from django_tenants.utils import tenant_context

from apps.orgs.models import Company
from apps.tenant_apps.girvi.models import GivenLoan


class Command(BaseCommand):
    help = "Normalize GivenLoan loan_id values across all tenant schemas."

    def handle(self, *args, **kwargs):
        tenants = Company.objects.exclude(schema_name="public")

        for tenant in tenants:
            self.stdout.write(f"Updating loans for tenant: {tenant.schema_name}")
            with tenant_context(tenant):
                loans = GivenLoan.objects.all()
                for loan in loans:
                    match = re.match(r"^([A-Z]*)(\d+)$", loan.loan_id)
                    if match:
                        series = match.group(1)
                        number = int(match.group(2))
                        new_loan_id = f"{series}{number:05d}"
                        loan.loan_id = new_loan_id
                        loan.save()
                    else:
                        self.stdout.write(
                            self.style.WARNING(
                                f"Invalid loan_id format for Loan {loan.id}: {loan.loan_id}"
                            )
                        )
                self.stdout.write(
                    f"Finished updating {loans.count()} loans for tenant: {tenant.schema_name}"
                )
