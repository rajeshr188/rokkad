from calendar import monthrange
from datetime import date, datetime
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django_tenants.utils import tenant_context

from apps.orgs.models import Company
from apps.tenant_apps.girvi.models import GivenLoan, LoanLifecycleState
from apps.tenant_apps.girvi.service_modules.accrual import (
    AccrualTriggerSource,
    InterestAccrualCommand,
    InterestAccrualService,
)
from apps.tenant_apps.girvi.service_modules.preferences import (
    get_loan_accrual_timing,
    is_loan_auto_post_accruals_enabled,
    is_loan_backfill_posting_allowed,
)


class Command(BaseCommand):
    help = "Accrue completed-month interest for open GivenLoans across one or all tenants."

    def add_arguments(self, parser):
        parser.add_argument(
            "--as-of-date",
            dest="as_of_date",
            help="Accrue interest through this date (YYYY-MM-DD). Defaults to today.",
        )
        parser.add_argument(
            "--schema",
            dest="schema",
            help="Optional tenant schema to process instead of all tenants.",
        )
        parser.add_argument(
            "--loan-id",
            dest="loan_id",
            type=int,
            help="Optional GivenLoan primary key to process within the selected tenant(s).",
        )
        parser.add_argument(
            "--trigger-source",
            dest="trigger_source",
            default=AccrualTriggerSource.SCHEDULED,
            choices=AccrualTriggerSource.values,
            help="Audit label recorded on created accrual rows.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview due accrual periods without creating rows or DEA postings.",
        )
        parser.add_argument(
            "--skip-accounting",
            action="store_true",
            help="Create accrual rows only; do not post DEA journal entries.",
        )
        parser.add_argument(
            "--backfill",
            action="store_true",
            help=(
                "Run in explicit backfill mode for currently open loans. "
                "This records the trigger source as BACKFILL and adds backfill notes."
            ),
        )
        parser.add_argument(
            "--respect-timing",
            action="store_true",
            help=(
                "When trigger source is SCHEDULED, respect the company's "
                "`Loan__Accrual_Timing` preference and skip tenants outside their run window."
            ),
        )

    def _parse_as_of_date(self, raw_value):
        if not raw_value:
            return timezone.localdate()

        try:
            return date.fromisoformat(str(raw_value))
        except ValueError:
            try:
                return datetime.fromisoformat(str(raw_value)).date()
            except ValueError as exc:
                raise CommandError(
                    f"Invalid --as-of-date value '{raw_value}'. Use YYYY-MM-DD format."
                ) from exc

    def _tenant_queryset(self, schema_name=None):
        tenants = Company.objects.exclude(schema_name="public")
        if schema_name:
            tenants = tenants.filter(schema_name=schema_name)
        return tenants.order_by("schema_name")

    def _loan_queryset(self, loan_id=None):
        closed_statuses = {
            LoanLifecycleState.CLOSED,
            LoanLifecycleState.RENEWED,
            LoanLifecycleState.CANCELLED,
            LoanLifecycleState.REJECTED,
        }
        qs = GivenLoan.objects.filter(release__isnull=True).exclude(status__in=closed_statuses)
        if loan_id:
            qs = qs.filter(pk=loan_id)
        return qs.order_by("loan_date", "pk")

    def _scheduled_run_due(self, tenant, as_of_date):
        timing = get_loan_accrual_timing(tenant).upper()
        if timing == "BOM":
            return as_of_date.day == 1, timing

        last_day = monthrange(as_of_date.year, as_of_date.month)[1]
        return as_of_date.day == last_day, timing

    def handle(self, *args, **options):
        as_of_date = self._parse_as_of_date(options.get("as_of_date"))
        if as_of_date > timezone.localdate():
            raise CommandError(
                "Interest accrual runs cannot use a future --as-of-date."
            )

        schema_name = options.get("schema")
        loan_id = options.get("loan_id")
        backfill = bool(options.get("backfill"))
        respect_timing = bool(options.get("respect_timing"))
        trigger_source = options.get("trigger_source") or AccrualTriggerSource.SCHEDULED
        if backfill:
            trigger_source = AccrualTriggerSource.BACKFILL
        dry_run = bool(options.get("dry_run"))
        post_to_accounting = not bool(options.get("skip_accounting")) and not dry_run

        tenants = list(self._tenant_queryset(schema_name=schema_name))
        if not tenants:
            raise CommandError(
                f"No tenant workspaces found for schema filter '{schema_name or '*'}'."
            )

        summary = {
            "tenants_processed": 0,
            "loans_considered": 0,
            "loans_with_new_accruals": 0,
            "periods_created": 0,
            "total_amount": Decimal("0.00"),
            "errors": 0,
            "timing_skips": 0,
        }

        if backfill:
            mode_label = "backfill preview" if dry_run else "backfill execution"
        else:
            mode_label = "preview" if dry_run else "execution"
        self.stdout.write(
            f"Starting loan interest accrual {mode_label} for {len(tenants)} tenant(s) as of {as_of_date}."
        )

        for tenant in tenants:
            self.stdout.write(f"\n[{tenant.schema_name}] Processing loan interest accruals...")
            summary["tenants_processed"] += 1

            if (
                respect_timing
                and not backfill
                and trigger_source == AccrualTriggerSource.SCHEDULED
            ):
                should_run, timing = self._scheduled_run_due(tenant, as_of_date)
                if not should_run:
                    summary["timing_skips"] += 1
                    self.stdout.write(
                        f"  Skipped due to Loan__Accrual_Timing={timing} for {as_of_date}."
                    )
                    continue

            with tenant_context(tenant):
                loans = list(self._loan_queryset(loan_id=loan_id))
                summary["loans_considered"] += len(loans)

                if not loans:
                    self.stdout.write("  No eligible open loans found.")
                    continue

                for loan in loans:
                    effective_post_to_accounting = post_to_accounting
                    if effective_post_to_accounting:
                        effective_post_to_accounting = is_loan_auto_post_accruals_enabled(
                            tenant
                        )
                        if backfill and effective_post_to_accounting:
                            effective_post_to_accounting = (
                                is_loan_backfill_posting_allowed(tenant)
                            )

                    run_notes = (
                        f"Backfill accrual run through {as_of_date} ({trigger_source})"
                        if backfill
                        else f"Batch accrual run on {as_of_date} ({trigger_source})"
                    )
                    command = InterestAccrualCommand(
                        loan=loan,
                        as_of_date=as_of_date,
                        trigger_source=trigger_source,
                        created_by=getattr(loan, "created_by", None),
                        notes=run_notes,
                        post_to_accounting=effective_post_to_accounting,
                    )

                    if dry_run:
                        preview = InterestAccrualService.preview(command)
                        if not preview.is_valid:
                            summary["errors"] += 1
                            self.stdout.write(
                                self.style.WARNING(
                                    f"  {loan.loan_id}: skipped - {'; '.join(preview.errors)}"
                                )
                            )
                            continue
                        if preview.pending_periods == 0:
                            self.stdout.write(f"  {loan.loan_id}: no new accrual periods due.")
                            continue

                        summary["loans_with_new_accruals"] += 1
                        summary["periods_created"] += preview.pending_periods
                        summary["total_amount"] += preview.newly_accrued_amount
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"  {loan.loan_id}: would create {preview.pending_periods} period(s) "
                                f"for INR {preview.newly_accrued_amount}"
                            )
                        )
                        continue

                    result = InterestAccrualService.execute(command)
                    if not result.success:
                        summary["errors"] += 1
                        self.stdout.write(
                            self.style.WARNING(
                                f"  {loan.loan_id}: accrual failed - {result.message}"
                            )
                        )
                        continue

                    if result.created_count == 0:
                        self.stdout.write(f"  {loan.loan_id}: no new accrual periods due.")
                        continue

                    summary["loans_with_new_accruals"] += 1
                    summary["periods_created"] += result.created_count
                    summary["total_amount"] += result.total_created_amount
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  {loan.loan_id}: created {result.created_count} period(s) "
                            f"for INR {result.total_created_amount}"
                        )
                    )

        self.stdout.write(
            self.style.SUCCESS(
                "\nInterest accrual summary: "
                f"tenants={summary['tenants_processed']}, "
                f"loans_scanned={summary['loans_considered']}, "
                f"loans_accrued={summary['loans_with_new_accruals']}, "
                f"periods={summary['periods_created']}, "
                f"amount=INR {summary['total_amount']}, "
                f"errors={summary['errors']}"
            )
        )
        return summary
