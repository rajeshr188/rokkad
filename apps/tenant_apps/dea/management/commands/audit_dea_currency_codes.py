from dataclasses import dataclass

from django.core.management.base import BaseCommand
from django.db import connection
from django.db.models import Count
from django_tenants.utils import schema_context

from apps.tenant_apps.dea.models import (
    AccountStatement,
    AccountTransaction,
    LedgerStatement,
    LedgerTransaction,
)


METAL_LIKE_CODES = {
    "AG",
    "AU",
    "GLD",
    "SLV",
    "XAG",
    "XAU",
}


@dataclass(frozen=True)
class CurrencySource:
    label: str
    model: object
    field_name: str


SOURCES = [
    CurrencySource(
        "LedgerTransaction.amount_currency",
        LedgerTransaction,
        "amount_currency",
    ),
    CurrencySource(
        "LedgerTransaction.amount_base_currency",
        LedgerTransaction,
        "amount_base_currency",
    ),
    CurrencySource(
        "AccountTransaction.amount_currency",
        AccountTransaction,
        "amount_currency",
    ),
    CurrencySource(
        "LedgerStatement.ClosingBalance_currency",
        LedgerStatement,
        "ClosingBalance_currency",
    ),
    CurrencySource(
        "AccountStatement.ClosingBalance_currency",
        AccountStatement,
        "ClosingBalance_currency",
    ),
    CurrencySource(
        "AccountStatement.TotalCredit_currency",
        AccountStatement,
        "TotalCredit_currency",
    ),
    CurrencySource(
        "AccountStatement.TotalDebit_currency",
        AccountStatement,
        "TotalDebit_currency",
    ),
]


class Command(BaseCommand):
    help = (
        "Read-only DEA currency-code audit. Reports distinct currency codes from "
        "financial transaction and statement columns and flags metal-like codes."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema",
            type=str,
            help="Tenant schema to inspect. If omitted, inspects the current schema.",
        )

    def handle(self, *args, **options):
        schema = options.get("schema")
        if schema:
            with schema_context(schema):
                return self._audit_schema(schema)
        return self._audit_schema(connection.schema_name)

    def _audit_schema(self, schema_name):
        self.stdout.write(f"DEA currency-code audit for schema: {schema_name}")
        suspicious_total = 0

        for source in SOURCES:
            rows = self._distinct_codes(source)
            if not rows:
                self.stdout.write(f"- {source.label}: no values")
                continue

            display_values = []
            for code, count in rows:
                flag = " SUSPICIOUS" if code in METAL_LIKE_CODES else ""
                suspicious_total += int(bool(flag))
                display_values.append(f"{code}({count}){flag}")
            self.stdout.write(f"- {source.label}: {', '.join(display_values)}")

        if suspicious_total:
            self.stdout.write(
                self.style.WARNING(
                    f"Suspicious metal-like currency code occurrences: {suspicious_total}"
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS("No suspicious metal-like currency codes found."))

    def _distinct_codes(self, source):
        return list(
            source.model.objects.exclude(**{source.field_name: ""})
            .values(source.field_name)
            .annotate(count=Count("pk"))
            .order_by(source.field_name)
            .values_list(source.field_name, "count")
        )
