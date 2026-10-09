"""Versioned closed-position download with unchanged source documents and media."""
import hashlib
import json
from copy import deepcopy
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED, BadZipFile
from zlib import error as ZlibError

from django.core import signing
from django.core.files.base import ContentFile
from django.db import transaction

from apps.orgs.access import resolve_workspace_access
from apps.orgs.audit import AuditLog
from apps.tenant_apps.loans import models as m
from .closed_position import read_position, preview_closed_position, admit_closed_position
from .closed_position_contract import encode, parse
from .history_contract import digest, dump, HistoryError, _pairs
from .history_setup import require_history_setup_access

PROFILE = "loan-closed-position-bundle/1"
MAX_BYTES = 32 * 1024 * 1024
MAX_FILES = 100
SALT = "loans.closed-position.bundle.v1"
MEDIA_TYPES = {"image/jpeg", "image/png", "image/webp", "application/pdf", "application/octet-stream"}


def _sha(content):
    return hashlib.sha256(content).hexdigest()


@transaction.atomic
def export_closed_position(*, workspace_id, actor, loan_id):
    workspace = require_history_setup_access(workspace_id, actor, read_only=True)
    resolve_workspace_access(actor=actor, workspace=workspace).require("data.export")
    loan = m.PawnLoan.objects.select_for_update().get(workspace_id=workspace_id, pk=loan_id)
    document = deepcopy(read_position(loan))
    archive = loan.historical_import.archive_evidence
    media = list(archive.attachments.filter(workspace_id=workspace_id).order_by("pk")) if archive else []
    if len(media) > MAX_FILES:
        raise HistoryError("Closed-position media exceeds one hundred files.")
    files, claims = {}, []
    for attachment in media:
        if attachment.mime_type not in MEDIA_TYPES:
            raise HistoryError("Unsupported portable historical attachment type.")
        try:
            with attachment.file.open("rb") as stream:
                content = stream.read(MAX_BYTES + 1)
        except OSError as exc:
            raise HistoryError("Retained source media is unavailable; export cannot omit it.") from exc
        if _sha(content) != attachment.sha256 or len(content) != attachment.byte_size:
            raise HistoryError("Retained source media is missing or corrupt.")
        files[attachment.sha256] = content
        if sum(map(len, files.values())) > MAX_BYTES:
            raise HistoryError("Closed-position media exceeds 32 MiB.")
        claims.append(dict(sha256=attachment.sha256, size=attachment.byte_size,
            name=attachment.original_filename, mime_type=attachment.mime_type, source_evidence=attachment.source_evidence))
    if media:
        manifest = dict(profile=PROFILE, position_sha256=digest(document), media=claims,
            earlier_history="UNAVAILABLE", financial_actions=[])
        if sum(map(len, files.values())) + len(encode(document)) + len(dump(manifest).encode()) > MAX_BYTES:
            raise HistoryError("Closed-position file evidence exceeds 32 MiB.")
        stream = BytesIO()
        with ZipFile(stream, "w", ZIP_DEFLATED) as archive_file:
            archive_file.writestr("position.json", encode(document))
            archive_file.writestr("manifest.json", dump(manifest))
            for checksum, content in files.items():
                archive_file.writestr("media/" + checksum, content)
        content, filename = stream.getvalue(), "loan-closed-position-v1.zip"
    else:
        content, filename = encode(document), "loan-closed-position-v1.json"
    if len(content) > MAX_BYTES:
        raise HistoryError("Closed-position export exceeds 32 MiB.")
    AuditLog.log("DATA_EXPORT", company=workspace, user=actor,
        description="Exported accepted closed position and retained source evidence; earlier financial history unavailable.",
        data=dict(loan=loan.pk, profile=PROFILE if media else document["profile"], sha256=_sha(content)))
    return content, filename


def parse_closed_position_file(content):
    if type(content) is not bytes or not 0 < len(content) <= MAX_BYTES:
        raise HistoryError("Upload one closed-position file of at most 32 MiB.")
    if not content.startswith(b"PK"):
        return parse(content), [], {}
    try:
        with ZipFile(BytesIO(content)) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)) or len(names) > MAX_FILES + 2 or sum(row.file_size for row in archive.infolist()) > MAX_BYTES:
                raise HistoryError("Duplicate files or excessive closed-position bundle size.")
            document = parse(archive.read("position.json"))
            manifest = json.loads(archive.read("manifest.json"), object_pairs_hook=_pairs)
            if (type(manifest) is not dict or set(manifest) != {"profile", "position_sha256", "media", "earlier_history", "financial_actions"}
                or manifest["profile"] != PROFILE or manifest["position_sha256"] != digest(document)
                or manifest["earlier_history"] != "UNAVAILABLE" or manifest["financial_actions"] != []
                or type(manifest["media"]) is not list or len(manifest["media"]) > MAX_FILES
                or (manifest["media"] and document["retained_evidence"] is None)):
                raise HistoryError("Unsupported or inconsistent closed-position bundle.")
            files, claims = {}, manifest["media"]
            for claim in claims:
                if (type(claim) is not dict or set(claim) != {"sha256", "size", "name", "mime_type", "source_evidence"}
                    or type(claim["sha256"]) is not str or len(claim["sha256"]) != 64
                    or any(c not in "0123456789abcdef" for c in claim["sha256"])
                    or type(claim["size"]) is not int or claim["size"] <= 0
                    or type(claim["name"]) is not str or not 0 < len(claim["name"]) <= 255
                    or type(claim["mime_type"]) is not str or claim["mime_type"] not in MEDIA_TYPES
                    or any(ord(c) < 32 or ord(c) == 127 for c in claim["name"])
                    or type(claim["source_evidence"]) is not dict
                    or type(claim["source_evidence"].get("verified_source_file")) is not dict
                    or claim["source_evidence"]["verified_source_file"].get("sha256") != claim["sha256"]):
                    raise HistoryError("Invalid retained media claim.")
                value = archive.read("media/" + claim["sha256"])
                if len(value) != claim["size"] or _sha(value) != claim["sha256"]:
                    raise HistoryError("Retained media content differs from its checksum.")
                files[claim["sha256"]] = value
            if set(names) != {"position.json", "manifest.json", *("media/" + checksum for checksum in files)}:
                raise HistoryError("Unexpected bundle entries; arbitrary paths are not accepted.")
            return document, claims, files
    except (BadZipFile, KeyError, UnicodeError, ValueError, RuntimeError, TypeError, RecursionError, NotImplementedError, ZlibError) as exc:
        if isinstance(exc, HistoryError):
            raise
        raise HistoryError("Invalid closed-position file.") from exc


def preview_closed_position_file(*, content, **mapping):
    document, claims, _ = parse_closed_position_file(content)
    summary, review = preview_closed_position(document=document, **mapping)
    summary["retained_files"] = len(claims)
    return summary, signing.dumps(dict(sha256=_sha(content), review=review), salt=SALT, compress=True)


def admit_closed_position_file(*, content, review_token, confirmed=False, **mapping):
    saved_files = []
    try:
        with transaction.atomic():
            return _admit_closed_position_file(content=content, review_token=review_token, confirmed=confirmed,
                saved_files=saved_files, **mapping)
    except Exception:
        for storage, name in saved_files:
            storage.delete(name)
        raise


def _admit_closed_position_file(*, content, review_token, confirmed, saved_files, **mapping):
    document, claims, files = parse_closed_position_file(content)
    try:
        approved = signing.loads(review_token or "", salt=SALT, max_age=3600)
    except (signing.BadSignature, TypeError, ValueError):
        raise HistoryError("Review this closed-position file again.") from None
    if approved.get("sha256") != _sha(content):
        raise HistoryError("Uploaded file changed after review.")
    loan, created = admit_closed_position(document=document, review_token=approved.get("review"), confirmed=confirmed, **mapping)
    archive = loan.historical_import.archive_evidence
    for claim in claims:
        existing = m.HistoricalLoanAttachment.objects.filter(workspace_id=loan.workspace_id, evidence=archive,
            sha256=claim["sha256"], original_filename=claim["name"], source_evidence=claim["source_evidence"]).first()
        if existing:
            if existing.byte_size != claim["size"] or existing.mime_type != claim["mime_type"]:
                raise HistoryError("Retained media metadata conflicts with its previous admission.")
            continue
        attachment = m.HistoricalLoanAttachment(workspace_id=loan.workspace_id, evidence=archive,
            sha256=claim["sha256"], byte_size=claim["size"], original_filename=claim["name"],
            mime_type=claim["mime_type"], source_evidence=claim["source_evidence"], imported_by=mapping["actor"])
        attachment.file.save(f"closed-position/{loan.workspace_id}/{archive.public_id}/{claim['sha256']}",
            ContentFile(files[claim["sha256"]]), save=False)
        saved_files.append((attachment.file.storage, attachment.file.name))
        attachment.save()
    return loan, created
