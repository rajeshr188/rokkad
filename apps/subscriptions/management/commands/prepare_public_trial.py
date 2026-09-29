"""Prepare the reviewed free offer without publishing it or assigning access."""
import json
from decimal import Decimal
from types import SimpleNamespace

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection, transaction

from apps.orgs.audit import AuditLog
from apps.orgs.permissions import is_platform_admin
from apps.subscriptions.models import Plan, RecurringPlanBinding
from apps.subscriptions.public_trial import PUBLIC_TRIAL_TERMS
from apps.subscriptions.services import build_entitlement_defaults


TRIAL_PLAN = dict(
    name="Rokkad 30-day public trial", tier="starter",
    description="30 days for one Workspace, owner plus five staff. No card or automatic charge.",
    price=Decimal("0.00"), yearly_price=Decimal("0.00"), extra_user_price=Decimal("0.00"),
    billing_cycle="monthly", trial_days=30, max_users=6, is_active=True,
    # These retired/unsupported commercial fields grant no additional capability.
    max_products=0, max_warehouses=0, max_transactions_per_month=0, max_invoices_per_month=0,
    has_advanced_reporting=False, has_multi_warehouse=False, has_approvals_workflow=False,
    has_api_access=False, has_custom_fields=False,
)


class Command(BaseCommand):
    help = "Preview the 30-day/six-member free Plan; --apply saves only the Plan and audit, never activation."

    def add_arguments(self, parser):
        parser.add_argument("--actor-id", required=True, type=int)
        parser.add_argument("--reason", required=True)
        parser.add_argument("--apply", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            actor = get_user_model().objects.get(pk=options["actor_id"])
            if not actor.is_active or not is_platform_admin(actor):
                raise PermissionDenied("An active platform administrator is required.")
            reason = options["reason"].strip()
            if not reason or len(reason) > 1000:
                raise ValidationError("Provide a reason of 1 to 1000 characters.")
            if any((settings.BILLING_ALLOW_TRIAL_START, settings.BILLING_CHECKOUT_ENABLED,
                    settings.BILLING_RECURRING_ENABLED)):
                raise ValidationError("Prepare the offer with trial signup and both payment switches paused.")
            if options["apply"]:
                # A short catalog lock also serializes the first insert (no unique name field).
                with connection.cursor() as cursor:
                    cursor.execute("LOCK TABLE subscriptions_plan IN SHARE ROW EXCLUSIVE MODE")
            existing = list(Plan.objects.filter(name=TRIAL_PLAN["name"]))
            if len(existing) > 1:
                raise ValidationError("Multiple trial plans need operator review; no plan was changed.")
            plan = existing[0] if existing else Plan(**TRIAL_PLAN)
            if existing and (any(getattr(plan, key) != value for key, value in TRIAL_PLAN.items())
                             or RecurringPlanBinding.objects.filter(plan=plan).exists()):
                raise ValidationError("The existing trial plan differs; no terms were overwritten.")
            plan.full_clean()
            created = options["apply"] and not existing
            if created:
                plan.save()
                AuditLog.log("BILLING_UPDATE", user=actor, company=None,
                    description="Prepared public trial catalog: " + reason, content_object=plan,
                    data=json.loads(json.dumps({"terms_version": PUBLIC_TRIAL_TERMS,
                                               "plan": TRIAL_PLAN, "published": False}, cls=DjangoJSONEncoder)))
            self.stdout.write(json.dumps({"plan_id": plan.pk, "created": bool(created),
                "preview": not options["apply"], "published": False, "terms_version": PUBLIC_TRIAL_TERMS,
                "plan": TRIAL_PLAN, "entitlements": build_entitlement_defaults(SimpleNamespace(plan=plan)),
            }, cls=DjangoJSONEncoder))
        except (get_user_model().DoesNotExist, PermissionDenied, ValidationError) as exc:
            raise CommandError(str(exc)) from None
