from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_datetime
from django.utils import timezone

from apps.tenant_apps.loans.services import dispatch_due_pawn_loan_notices
from apps.tenant_apps.loans.management.workspace import command_workspace


class Command(BaseCommand):
    help = "Dispatch previously queued PawnLoan notices in one explicit active Workspace."

    def add_arguments(self, parser):
        parser.add_argument("--workspace-id", type=int, required=True)
        parser.add_argument("--as-of", dest="as_of")
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        as_of = None
        if options.get("as_of"):
            try:
                as_of = parse_datetime(options["as_of"])
            except (ValueError, TypeError) as exc:
                raise CommandError("--as-of must be an ISO-8601 datetime.") from exc
            if as_of is None:
                raise CommandError("--as-of must be an ISO-8601 datetime.")
            if timezone.is_naive(as_of):
                as_of = timezone.make_aware(as_of, timezone.get_current_timezone())
        if not 1 <= options["limit"] <= 1000:
            raise CommandError("--limit must be between 1 and 1000.")
        with command_workspace(options["workspace_id"]):
            summary = dispatch_due_pawn_loan_notices(
                as_of=as_of,
                limit=options["limit"],
            )
        self.stdout.write(
            self.style.SUCCESS(
                f"Workspace {options['workspace_id']} PawnLoan notices: due={summary.due_count}, "
                f"sent={summary.sent_count}, failed={summary.failed_count}."
            )
        )
