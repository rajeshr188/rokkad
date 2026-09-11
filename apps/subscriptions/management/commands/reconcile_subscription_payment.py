import json

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.orgs.models import Company
from apps.tenancy.context import workspace_context
from apps.subscriptions.razorpay_service import BillingProviderError
from apps.subscriptions.recovery import reconcile_payment


class Command(BaseCommand):
    help = "Verify a known Workspace checkout against provider records; --apply records the result. Never issues refunds."

    def add_arguments(self, parser):
        parser.add_argument("--workspace-id", type=int, required=True)
        parser.add_argument("--actor-id", type=int, required=True)
        parser.add_argument("--invoice-id", type=int, required=True)
        parser.add_argument("--payment-id", required=True)
        parser.add_argument("--refund-id")
        parser.add_argument("--reason", required=True)
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        workspace = Company.all_objects.filter(pk=options["workspace_id"]).first()
        actor = get_user_model().objects.filter(pk=options["actor_id"], is_active=True).first()
        if not workspace or not actor:
            raise CommandError("An existing Workspace and active actor are required.")
        try:
            with workspace_context(workspace.pk):
                result = reconcile_payment(
                    workspace=workspace, actor=actor, invoice_id=options["invoice_id"],
                    payment_id=options["payment_id"], refund_id=options["refund_id"],
                    reason=options["reason"], apply=options["apply"],
                )
        except (PermissionDenied, ValidationError, BillingProviderError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(result))
