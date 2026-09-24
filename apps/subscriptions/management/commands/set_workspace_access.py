from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_datetime
from apps.orgs.models import Company
from apps.subscriptions.models import Plan
from apps.subscriptions.access_policy import record_access_decision


class Command(BaseCommand):
    help = "Record an audited platform access extension/restriction for one Workspace."

    def add_arguments(self, parser):
        parser.add_argument("--workspace-id", type=int, required=True)
        parser.add_argument("--actor-id", type=int, required=True)
        parser.add_argument("--mode", choices=["full", "read_only", "default"], required=True)
        parser.add_argument("--until", help="ISO datetime including timezone, e.g. 2026-11-01T00:00:00+05:30")
        parser.add_argument("--reason", required=True)
        parser.add_argument("--plan-id", type=int)

    def handle(self, *args, **options):
        try:
            workspace = Company.all_objects.get(pk=options["workspace_id"])
            actor = get_user_model().objects.get(pk=options["actor_id"])
            expiry = parse_datetime(options["until"]) if options["until"] else None
            if options["until"] and expiry is None:
                raise ValidationError("Invalid ISO expiry date.")
            plan = Plan.objects.get(pk=options["plan_id"]) if options["plan_id"] else None
            decision = record_access_decision(workspace=workspace, actor=actor, mode=options["mode"],
                expires_at=expiry, reason=options["reason"], plan=plan)
        except (Company.DoesNotExist, get_user_model().DoesNotExist, Plan.DoesNotExist,
                PermissionDenied, ValidationError, ValueError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(f"Workspace {workspace.pk}: recorded access decision {decision.pk} ({decision.mode}).")
