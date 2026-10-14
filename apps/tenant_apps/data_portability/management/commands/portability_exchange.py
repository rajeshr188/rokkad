"""Private chunked export, verification and one-file browser staging."""
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, connection, transaction
from django.urls import reverse

from apps.tenancy.context import workspace_context
from apps.tenant_apps.data_portability import exchange
from apps.tenant_apps.data_portability.contracts import dump
from apps.tenant_apps.data_portability.models import ImportBatch


class Command(BaseCommand):
    help = "Export a partial private exchange, inspect destination receipts, or stage its next chunk for browser review. Never commits financial records."

    def add_arguments(self, parser):
        parser.add_argument("operation", choices=["export", "inspect", "stage"])
        parser.add_argument("--workspace-id", required=True, type=int)
        parser.add_argument("--actor-id", required=True, type=int)
        parser.add_argument("--directory", required=True)
        parser.add_argument("--party-only", action="store_true")
        parser.add_argument("--expected-sha256")
        parser.add_argument("--chunk", type=int)

    def handle(self, *args, **options):
        try:
            actor = get_user_model().objects.get(pk=options["actor_id"])
            operation, directory = options["operation"], Path(options["directory"]).resolve()
            if operation == "export":
                if options["expected_sha256"] or options["chunk"]:
                    raise ValueError("Export does not accept a restore checksum or chunk.")
                if directory.exists() or not directory.parent.is_dir():
                    raise ValueError("Choose a new output directory inside an existing private parent; no files will be replaced.")
                # TemporaryDirectory creates mode 0700. On Windows the private
                # parent must have the user's protected ACL; chmod is no ACL.
                with TemporaryDirectory(prefix=".rokkad-exchange-", dir=directory.parent) as temporary:
                    prepared = Path(temporary) / "prepared"
                    prepared.mkdir(mode=0o700)
                    if connection.in_atomic_block:
                        raise ValueError("Run exchange export in a fresh process, outside any existing transaction.")
                    with transaction.atomic():
                        with connection.cursor() as cursor:
                            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
                        with workspace_context(options["workspace_id"]):
                            manifest = exchange.write_exchange(workspace_id=options["workspace_id"], actor=actor,
                                directory=prepared, include_loans=not options["party_only"], _consistent_snapshot=True)
                    # Publish after the enclosing Workspace transaction commits.
                    # A failed rename never exposes a partial manifest.
                    prepared.rename(directory)
                result = dict(directory=str(directory), sha256=manifest["sha256"], counts=manifest["counts"], chunks=len(manifest["chunks"]), scope="PARTIAL")
            else:
                if options["party_only"]:
                    raise ValueError("Party-only is an export option.")
                if operation == "stage" and (not options["expected_sha256"] or options["chunk"] is None):
                    raise ValueError("Staging needs the reviewed manifest --expected-sha256 and --chunk.")
                if operation == "inspect" and options["chunk"] is not None:
                    raise ValueError("Inspect does not stage a chunk.")
                with workspace_context(options["workspace_id"]):
                    values = dict(workspace_id=options["workspace_id"], actor=actor, directory=directory,
                        expected_sha256=options["expected_sha256"])
                    if operation == "inspect":
                        result = exchange.inspect_exchange(**values)
                    else:
                        batch = exchange.stage_chunk(**values, number=options["chunk"])
                        route = "batch" if isinstance(batch, ImportBatch) else "restore_batch"
                        workspace = exchange.Company.all_objects.get(pk=options["workspace_id"])
                        result = dict(chunk=options["chunk"], batch=str(batch.public_id), state=batch.state,
                            review_url=reverse("workspace_portability:"+route, kwargs=dict(workspace_slug=workspace.slug, batch_id=batch.public_id)))
            self.stdout.write(dump(result))
        except (OSError, ValueError, ObjectDoesNotExist, PermissionDenied, ValidationError, DatabaseError) as exc:
            raise CommandError(str(exc)) from exc
