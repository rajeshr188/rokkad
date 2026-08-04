from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_datetime

from apps.tenant_apps.loans.services import dispatch_due_pawn_loan_notices


class Command(BaseCommand):
    help = "Dispatch due queued PawnLoan notices in the active tenant schema."

    def add_arguments(self, parser):
        parser.add_argument("--as-of", dest="as_of")
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        as_of = None
        if options.get("as_of"):
            as_of = parse_datetime(options["as_of"])
            if as_of is None:
                raise CommandError("--as-of must be an ISO-8601 datetime.")
        if options["limit"] < 1:
            raise CommandError("--limit must be positive.")
        summary = dispatch_due_pawn_loan_notices(
            as_of=as_of,
            limit=options["limit"],
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"PawnLoan notices: due={summary.due_count}, "
                f"sent={summary.sent_count}, failed={summary.failed_count}."
            )
        )
