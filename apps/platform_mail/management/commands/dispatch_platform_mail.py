import time

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
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

    def handle(self, *args, **options):
        if not 1 <= options["limit"] <= 100:
            raise CommandError("Limit must be between 1 and 100.")
        if options["recover_stale"]:
            self.stdout.write(f"Marked uncertain: {recover_stale_sends()}")
            return
        rows = Delivery.objects.filter(status=Delivery.Status.QUEUED, available_at__lte=timezone.now()).order_by("created_at")
        if options["delivery"]:
            try:
                rows = rows.filter(pk=options["delivery"])
            except ValidationError:
                raise CommandError("Invalid delivery ID.") from None
        for pk in list(rows.values_list("pk", flat=True)[:options["limit"]]):
            try:
                outcome = dispatch_one(pk, capture=options["capture"])
            except ValidationError as exc:
                raise CommandError(exc.messages[0]) from None
            self.stdout.write(f"{pk}: {outcome}")
            if options["send"]:
                time.sleep(1.1)  # Single worker, below the initial SES sandbox rate.
