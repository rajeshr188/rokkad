"""Explicit operator entry point while recurring Checkout remains unavailable."""
import json

from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.subscriptions import recurring
from apps.subscriptions.razorpay_service import BillingProviderError


class Command(BaseCommand):
    help = "Test-only recurring preparation: bind a plan, create one durable attempt, or reconcile a known provider ID. Grants no access."

    def add_arguments(self, parser):
        parser.add_argument("--actor-id", type=int, required=True)
        actions = parser.add_subparsers(dest="action", required=True)
        bind = actions.add_parser("bind")
        bind.add_argument("--plan-id", type=int, required=True)
        bind.add_argument("--cycle", choices=["monthly", "yearly"], required=True)
        bind.add_argument("--provider-plan-id", required=True)
        bind.add_argument("--reason", required=True)
        create = actions.add_parser("create")
        create.add_argument("--workspace-id", type=int, required=True)
        create.add_argument("--binding-id", type=int, required=True)
        create.add_argument("--total-count", type=int, required=True)
        create.add_argument("--request-key", required=True)
        create.add_argument("--start-at", type=int, help="Optional future Unix timestamp; frozen before provider creation.")
        reconcile = actions.add_parser("reconcile")
        reconcile.add_argument("--workspace-id", type=int, required=True)
        reconcile.add_argument("--agreement-id", type=int, required=True)
        reconcile.add_argument("--provider-subscription-id", required=True)
        reconcile.add_argument("--reason", required=True)

    def handle(self, *args, **options):
        try:
            actor = get_user_model().objects.get(pk=options["actor_id"], is_active=True)
            if options["action"] == "bind":
                binding = recurring.bind_plan(actor=actor, plan_id=options["plan_id"], cycle=options["cycle"],
                    provider_plan_id=options["provider_plan_id"], reason=options["reason"])
                result = {"binding_id": binding.pk, "mode": binding.mode}
            else:
                if options["action"] == "create":
                    agreement = recurring.create_agreement(actor=actor, workspace_id=options["workspace_id"],
                        binding_id=options["binding_id"], total_count=options["total_count"], request_key=options["request_key"],
                        start_at=options["start_at"])
                else:
                    agreement = recurring.reconcile_agreement(actor=actor, workspace_id=options["workspace_id"],
                        agreement_id=options["agreement_id"], provider_subscription_id=options["provider_subscription_id"],
                        reason=options["reason"])
                result = {"agreement_id": agreement.pk, "state": agreement.state, "provider_status": agreement.provider_status}
        except (PermissionDenied, ValidationError, BillingProviderError, ObjectDoesNotExist) as exc:
            message = exc.messages[0] if isinstance(exc, ValidationError) else str(exc)
            raise CommandError(message) from None
        self.stdout.write(json.dumps(result))
