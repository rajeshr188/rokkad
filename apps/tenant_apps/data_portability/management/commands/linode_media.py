"""Plan and attach verified media to an explicitly selected isolated rehearsal."""
import hashlib
import json
from collections import Counter
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from apps.tenancy.context import workspace_context
from apps.tenant_apps.data_portability.legacy_media import application_names, attach, resolve_target, validate_evidence
from apps.tenant_apps.data_portability.legacy_media_storage import R2MediaCopies
from apps.tenant_apps.data_portability.models import LegacyMediaReceipt
from apps.tenant_apps.loans.services.history_setup import require_history_setup_access


def checked_jsonl(path, expected):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise CommandError("Input checksum differs from the reviewed evidence.")
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


class Command(BaseCommand):
    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument("action", choices=["plan", "apply"])
        parser.add_argument("--database", required=True)
        parser.add_argument("--actor", required=True, type=int)
        parser.add_argument("--workspaces", required=True, help='JSON schema-to-Workspace-ID mapping')
        parser.add_argument("--output", required=True)
        parser.add_argument("--references")
        parser.add_argument("--references-sha256")
        parser.add_argument("--customers")
        parser.add_argument("--customers-sha256")
        parser.add_argument("--namespace")
        parser.add_argument("--archive-sha256")
        parser.add_argument("--plan")
        parser.add_argument("--plan-sha256")
        parser.add_argument("--confirmed", action="store_true")
        parser.add_argument("--workers", type=int, default=16)

    def handle(self, *args, **options):
        database = options["database"]
        if connection.settings_dict["NAME"] != database or not database.startswith("rokkad_baseline_rehearsal_"):
            raise CommandError("This command currently supports only an explicitly selected isolated rehearsal database.")
        with connection.cursor() as cursor:
            cursor.execute("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user")
            if any(cursor.fetchone()):
                raise CommandError("Use the restricted runtime role for media admission.")
        actor = get_user_model().objects.get(pk=options["actor"])
        workspaces = json.loads(options["workspaces"])
        if len(set(workspaces.values())) != len(workspaces):
            raise CommandError("Each source branch must have a distinct Workspace.")
        for workspace_id in workspaces.values():
            with workspace_context(workspace_id):
                require_history_setup_access(workspace_id, actor)
        output = Path(options["output"])
        output.mkdir(parents=True, exist_ok=True)
        (output / ".gitignore").write_text("*\n")
        if options["action"] == "plan":
            self.plan(options, workspaces, actor, output)
        else:
            self.apply(options, workspaces, actor, output)

    def plan(self, options, workspaces, actor, output):
        rows = checked_jsonl(options["references"], options["references_sha256"])
        customers = checked_jsonl(options["customers"], options["customers_sha256"])
        customer_rows = {(r["schema"], r["source_row"]["id"]): r for r in customers}
        if len(customer_rows) != len(customers):
            raise CommandError("Duplicate customer source rows.")
        defaults = Counter((r["schema"], r["source_row"]["customer_id"]) for r in customers if r["source_row"]["is_default"] == "t")
        if any(count > 1 for count in defaults.values()):
            raise CommandError("Multiple default customer photographs require owner review.")
        plan, counts, seen = [], Counter(), set()
        for row in rows:
            source = row["source"]
            if source["schema"] not in workspaces:
                raise CommandError("A source schema has no explicit destination.")
            if row["status"] != "EXACT_SOURCE_FILE_PRESERVED":
                counts[row["status"]] += 1
                continue
            evidence = {k: row[k] for k in ("source", "status", "verified_source_file")}
            evidence.update(namespace=options["namespace"], archive_sha256=options["archive_sha256"])
            if source["table"] == "contact_customerpic":
                evidence["customer_source"] = customer_rows[(source["schema"], source["source_id"])]
            identity = validate_evidence(evidence)
            if identity in seen:
                raise CommandError("Duplicate source photo identity.")
            seen.add(identity)
            workspace_id = workspaces[source["schema"]]
            with workspace_context(workspace_id):
                kind, target = resolve_target(workspace_id=workspace_id, actor=actor, evidence=evidence)
            names = application_names(workspace_id=workspace_id, evidence=evidence, kind=kind)
            plan.append(dict(database=options["database"], workspace_id=workspace_id, kind=kind,
                             target_id=target.pk, evidence=evidence, names=names))
            counts[kind] += 1
            if len(plan) % 1000 == 0:
                self.stdout.write(f"Resolved {len(plan)} photographs")
                self.stdout.flush()
        raw = b"".join((json.dumps(r, sort_keys=True) + "\n").encode() for r in plan)
        (output / "plan.jsonl").write_bytes(raw)
        report = {"state": "PLANNED", "database": options["database"], "counts": counts,
                  "plan_sha256": hashlib.sha256(raw).hexdigest(), "application_copies": sum(len(r["names"]) for r in plan)}
        (output / "plan-summary.json").write_text(json.dumps(report, indent=2))
        self.stdout.write(json.dumps(report))

    def apply(self, options, workspaces, actor, output):
        if not options["confirmed"] or not 1 <= options["workers"] <= 32:
            raise CommandError("Confirm the exact plan and select 1–32 copy workers.")
        rows = checked_jsonl(options["plan"], options["plan_sha256"])
        # Check the whole plan and all destination identities before storage writes.
        pending, counts = [], Counter()
        for row in rows:
            evidence = row["evidence"]
            workspace_id = workspaces[evidence["source"]["schema"]]
            if row["database"] != options["database"] or row["workspace_id"] != workspace_id:
                raise CommandError("Plan destination differs from the selected rehearsal.")
            system, source_id = validate_evidence(evidence)
            with workspace_context(workspace_id):
                receipt = LegacyMediaReceipt.objects.filter(workspace_id=workspace_id, source_system=system, source_id=source_id).first()
                if receipt:
                    attach(workspace_id=workspace_id, actor=actor, evidence=evidence, storage=None)
                    counts["already_attached"] += 1
                    continue
                kind, target = resolve_target(workspace_id=workspace_id, actor=actor, evidence=evidence)
                if row["kind"] != kind or row["target_id"] != target.pk or row["names"] != application_names(workspace_id=workspace_id, evidence=evidence, kind=kind):
                    raise CommandError("Source binding changed after planning.")
                if kind == "party" and row["names"].get("profile") and target.profile_photo:
                    raise CommandError("A destination Party profile photo changed; review before attachment.")
            pending.append(row)
            if len(pending) % 1000 == 0:
                self.stdout.write(f"Rechecked {len(pending)} pending attachments")
                self.stdout.flush()
        storage = R2MediaCopies()
        def prepare(row):
            storage.prepare(row["names"], row["evidence"]["verified_source_file"])
            return row
        with (output / "receipts.jsonl").open("a", encoding="utf-8") as report, ThreadPoolExecutor(max_workers=options["workers"]) as executor:
            iterator, queue = iter(pending), set()
            for _ in range(options["workers"]):
                row = next(iterator, None)
                if row is not None:
                    queue.add(executor.submit(prepare, row))
            while queue:
                completed, queue = wait(queue, return_when=FIRST_COMPLETED)
                for future in completed:
                    row = future.result()
                    with workspace_context(row["workspace_id"]):
                        receipt, created = attach(workspace_id=row["workspace_id"], actor=actor, evidence=row["evidence"], storage=storage)
                    counts["created" if created else "already_attached"] += 1
                    report.write(json.dumps({"receipt_id": receipt.pk, "workspace_id": row["workspace_id"],
                        "source_system": receipt.source_system, "source_id": receipt.source_id, "target": receipt.target}) + "\n")
                    report.flush()
                    if counts["created"] % 250 == 0:
                        self.stdout.write(json.dumps(counts))
                        self.stdout.flush()
                    row = next(iterator, None)
                    if row is not None:
                        queue.add(executor.submit(prepare, row))
        summary = {"state": "REHEARSAL_MEDIA_ATTACHED", "database": options["database"], "counts": counts,
                   "plan_sha256": options["plan_sha256"], "production_ready": False}
        (output / "summary.json").write_text(json.dumps(summary, indent=2))
        self.stdout.write(json.dumps(summary))
