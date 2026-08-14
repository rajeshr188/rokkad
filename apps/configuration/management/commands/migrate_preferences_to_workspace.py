from django.core.management.base import BaseCommand, CommandError

from apps.configuration.services import PreferenceService
from apps.orgs.models import CompanyPreferenceModel
from apps.orgs.registries import company_preference_registry


LEGACY_GIRVI_KEY_MAP = {
    "Loan__Default_Date": "loan__default_date",
    "Loan__Interest_Deduction": "loan__interest_deduction_enabled",
    "Loan__Haircut": "loan__collateral_haircut_percent",
    "Loan__Accrual_Timing": "loan__accrual_timing",
    "Loan__Auto_Post_Accruals": "loan__auto_post_accruals",
    "Loan__Catchup_On_Receipt": "loan__catchup_on_receipt",
    "Loan__Catchup_On_Release": "loan__catchup_on_release",
    "Loan__Release_Fail_Closed_On_Accrual_Error": (
        "loan__release_fail_closed_on_accrual_error"
    ),
    "Loan__Catchup_On_Renewal": "loan__catchup_on_renewal",
    "Loan__Allow_Backfill_Posting": "loan__allow_backfill_posting",
    "Loan__Disbursal_Deductions_Enabled": "loan__disbursal_deductions_enabled",
    "Loan__Minimum_Document_Charge": "loan__minimum_document_charge",
    "Interest_Rate__gold": "loan__default_gold_interest_rate",
    "Interest_Rate__silver": "loan__default_silver_interest_rate",
    "Interest_Rate__other": "loan__default_other_interest_rate",
}


class Command(BaseCommand):
    help = (
        "Inventory legacy workspace preference rows before migrating them to the "
        "central configuration registry."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview legacy preference rows without writing central preferences.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Write explicitly mapped legacy Girvi rows into central workspace preferences.",
        )

    def handle(self, *args, **options):
        dry_run = bool(options.get("dry_run"))
        apply_changes = bool(options.get("apply"))

        if dry_run and apply_changes:
            raise CommandError("Use either --dry-run or --apply, not both.")
        if not dry_run and not apply_changes:
            raise CommandError("Use --dry-run to preview or --apply to write mapped rows.")

        rows = (
            CompanyPreferenceModel.objects.select_related("instance")
            .filter(section__in={"Loan", "Interest_Rate"})
            .order_by("instance_id", "section", "name")
        )
        matched_count = 0
        unmapped_count = 0
        written_count = 0

        mode = "apply" if apply_changes else "dry-run"
        self.stdout.write(f"Legacy Girvi preference migration ({mode}):")
        for row in rows:
            key = f"{row.section}__{row.name}"
            central_key = LEGACY_GIRVI_KEY_MAP.get(key)
            if central_key is None:
                unmapped_count += 1
                continue

            matched_count += 1
            workspace = getattr(row, "instance", None)
            workspace_label = (
                f"{getattr(workspace, 'schema_name', '')} ({getattr(workspace, 'id', '')})"
                if workspace is not None
                else f"workspace_id={row.instance_id}"
            )
            value = company_preference_registry.manager(instance=workspace)[key]
            self.stdout.write(f"  {workspace_label}: {key} -> {central_key}={value}")

            if apply_changes:
                PreferenceService.set_workspace(workspace, central_key, value)
                written_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Inventory complete: "
                f"matched={matched_count}, skipped_unmapped={unmapped_count}, "
                f"written={written_count}"
            )
        )
