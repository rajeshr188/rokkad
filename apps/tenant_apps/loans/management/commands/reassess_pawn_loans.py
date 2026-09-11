from datetime import date
import time

from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections
from django.utils import timezone

from apps.tenancy.context import workspace_context
from apps.tenant_apps.loans.services.risk_snapshots import RiskSnapshotRefreshError, reassess_pawn_loans_batch


class Command(BaseCommand):
    help = "Refresh a bounded batch of active loans in an explicit Workspace; optionally repeat."

    def add_arguments(self, parser):
        parser.add_argument("--workspace-id", type=int, required=True)
        parser.add_argument("--as-of", type=date.fromisoformat)
        parser.add_argument("--batch-size", type=int, default=100)
        parser.add_argument("--repeat-seconds", type=int, default=0,
                            help="Repeat with today's local date, at least 60 seconds apart. Zero runs once.")

    def handle(self, *args, **options):
        interval = options["repeat_seconds"]
        if interval and (interval < 60 or interval > 86400 or options["as_of"] is not None):
            raise CommandError("Repeat interval must be 60–86400 seconds and cannot use --as-of.")
        if options["workspace_id"] < 1 or not 1 <= options["batch_size"] <= 1000:
            raise CommandError("Use a positive Workspace ID and a batch size from 1 to 1000.")
        try:
            while True:
                close_old_connections()
                try:
                    self._run_batch(options)
                except CommandError as exc:
                    if not interval:
                        raise
                    self.stderr.write(str(exc))
                finally:
                    close_old_connections()
                if not interval:
                    return
                time.sleep(interval)
        except KeyboardInterrupt:
            self.stdout.write("Monitoring stopped.")

    def _run_batch(self, options):
        try:
            with workspace_context(options["workspace_id"]):
                result = reassess_pawn_loans_batch(workspace_id=options["workspace_id"], as_of_date=options["as_of"] or timezone.localdate(), batch_size=options["batch_size"])
        except RiskSnapshotRefreshError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"selected={result['selected']} current={result['current']} errors={len(result['errors'])}"))
        for row in result["errors"]:
            self.stderr.write(f"loan={row['loan_id']} error={row['error']}")
        if result["errors"]:
            raise CommandError(
                f"{len(result['errors'])} PawnLoan risk assessment(s) failed."
            )
