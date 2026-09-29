import time

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.utils import timezone

from apps.platform_mail.models import Delivery
from apps.platform_mail.services import dispatch_one, recover_stale_sends


class Command(BaseCommand):
    help = "Dispatch a bounded committed platform-mail queue; capture prints IDs/status only."

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--send", action="store_true")
        group.add_argument("--capture", action="store_true")
        group.add_argument("--recover-stale", action="store_true")
        parser.add_argument("--limit", type=int, default=20)
        parser.add_argument("--delivery", type=str)
        scope = parser.add_mutually_exclusive_group()
        scope.add_argument("--invitations-only", action="store_true",
                           help="Select invitations only before selecting the bounded batch.")
        scope.add_argument("--receipts-only", action="store_true",
                           help="Select receipts only before selecting the bounded batch.")
        scope.add_argument("--accounts-only", action="store_true")
        scope.add_argument("--invitations-and-accounts", action="store_true",
                           help="Select invitations and account emails, excluding every receipt.")

    def handle(self, *args, **options):
        if not 1 <= options["limit"] <= 100:
            raise CommandError("Limit must be between 1 and 100.")
        scopes = {
            "invitations_only": (Q(invitation__isnull=False), "invitation-only"),
            "receipts_only": (Q(invoice__isnull=False), "receipt-only"),
            "accounts_only": (Q(account_email__isnull=False), "account-only"),
            "invitations_and_accounts": (Q(invoice__isnull=True), "invitation-and-account"),
        }
        selected = [value for key, value in scopes.items() if options[key]]
        if len(selected) > 1:
            raise CommandError("Choose only one source scope.")
        if options["recover_stale"]:
            if selected:
                raise CommandError("Source scope applies to dispatch, not stale-claim recovery.")
            self.stdout.write(f"Marked uncertain: {recover_stale_sends()}")
            return
        rows = Delivery.objects.filter(status=Delivery.Status.QUEUED, available_at__lte=timezone.now()).order_by("created_at")
        if options["delivery"]:
            try:
                rows = rows.filter(pk=options["delivery"])
            except ValidationError:
                raise CommandError("Invalid delivery ID.") from None
            if selected and rows.exclude(selected[0][0]).exists():
                raise CommandError(f"The selected delivery is outside {selected[0][1]} scope.")
        if selected:
            rows = rows.filter(selected[0][0])
        for pk in list(rows.values_list("pk", flat=True)[:options["limit"]]):
            try:
                outcome = dispatch_one(pk, capture=options["capture"])
            except ValidationError as exc:
                raise CommandError(exc.messages[0]) from None
            self.stdout.write(f"{pk}: {outcome}")
            if options["send"]:
                time.sleep(1.1)  # Single worker, below the initial SES sandbox rate.
