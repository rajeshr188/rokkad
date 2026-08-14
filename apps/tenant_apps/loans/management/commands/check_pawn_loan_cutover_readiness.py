import json
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from apps.tenant_apps.loans.selectors.cutover_readiness import (
    get_pawn_loan_cutover_readiness,
)


ACK_OPTIONS = {
    "ack_backup": "BACKUP_REHEARSED",
    "ack_recovery": "RECOVERY_REHEARSED",
    "ack_support": "SUPPORT_READY",
    "ack_monitoring": "MONITORING_READY",
    "ack_permissions": "PERMISSIONS_REVIEWED",
    "ack_pilot_workflow": "PILOT_WORKFLOW_ACCEPTED",
}


class Command(BaseCommand):
    help = (
        "Fail-closed PawnLoan operational-readiness gate. "
        "Run inside the target tenant schema."
    )

    def add_arguments(self, parser):
        parser.add_argument("--as-of", default=date.today().isoformat())
        parser.add_argument("--format", choices=("text", "json"), default="text")
        parser.add_argument("--fail-on-blocker", action="store_true")
        parser.add_argument("--ack-backup", action="store_true")
        parser.add_argument("--ack-recovery", action="store_true")
        parser.add_argument("--ack-support", action="store_true")
        parser.add_argument("--ack-monitoring", action="store_true")
        parser.add_argument("--ack-permissions", action="store_true")
        parser.add_argument("--ack-pilot-workflow", action="store_true")

    def handle(self, *args, **options):
        try:
            as_of_date = date.fromisoformat(options["as_of"])
        except ValueError as exc:
            raise CommandError("--as-of must use YYYY-MM-DD format.") from exc
        acknowledgements = {
            code: options[name] for name, code in ACK_OPTIONS.items()
        }
        readiness = get_pawn_loan_cutover_readiness(
            as_of_date=as_of_date,
            acknowledgements=acknowledgements,
        )
        if options["format"] == "json":
            self.stdout.write(json.dumps(readiness.as_dict(), sort_keys=True))
        else:
            self._write_text(readiness)
        if options["fail_on_blocker"] and not readiness.is_ready:
            raise CommandError(
                f"PawnLoan operations are NO-GO: {readiness.blocker_count} blocker(s)."
            )

    def _write_text(self, readiness):
        state = "GO" if readiness.is_ready else "NO-GO"
        self.stdout.write(
            f"PawnLoan operational readiness for workspace {readiness.workspace_id} "
            f"as of {readiness.as_of_date}: {state}"
        )
        for check in readiness.checks:
            status = "PASS" if check.passed else "BLOCK"
            mode = "AUTO" if check.automated else "MANUAL"
            self.stdout.write(f"  [{status}] [{mode}] {check.code}: {check.message}")


__all__ = ["ACK_OPTIONS", "Command"]
