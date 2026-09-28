import json

from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.orgs.models import Company
from apps.tenancy.context import workspace_context
from apps.subscriptions.recurring_cycles import reconcile_cycle
from apps.subscriptions.razorpay_service import BillingProviderError


class Command(BaseCommand):
    help = "Verify and record one known mode-matched recurring paid invoice; never initiates a charge."

    def add_arguments(self, parser):
        parser.add_argument("--workspace-id", type=int, required=True)
        parser.add_argument("--actor-id", type=int, required=True)
        parser.add_argument("--agreement-id", type=int, required=True)
        parser.add_argument("--provider-invoice-id", required=True)
        parser.add_argument("--reason", required=True)

    def handle(self, *args, **options):
        try:
            workspace = Company.all_objects.get(pk=options["workspace_id"])
            actor = get_user_model().objects.get(pk=options["actor_id"], is_active=True)
            with workspace_context(workspace.pk):
                cycle = reconcile_cycle(workspace=workspace, actor=actor, agreement_id=options["agreement_id"],
                    provider_invoice_id=options["provider_invoice_id"], reason=options["reason"])
        except (ObjectDoesNotExist, PermissionDenied, ValidationError, BillingProviderError) as exc:
            message = exc.messages[0] if isinstance(exc, ValidationError) else str(exc)
            raise CommandError(message) from None
        self.stdout.write(json.dumps({"cycle_id": cycle.pk, "invoice_id": cycle.invoice_id,
            "access_action": cycle.access_action, "period_end": cycle.period_end.isoformat()}))
