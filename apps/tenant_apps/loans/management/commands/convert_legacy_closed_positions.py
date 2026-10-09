"""Explicit review/apply operator entry point for retained legacy closed positions."""
import json
import re
from pathlib import Path
from uuid import UUID, uuid5

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.utils import timezone

from apps.tenancy.context import workspace_context
from apps.tenant_apps.data_portability.children import parent_for
from apps.tenant_apps.data_portability.legacy_closed_positions import (
    SOURCE_NAMESPACE, RELEASE_MEANING_REFERENCE, classify_closed_position,
)
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.services.closed_position_batch import review_closed_position_batch, apply_closed_position_batch, MAX_CHUNK
from apps.tenant_apps.loans.services.history_contract import digest
from apps.tenant_apps.loans.services.history_setup import require_history_setup_access
from apps.tenant_apps.loans.services.archive import get_evidence


def unchanged_manifest_candidates(workspace_id, actor, manifest):
    if manifest.get("workspace_id") != workspace_id or manifest.get("actor_id") != actor.pk:
        raise ValueError("An earlier review belongs to another Workspace or operator.")
    for entry in manifest["entries"]:
        with workspace_context(workspace_id):
            require_history_setup_access(workspace_id, actor)
            source = get_evidence(workspace_id=workspace_id, actor=actor, evidence_id=entry["evidence_id"])
            document = {**entry["position"], "retained_evidence": source.document}
        yield dict(document=document, borrower_id=entry["borrower_id"], series_id=entry["series_id"],
            evidence_id=entry["evidence_id"], expected_sha256=entry["accepted_sha256"])


def load_owner_return_cohort(path):
    if not path:
        return None
    cohort = json.loads(Path(path).read_text(encoding="utf8"))
    if (type(cohort) is not dict or len(cohort) != 190
            or any(not re.fullmatch(r"jcl:girvi_loan:[0-9]+", key)
                or not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)
                for key, value in cohort.items())):
        raise ValueError("The temporary JCL attestation must be the exact frozen 190 source identities/hashes.")
    return cohort


def legacy_candidates(workspace_id, actor, cohort, exceptions):
    # Fetch ids only; prepare each source graph under its own short read context.
    with workspace_context(workspace_id):
        require_history_setup_access(workspace_id, actor)
        ids = list(m.HistoricalLoanEvidence.objects.filter(workspace_id=workspace_id,
            source_namespace=SOURCE_NAMESPACE).order_by("pk").values_list("pk", flat=True))
    for pk in ids:
        with workspace_context(workspace_id):
            require_history_setup_access(workspace_id, actor)
            evidence = m.HistoricalLoanEvidence.objects.get(workspace_id=workspace_id, pk=pk)
            if digest(evidence.document) != evidence.source_sha256:
                raise ValueError("Retained source fingerprint differs. Stop before review.")
            result = classify_closed_position(evidence.document, as_of=timezone.localdate(),
                release_meaning_reference=RELEASE_MEANING_REFERENCE, owner_return_cohort=cohort)
            if result["status"] != "CANDIDATE":
                exceptions.append(dict(evidence_id=str(evidence.public_id), sha256=evidence.source_sha256, reason=result["reason"]))
                continue
            doc = result["document"]
            source, reference = doc["source"], doc["loan"]["borrower_reference"]
            schema = source["system"].rsplit(":", 1)[-1]
            refs = [reference["id"], str(uuid5(uuid5(UUID(source["namespace"]), schema), reference["id"]))]
            parties = [parent_for(dict(party_source_system=reference["system"], party_external_id=ref), workspace_id) for ref in refs]
            parties = {p.party_id for p in parties if p}
            if len(parties) != 1:
                raise ValueError("Missing or contradictory exact Party mappings. Stop before review.")
            raw = [r for r in evidence.document["source_records"] if isinstance(r.get("source"), dict)
                and r["source"].get("source_system") == source["system"]
                and r["source"].get("table") == "girvi_loan" and r["source"].get("external_id") == source["loan_id"]]
            code = f"LINODE-{raw[0]['facts'].get('series_id')}"
            series = m.LoanSeries.objects.get(workspace_id=workspace_id, code=code)
            candidate = dict(document=doc, borrower_id=parties.pop(), series_id=series.pk, evidence_id=str(evidence.public_id))
        yield candidate


class Command(BaseCommand):
    help = "Review retained legacy closed positions, then apply the exact signed manifest in bounded resumable chunks."

    def add_arguments(self, parser):
        parser.add_argument("--workspace-id", type=int, required=True)
        parser.add_argument("--actor-id", type=int, required=True)
        parser.add_argument("--manifest", required=True)
        parser.add_argument("--review-token-file", required=True)
        parser.add_argument("--owner-return-cohort", help="Temporary frozen JCL 190-record identity/hash manifest, never a general import rule.")
        parser.add_argument("--refresh-manifest", help="Recheck an expired manifest into new review files, preserving its positions and hashes.")
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--confirmed", action="store_true")
        parser.add_argument("--start", type=int, default=0)
        parser.add_argument("--batch-size", type=int, default=50)

    def handle(self, *args, **options):
        try:
            if connection.in_atomic_block:
                raise ValueError("Run outside an outer transaction so each bounded chunk commits independently.")
            if not 1 <= options["batch_size"] <= MAX_CHUNK:
                raise ValueError("Batch size must be between 1 and 100.")
            actor = get_user_model().objects.get(pk=options["actor_id"])
            path = Path(options["manifest"]); token_path = Path(options["review_token_file"])
            wid = options["workspace_id"]
            if options["apply"]:
                manifest = json.loads(path.read_text(encoding="utf8"))
                token = token_path.read_text(encoding="utf8").strip()
                start = options["start"]
                if not 0 <= start < len(manifest["entries"]):
                    raise ValueError("Start must identify an entry in the reviewed manifest.")
                while start < len(manifest["entries"]):
                    result = apply_closed_position_batch(workspace_id=wid, actor=actor, manifest=manifest,
                        review_token=token, start=start, limit=options["batch_size"], confirmed=options["confirmed"])
                    self.stdout.write(json.dumps(result, sort_keys=True)); self.stdout.flush()
                    start = result["next_start"]
            else:
                if any(p.exists() for p in (path, token_path, path.with_suffix(path.suffix + ".exceptions"))):
                    raise ValueError("Review files already exist. Use new paths; do not replace accepted review evidence.")
                exceptions = []
                cohort = load_owner_return_cohort(options["owner_return_cohort"])
                candidates = (unchanged_manifest_candidates(wid, actor,
                    json.loads(Path(options["refresh_manifest"]).read_text(encoding="utf8"))) if options["refresh_manifest"]
                    else legacy_candidates(wid, actor, cohort, exceptions))
                manifest, token = review_closed_position_batch(workspace_id=wid, actor=actor,
                    candidates=candidates)
                # Operator review files are private and create-only. Exception
                # records remain retained and are never silently converted.
                for target, content in ((path, json.dumps(manifest)), (token_path, token),
                        (path.with_suffix(path.suffix + ".exceptions"), json.dumps(exceptions))):
                    with target.open("x", encoding="utf8") as stream:
                        target.chmod(0o600); stream.write(content)
                self.stdout.write(json.dumps(dict(reviewed=len(manifest["entries"]), held=len(exceptions),
                    sha256=digest(manifest), owner_return_cohort_sha256=digest(cohort) if cohort else None)))
        except (ValueError, KeyError, OSError, PermissionDenied, ValidationError, get_user_model().DoesNotExist,
                m.LoanSeries.DoesNotExist, m.LoanSeries.MultipleObjectsReturned) as exc:
            raise CommandError(str(exc)) from exc
