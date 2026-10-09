"""Reviewed retained-source batches; each apply call is one bounded transaction."""
from copy import deepcopy
from itertools import islice

from django.core import signing
from django.db import transaction
from django.utils import timezone

from apps.orgs.audit import AuditLog
from apps.tenancy.context import workspace_context
from . import closed_position as admission
from .archive import get_evidence
from .history_contract import digest
from .history_setup import require_history_setup_access
from .recorded_numbers import LockedNumberClaims, claim_number, identity

PROFILE = "loan-closed-position-batch/1"
SALT = "loans.closed-position.batch.review.v1"
MAX_CHUNK = 100
MAX_ENTRIES = 50000


def review_closed_position_batch(*, workspace_id, actor, candidates):
    """Review exact supplied positions/mappings, not inferred borrower names.

    candidates is an iterable of document/borrower_id/series_id/evidence_id.
    Review reserves no number. Current authority, snapshots and collisions are
    checked again at commit; a signature never bypasses those checks.
    """
    manifest = dict(profile=PROFILE, workspace_id=workspace_id, actor_id=actor.pk,
        reviewed_on=timezone.localdate().isoformat(), entries=[])
    sources, numbers = set(), set()
    iterator = iter(candidates)
    while chunk := list(islice(iterator, MAX_CHUNK)):
        with workspace_context(workspace_id), transaction.atomic():
            require_history_setup_access(workspace_id, actor)
            claims = LockedNumberClaims(workspace_id)
            for candidate in chunk:
                if len(manifest["entries"]) >= MAX_ENTRIES:
                    raise ValueError("Split this review into bounded manifests.")
                if not candidate.get("evidence_id"):
                    raise ValueError("Batch conversion requires an existing exact retained source.")
                workspace, series, accepted = admission._prepare(workspace_id, actor,
                    candidate["document"], candidate["borrower_id"], candidate["series_id"], candidate["evidence_id"])
                if candidate.get("expected_sha256") and digest(accepted) != candidate["expected_sha256"]:
                    raise ValueError("The earlier reviewed source or mapping changed. Do not refresh its approval.")
                position = accepted["position"]
                source = position["source"]
                key = (source["namespace"], admission.position_source_id(source))
                number = identity(position["loan"]["number"])
                if key in sources or number in numbers:
                    raise ValueError("Duplicate source or loan number in the reviewed batch.")
                sources.add(key); numbers.add(number)
                # The review simulates ordinary range/counter rules, then rolls
                # back. Admission also verifies existing provenance for retries.
                from apps.tenant_apps.loans import models as m
                origin = m.HistoricalLoanImport.objects.filter(workspace_id=workspace_id,
                    source_namespace=source["namespace"], source_id=key[1]).first()
                if origin:
                    if origin.document != accepted or origin.source_sha256 != digest(accepted):
                        raise ValueError("An existing origin differs from this reviewed position.")
                    admission.read_position(origin.loan)
                else:
                    claim_number(series, position["loan"]["number"], kind="PAWN_LOAN", actor=actor,
                        archive_ids=[r[0] for r in accepted["archive"]["snapshots"]], _claims=claims)
                portable = deepcopy(position)
                portable["retained_evidence"] = None
                manifest["entries"].append(dict(evidence_id=str(candidate["evidence_id"]),
                    borrower_id=candidate["borrower_id"], series_id=candidate["series_id"],
                    position=portable, accepted_sha256=digest(accepted)))
            transaction.set_rollback(True)
    if not manifest["entries"]:
        raise ValueError("There are no eligible positions to review.")
    token = signing.dumps(dict(workspace=workspace_id, actor=actor.pk, sha256=digest(manifest),
        date=manifest["reviewed_on"]), salt=SALT)
    return manifest, token


def apply_closed_position_batch(*, workspace_id, actor, manifest, review_token,
        start=0, limit=50, confirmed=False):
    if confirmed is not True:
        raise ValueError("Confirm the exact reviewed batch before recording positions.")
    if (type(start) is not int or type(limit) is not int or start < 0 or not 1 <= limit <= MAX_CHUNK
            or type(manifest) is not dict or set(manifest) != {"profile", "workspace_id", "actor_id", "reviewed_on", "entries"}
            or manifest["profile"] != PROFILE or type(manifest["entries"]) is not list
            or not 1 <= len(manifest["entries"]) <= MAX_ENTRIES or start >= len(manifest["entries"])):
        raise ValueError("Invalid manifest or bounded batch range.")
    expected = dict(workspace=workspace_id, actor=actor.pk, sha256=digest(manifest),
        date=timezone.localdate().isoformat())
    try:
        approved = signing.loads(review_token or "", salt=SALT, max_age=86400)
    except (signing.BadSignature, TypeError, ValueError):
        raise ValueError("Review the batch again; approval is missing or expired.") from None
    if (approved != expected or manifest["workspace_id"] != workspace_id
            or manifest["actor_id"] != actor.pk or manifest["reviewed_on"] != expected["date"]):
        raise ValueError("Batch, Workspace, operator or review day changed. Review again.")
    created = skipped = 0
    with workspace_context(workspace_id):
        require_history_setup_access(workspace_id, actor)
        claims = LockedNumberClaims(workspace_id)
        for entry in manifest["entries"][start:start + limit]:
            if type(entry) is not dict or set(entry) != {"evidence_id", "borrower_id", "series_id", "position", "accepted_sha256"}:
                raise ValueError("Unsupported reviewed batch entry.")
            evidence = get_evidence(workspace_id=workspace_id, actor=actor, evidence_id=entry["evidence_id"])
            document = deepcopy(entry["position"])
            document["retained_evidence"] = evidence.document
            workspace, series, accepted = admission._prepare(workspace_id, actor, document,
                entry["borrower_id"], entry["series_id"], entry["evidence_id"])
            if digest(accepted) != entry["accepted_sha256"]:
                raise ValueError("Source snapshots or mappings changed since review. Stop and review again.")
            _, added = admission._write(workspace, series, actor, accepted, _number_claims=claims)
            created += int(added); skipped += int(not added)
        result = dict(profile=PROFILE, sha256=expected["sha256"], start=start,
            next_start=min(start + limit, len(manifest["entries"])), total=len(manifest["entries"]),
            created=created, already_admitted=skipped)
        AuditLog.log("DATA_IMPORT", company=workspace, user=actor,
            description="Recorded reviewed closed-position batch; original source evidence retained.", data=result)
    return result
