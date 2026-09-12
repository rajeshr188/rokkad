from datetime import date
import time

from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections, DatabaseError
from django.utils import timezone

from apps.tenant_apps.loans.services.risk_snapshots import RiskSnapshotRefreshError
from apps.tenant_apps.loans.services.risk_jobs import reassess_pawn_loans_pass


class Command(BaseCommand):
    help = "Refresh a bounded batch of active loans in an explicit Workspace; optionally repeat."

    def add_arguments(self, parser):
        parser.add_argument("--workspace-id", type=int, action="append", nargs="+", required=True,
                            help="Explicit Workspace ID; repeat this option to process a bounded turn for each.")
        parser.add_argument("--as-of", type=date.fromisoformat)
        parser.add_argument("--batch-size", type=int, default=100)
        parser.add_argument("--repeat-seconds", type=int, default=0,
                            help="Idle/error retry interval, 60-86400 seconds. Zero runs one pass per Workspace.")
        parser.add_argument("--busy-seconds", type=int, default=1,
                            help="Pause between rounds while assessments succeed (1-60 seconds).")

    def handle(self, *args, **options):
        interval = options["repeat_seconds"]
        if interval and (interval < 60 or interval > 86400 or options["as_of"] is not None):
            raise CommandError("Repeat interval must be 60–86400 seconds and cannot use --as-of.")
        supplied_ids = options["workspace_id"]
        groups = (supplied_ids,) if isinstance(supplied_ids, int) else supplied_ids
        workspace_ids = tuple(dict.fromkeys(value for group in groups
            for value in (group if isinstance(group, (list, tuple)) else (group,))))
        busy = options["busy_seconds"]
        if any(value < 1 for value in workspace_ids) or not 1 <= options["batch_size"] <= 1000:
            raise CommandError("Use positive Workspace IDs and a batch size from 1 to 1000.")
        if not workspace_ids or not 1 <= busy <= 60:
            raise CommandError("Specify a Workspace and a busy interval from 1 to 60 seconds.")
        try:
            while True:
                progress, failures = False, 0
                for workspace_id in workspace_ids:
                    close_old_connections()
                    try:
                        result = self._run_batch({**options, "workspace_id": workspace_id})
                        progress = progress or result["current"] > 0
                        failures += len(result["errors"])
                    except CommandError as exc:
                        failures += 1
                        self.stderr.write(f"workspace={workspace_id} {exc}")
                    finally:
                        close_old_connections()
                if not interval:
                    if failures:
                        raise CommandError(f"{failures} PawnLoan assessments or Workspace passes failed.")
                    return
                time.sleep(busy if progress else interval)
        except KeyboardInterrupt:
            self.stdout.write("Monitoring stopped.")

    def _run_batch(self, options):
        try:
            result = reassess_pawn_loans_pass(workspace_id=options["workspace_id"],
                as_of_date=options["as_of"] or timezone.localdate(), batch_size=options["batch_size"])
        except (RiskSnapshotRefreshError, DatabaseError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"workspace={options['workspace_id']} selected={result['selected']} current={result['current']} errors={len(result['errors'])}"))
        for row in result["errors"]:
            self.stderr.write(f"workspace={options['workspace_id']} loan={row['loan_id']} error={row['error']}")
        return result
