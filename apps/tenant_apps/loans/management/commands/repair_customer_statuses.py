"""Preview or apply the owner's existing-customer loan-history status repair."""
import json

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.tenancy.context import workspace_context
from apps.tenant_apps.loans.services.customer_status import repair_customer_statuses


class Command(BaseCommand):
    help = "Activate customers with recorded loans (including exactly linked historical loans); deactivate customers with none."

    def add_arguments(self, parser):
        parser.add_argument("--workspace-id", type=int, required=True)
        parser.add_argument("--actor-id", type=int, required=True)
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--expected-digest")

    def handle(self, *args, **options):
        try:
            actor = get_user_model().objects.get(pk=options["actor_id"])
            with workspace_context(options["workspace_id"]):
                result = repair_customer_statuses(workspace_id=options["workspace_id"], actor=actor,
                    apply=options["apply"], expected_digest=options["expected_digest"])
        except (get_user_model().DoesNotExist, PermissionDenied, ValidationError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(result, sort_keys=True))
