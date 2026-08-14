from django.core.management.base import BaseCommand, CommandError

from apps.tenant_apps.girvi.models import GirviNumberSequence, Series
from apps.tenant_apps.girvi.service_modules.id_generation import (
    GirviNumberSequenceService,
)


class Command(BaseCommand):
    help = (
        "Dry-run or apply GirviNumberSequence rows for the current tenant schema "
        "from existing Girvi document IDs."
    )

    def add_arguments(self, parser):
        mode = parser.add_mutually_exclusive_group(required=True)
        mode.add_argument(
            "--dry-run",
            action="store_true",
            help="Report required sequence rows without writing changes.",
        )
        mode.add_argument(
            "--apply",
            action="store_true",
            help="Create/update sequence rows for the current tenant schema.",
        )
        parser.add_argument(
            "--series-id",
            type=int,
            help="Restrict sync to a single Series primary key.",
        )

    def handle(self, *args, **options):
        apply = bool(options["apply"])
        series_qs = Series.objects.order_by("pk")
        if options.get("series_id"):
            series_qs = series_qs.filter(pk=options["series_id"])
            if not series_qs.exists():
                raise CommandError(f"Series {options['series_id']} was not found.")

        document_kinds = [
            GirviNumberSequence.DocumentKind.GIVEN_LOAN,
            GirviNumberSequence.DocumentKind.TAKEN_LOAN,
            GirviNumberSequence.DocumentKind.GIVEN_LOAN_RELEASE,
            GirviNumberSequence.DocumentKind.TAKEN_LOAN_SETTLEMENT,
        ]

        summaries = []
        for series in series_qs:
            for document_kind in document_kinds:
                summaries.append(
                    GirviNumberSequenceService.sync_from_existing(
                        series,
                        document_kind,
                        apply=apply,
                    )
                )

        mode = "APPLY" if apply else "DRY-RUN"
        self.stdout.write(f"{mode}: inspected {len(summaries)} Girvi sequence row(s).")
        for summary in summaries:
            action = "created" if summary["created"] else "updated"
            if not apply:
                action = "would-create" if summary["created"] else "would-update"
            self.stdout.write(
                "series={series_id} kind={document_kind} action={action} "
                "prefix={prefix} width={width} highest={highest_existing_number} "
                "next={target_next_number}".format(action=action, **summary)
            )
