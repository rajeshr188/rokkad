from django.core.management.base import BaseCommand, CommandError

from apps.tenant_apps.loans.services.product_catalog import (
    LoanProductCatalogError,
    _seed_default_loan_products,
)


class Command(BaseCommand):
    help = "Idempotently seed the four draft loan products in the active tenant schema."

    def handle(self, *args, **options):
        try:
            versions = _seed_default_loan_products()
        except LoanProductCatalogError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"Ready product versions: {len(versions)}"))
