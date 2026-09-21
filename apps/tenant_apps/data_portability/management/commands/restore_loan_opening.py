"""Bounded operator preview/confirmed restore of one exported opening loan."""
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.tenancy.context import workspace_context
from apps.tenant_apps.loans.services.history_contract import MAX_BYTES, dump
from apps.tenant_apps.loans.services.opening_restore import _access, preview_opening_restore, commit_opening_restore


class Command(BaseCommand):
    help = "Preview one opening export restore. Commit requires --commit and the exact --expected-sha256 from the reviewed preview."

    def add_arguments(self, parser):
        parser.add_argument("--workspace-id", required=True, type=int)
        parser.add_argument("--actor-id", required=True, type=int)
        parser.add_argument("--source", required=True, help="One bounded loan-opening.jsonl export.")
        for name in ("borrower-id", "revision-id", "series-id", "product-version-id"):
            parser.add_argument("--" + name, required=True, type=int)
        parser.add_argument("--commit", action="store_true")
        parser.add_argument("--expected-sha256")

    def handle(self, *args, **options):
        try:
            actor = get_user_model().objects.get(pk=options["actor_id"])
            with workspace_context(options["workspace_id"]):
                _access(options["workspace_id"], actor)
                if bool(options["commit"]) != bool(options["expected_sha256"]):
                    raise ValueError("Commit requires both --commit and the reviewed --expected-sha256; omit both for preview.")
                with Path(options["source"]).open("rb") as stream:
                    content = stream.read(MAX_BYTES + 1)
                kwargs = dict(workspace_id=options["workspace_id"], actor=actor, content=content,
                    mapping={key: options[key] for key in ("borrower_id", "revision_id", "series_id", "product_version_id")})
                if options["commit"]:
                    origin, summary = commit_opening_restore(**kwargs, expected_sha256=options["expected_sha256"], confirmed=True)
                    result = {"committed": True, "loan_id": origin.loan_id, "summary": summary}
                else:
                    result = {"committed": False, **preview_opening_restore(**kwargs)}
            self.stdout.write(dump(result))
        except (OSError, ValueError, ObjectDoesNotExist, PermissionDenied, ValidationError) as exc:
            raise CommandError(str(exc)) from exc
