from django.core.management.base import BaseCommand, CommandError
from apps.tenant_apps.loans.management.workspace import command_workspace

from apps.tenant_apps.loans.services.product_catalog import (
    LoanProductCatalogError,
    _seed_default_loan_products,
)


class Command(BaseCommand):
    help = "Idempotently seed four draft loan products in one explicit active Workspace."

    def add_arguments(self, parser):
        parser.add_argument("--workspace-id", type=int, required=True)

    def handle(self, *args, **options):
        try:
            with command_workspace(options["workspace_id"]):
                versions = _seed_default_loan_products()
        except LoanProductCatalogError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"Workspace {options['workspace_id']} ready product versions: {len(versions)}"))
