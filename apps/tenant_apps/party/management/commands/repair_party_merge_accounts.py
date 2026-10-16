"""Finish retained merges; defaults to a rolled-back preview."""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from apps.tenancy.context import workspace_context
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.party.services.party_merge import repair_merged_party_accounts


class Command(BaseCommand):
    help = "Repair loan/Khata links from recorded Party merges in one explicit Workspace."

    def add_arguments(self, parser):
        parser.add_argument("--workspace-id", type=int, required=True)
        parser.add_argument("--actor-id", type=int, required=True)
        parser.add_argument("--commit", action="store_true")

    def handle(self, *args, **options):
        import json
        actor = get_user_model().objects.get(pk=options["actor_id"])
        totals = dict(merges=0, loans=0, khata=0, committed=options["commit"])
        # One transaction: a broken mapping rolls back every move in this unit.
        with workspace_context(options["workspace_id"]):
            sources = list(Party.objects.filter(metadata__has_key="merged_into_party_id").order_by("pk"))
            for source in sources:
                loans, accounts = repair_merged_party_accounts(source=source, actor=actor)
                totals["merges"] += 1
                totals["loans"] += loans
                totals["khata"] += accounts
            if not options["commit"]:
                transaction.set_rollback(True)
        self.stdout.write(json.dumps(totals))
