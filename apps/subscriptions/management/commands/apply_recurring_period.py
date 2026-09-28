import json

from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.orgs.models import Company
from apps.tenancy.context import workspace_context
from apps.subscriptions.recurring_access import apply_held_period
from apps.subscriptions.razorpay_service import BillingProviderError


class Command(BaseCommand):
    help = "Apply one reviewed, started Test Mode recurring period; never charges or changes immutable payment evidence."

    def add_arguments(self, parser):
        parser.add_argument("--workspace-id", type=int, required=True)
        parser.add_argument("--actor-id", type=int, required=True)
        parser.add_argument("--cycle-id", type=int, required=True)
        parser.add_argument("--revision", required=True)
        parser.add_argument("--reason", required=True)

    def handle(self, *args, **options):
        try:
            workspace = Company.all_objects.get(pk=options["workspace_id"])
            actor = get_user_model().objects.get(pk=options["actor_id"], is_active=True)
            with workspace_context(workspace.pk):
                resolution = apply_held_period(workspace=workspace, actor=actor, cycle_id=options["cycle_id"],
                    revision=options["revision"], reason=options["reason"])
        except (ObjectDoesNotExist, PermissionDenied, ValidationError, BillingProviderError) as exc:
            message = exc.messages[0] if isinstance(exc, ValidationError) else str(exc)
            raise CommandError(message) from None
        self.stdout.write(json.dumps({"resolution_id": resolution.pk, "cycle_id": resolution.cycle_id,
            "applied_period_end": resolution.evidence["after"]["end_date"]}))
