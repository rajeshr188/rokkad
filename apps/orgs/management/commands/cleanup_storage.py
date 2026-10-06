"""Explicit operator workflow; no URL, timer, prefix purge or recovery expiry."""
import json

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from apps.orgs.models import StorageInventoryRun

from apps.orgs.services.storage_cleanup import (
    CleanupJournal, R2CleanupStore, approval_digest, cleanup_guard, execute_cleanup,
    load_bound, plan_cleanup, prepare_cleanup, private_directory, restore_cleanup,
)


class Command(BaseCommand):
    help = "Review, back up, delete or restore up to 50 exact old media candidates during offline maintenance."

    def add_arguments(self, parser):
        parser.add_argument("action", choices=("candidates", "plan", "inspect", "prepare", "execute", "restore"))
        parser.add_argument("--actor-id", type=int, required=True)
        parser.add_argument("--directory", required=True, help="Existing dedicated private 0700 directory outside application/media trees.")
        parser.add_argument("--inventory-id", type=int)
        parser.add_argument("--object-ids", type=int, nargs="+")
        parser.add_argument("--reason", default="", help="Why these exact objects have no remaining retention obligation.")
        parser.add_argument("--approve-digest", default="")
        parser.add_argument("--writers-stopped", default="", help="Exact bucket/prefix after stopping web, workers, imports and external writers.")
        parser.add_argument("--after-id", type=int, default=0, help="Candidate pagination cursor; at most 50 entries per call.")
        parser.add_argument("--private-details", action="store_true", help="Inspect only: print private keys/reason for review in a secure terminal.")

    def handle(self, *args, **options):
        try:
            actor = get_user_model().objects.get(pk=options["actor_id"])
            if options["private_details"] and options["action"] != "inspect":
                raise CommandError("Private details are available only with inspect")
            directory = private_directory(options["directory"])
            journal = CleanupJournal(directory)
            store = R2CleanupStore()
            action = options["action"]
            if action == "candidates":
                with cleanup_guard(actor):
                    runs = StorageInventoryRun.objects.filter(state="complete", scope=store.scope)
                    run = runs.get(pk=options["inventory_id"]) if options["inventory_id"] else runs.first()
                    if run is None:
                        raise CommandError("Run reconcile_storage first")
                    rows = list(run.inventory_objects.filter(state="unreferenced_review", pk__gt=options["after_id"])
                        .order_by("pk").values("id", "key_digest", "byte_size")[:50])
                self.stdout.write(json.dumps({"inventory_id": run.pk, "candidates": rows,
                                              "after_id": rows[-1]["id"] if rows else None}))
                return
            if action == "plan":
                data = plan_cleanup(actor=actor, inventory_id=options["inventory_id"],
                    object_ids=options["object_ids"] or [], reason=options["reason"], journal=journal, store=store)
            elif action == "prepare":
                data = prepare_cleanup(actor=actor, journal=journal, store=store)
            elif action in ("execute", "restore"):
                fn = execute_cleanup if action == "execute" else restore_cleanup
                data = fn(actor=actor, journal=journal, store=store,
                    approve_digest=options["approve_digest"], writers_stopped=options["writers_stopped"])
            else:
                with cleanup_guard(actor):
                    data = load_bound(journal, store)
            # Do not print customer filenames, object URLs or provider exception text.
            summary = {"plan_id": data["plan"]["id"], "action": action,
                       "objects": len(data["items"]), "bytes": sum(o["head"]["bytes"] for o in data["plan"]["objects"]),
                       "states": [i["state"] for i in data["items"]], "digest": approval_digest(data),
                       "recovery_expiry": None}
            if options["private_details"]:
                summary["private_plan"] = data["plan"]
                summary["private_recovery"] = data["items"]
            self.stdout.write(json.dumps(summary))
        except Exception as exc:
            from django.core.exceptions import ValidationError, PermissionDenied
            # Our validation messages are fixed text; arbitrary provider errors are not.
            if isinstance(exc, (ValidationError, PermissionDenied)):
                message = "; ".join(exc.messages) if isinstance(exc, ValidationError) else str(exc)
            else:
                message = type(exc).__name__
            raise CommandError(f"Cleanup stopped: {message}. Keep private evidence and recovery objects; inspect before resuming.") from None
