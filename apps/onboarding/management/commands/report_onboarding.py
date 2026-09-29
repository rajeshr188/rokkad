"""Read-only, platform-admin onboarding snapshot (contains account emails)."""
import json

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.serializers.json import DjangoJSONEncoder
from django.utils.dateparse import parse_datetime

from apps.onboarding.services.monitoring import onboarding_report


class Command(BaseCommand):
    help = "Read-only onboarding report; output contains private account emails."

    def add_arguments(self, parser):
        parser.add_argument("--actor-id", type=int, required=True)
        parser.add_argument("--since", help="Signup cutoff, ISO timestamp with time zone; default last 30 days")
        parser.add_argument("--query", default="")
        parser.add_argument("--page", type=int, default=1)

    def handle(self, *args, **options):
        actor = get_user_model().objects.filter(pk=options["actor_id"]).first()
        try:
            since = parse_datetime(options["since"]) if options["since"] else None
            if options["since"] and since is None:
                raise ValidationError("Invalid signup cutoff.")
            report = onboarding_report(actor=actor, since=since, query=options["query"], page=options["page"])
        except (PermissionDenied, ValidationError, ValueError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(report, cls=DjangoJSONEncoder))
