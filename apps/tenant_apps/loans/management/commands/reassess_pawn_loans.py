from datetime import date

from django.core.management.base import BaseCommand, CommandError

from apps.tenant_apps.loans.services.risk_snapshots import RiskSnapshotRefreshError, reassess_pawn_loans_batch


class Command(BaseCommand):
    help = "Refresh a bounded batch of PawnLoan risk projections in the active tenant schema."

    def add_arguments(self, parser):
        parser.add_argument("--workspace-id", type=int, required=True)
        parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
        parser.add_argument("--batch-size", type=int, default=100)

    def handle(self, *args, **options):
        try:
            result = reassess_pawn_loans_batch(workspace_id=options["workspace_id"], as_of_date=options["as_of"], batch_size=options["batch_size"])
        except RiskSnapshotRefreshError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"selected={result['selected']} current={result['current']} errors={len(result['errors'])}"))
        for row in result["errors"]:
            self.stderr.write(f"loan={row['loan_id']} error={row['error']}")
        if result["errors"]:
            raise CommandError(
                f"{len(result['errors'])} PawnLoan risk assessment(s) failed."
            )
