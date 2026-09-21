"""Operator bridge: stage one prepared review; final approval stays in the browser."""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.urls import reverse

from apps.tenancy.context import workspace_context
from apps.tenant_apps.loans.services.history_setup import require_history_setup_access
from apps.tenant_apps.loans.services.opening_import import PROFILE
from apps.tenant_apps.data_portability.opening_review import read_documents
from apps.tenant_apps.data_portability.legacy_opening import stage
from apps.tenant_apps.data_portability.legacy_profiles import PROFILES


class Command(BaseCommand):
    help = "Stage one operator-prepared legacy opening against its dump for owner browser review. Never commits a loan."

    def add_arguments(self, parser):
        parser.add_argument("--workspace-id", required=True, type=int)
        parser.add_argument("--actor-id", required=True, type=int)
        parser.add_argument("--dump", required=True)
        parser.add_argument("--opening-file", required=True, help="One bounded UTF-8 JSONL record: profile, review and setup, prepared by the migration operator.")
        parser.add_argument("--pg-restore", default="pg_restore")
        parser.add_argument("--source-profile", choices=sorted(PROFILES),
                            help="Verify the versioned source profile and retain its reviewed correction ledger.")
        parser.add_argument("--payment-review-file", help="One bounded JSONL decision excluding the exact reviewed payment rows; original source evidence is retained.")

    def handle(self, *args, **options):
        try:
            actor = get_user_model().objects.get(pk=options["actor_id"])
            with workspace_context(options["workspace_id"]):
                workspace = require_history_setup_access(options["workspace_id"], actor)
                rows = read_documents(options["opening_file"])
                if len(rows) != 1 or not isinstance(rows[0], dict) or set(rows[0]) != {"profile", "review", "setup"} or rows[0]["profile"] != PROFILE:
                    raise ValueError("Supply exactly one prepared opening commit document.")
                payment_review = None
                if options["payment_review_file"]:
                    decisions = read_documents(options["payment_review_file"])
                    if len(decisions) != 1 or not isinstance(decisions[0], dict):
                        raise ValueError("Supply exactly one reviewed payment-exclusion decision.")
                    payment_review = decisions[0]
                batch = stage(workspace_id=workspace.pk, actor=actor, archive_path=options["dump"],
                    review=rows[0]["review"], setup=rows[0]["setup"], pg_restore=options["pg_restore"],
                    source_profile=options["source_profile"], payment_review=payment_review)
                url = reverse("workspace_portability:opening_batch", kwargs={"workspace_slug": workspace.slug, "batch_id": batch.public_id})
            self.stdout.write("Source-verified opening staged. No loan imported. Owner review: " + url)
        except (ValueError, ObjectDoesNotExist, PermissionDenied, ValidationError) as exc:
            raise CommandError(str(exc)) from exc
