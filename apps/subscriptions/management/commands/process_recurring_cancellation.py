from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.subscriptions.recurring_owner import process_cancellation
from apps.subscriptions.razorpay_service import BillingProviderError


class Command(BaseCommand):
    help = "Deliver a saved Test Mode cancellation once, or fetch an uncertain result. Never re-POST."

    def add_arguments(self, parser):
        parser.add_argument("--request-id", type=int, required=True)

    def handle(self, *args, **options):
        try:
            agreement = process_cancellation(request_id=options["request_id"])
        except (ObjectDoesNotExist, PermissionDenied, ValidationError, BillingProviderError) as exc:
            raise CommandError(exc.messages[0] if isinstance(exc, ValidationError) else str(exc)) from None
        self.stdout.write(f"Agreement {agreement.pk}: {agreement.provider_status}. Paid dates unchanged.")
