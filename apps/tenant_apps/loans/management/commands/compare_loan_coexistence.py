import json
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from apps.tenant_apps.loans.selectors.comparison import (
    get_loan_coexistence_comparison,
)


class Command(BaseCommand):
    help = (
        "Read-only comparison of Girvi/Loans source projections against the "
        "unified coexistence contract. Run in a tenant schema."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--as-of",
            default=date.today().isoformat(),
            help="Comparison date in YYYY-MM-DD format (default: today).",
        )
        parser.add_argument(
            "--format",
            choices=("text", "json"),
            default="text",
            help="Output format (default: text).",
        )
        parser.add_argument(
            "--fail-on-mismatch",
            action="store_true",
            help="Return a non-zero exit when categorized mismatches exist.",
        )

    def handle(self, *args, **options):
        try:
            as_of_date = date.fromisoformat(options["as_of"])
        except ValueError as exc:
            raise CommandError("--as-of must use YYYY-MM-DD format.") from exc

        comparison = get_loan_coexistence_comparison(as_of_date=as_of_date)
        if options["format"] == "json":
            self.stdout.write(json.dumps(comparison.as_dict(), sort_keys=True))
        else:
            self._write_text(comparison)

        if comparison.mismatch_count and options["fail_on_mismatch"]:
            raise CommandError(
                f"Loan coexistence comparison found {comparison.mismatch_count} mismatch(es)."
            )

    def _write_text(self, comparison):
        self.stdout.write(f"Loan coexistence comparison as of {comparison.as_of_date}:")
        for summary in comparison.actual:
            self.stdout.write(
                "  "
                f"{summary.source_system}: rows={summary.row_count}, "
                f"active={summary.active_count}, closed={summary.closed_count}, "
                f"principal={summary.principal_outstanding}, "
                f"interest={summary.interest_outstanding}, due={summary.total_due}, "
                f"collateral={summary.collateral_count}, "
                f"release={dict(summary.release_counts)}, "
                f"dea={dict(summary.dea_visibility_counts)}"
            )
        if comparison.is_match:
            self.stdout.write(self.style.SUCCESS("Comparison passed: zero mismatches."))
            return
        self.stderr.write(
            self.style.WARNING(
                f"Comparison found {comparison.mismatch_count} mismatch(es):"
            )
        )
        for mismatch in comparison.mismatches:
            identity = f" [{mismatch.source_key}]" if mismatch.source_key else ""
            self.stderr.write(
                f"  {mismatch.category} {mismatch.source_system}{identity} "
                f"{mismatch.metric}: expected={mismatch.expected!r}, "
                f"actual={mismatch.actual!r}"
            )
