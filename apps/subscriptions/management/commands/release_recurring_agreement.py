import json

from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.subscriptions.recurring_release import release_refunded_agreement
from apps.subscriptions.razorpay_service import BillingProviderError


class Command(BaseCommand):
    help = "Release a cancelled, fully refunded and reviewed Test Mode agreement; never charges or grants access."

    def add_arguments(self, parser):
        parser.add_argument("--workspace-id", type=int, required=True)
        parser.add_argument("--actor-id", type=int, required=True)
        parser.add_argument("--agreement-id", type=int, required=True)
        parser.add_argument("--revision", required=True)
        parser.add_argument("--reason", required=True)

    def handle(self, *args, **options):
        try:
            actor = get_user_model().objects.get(pk=options["actor_id"], is_active=True)
            event = release_refunded_agreement(workspace_id=options["workspace_id"], actor=actor,
                agreement_id=options["agreement_id"], revision=options["revision"], reason=options["reason"])
        except (ObjectDoesNotExist, PermissionDenied, ValidationError, BillingProviderError) as exc:
            message = exc.messages[0] if isinstance(exc, ValidationError) else str(exc)
            raise CommandError(message) from None
        self.stdout.write(json.dumps({"release_event_id": event.pk, "agreement_id": event.agreement_id}))
