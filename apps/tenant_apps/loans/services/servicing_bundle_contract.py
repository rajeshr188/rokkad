"""Fixed source-local row and ZIP boundaries for servicing bundle versions 1–4."""
import json
import hashlib
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path, PurePosixPath
from uuid import UUID
from zipfile import ZipFile, BadZipFile
from io import BytesIO
from zlib import error as ZlibError

from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from .history_contract import HistoryError, _pairs, dump

PROFILE = "loan-servicing-bundle/1"
CORRECTION_PROFILE = "loan-servicing-bundle/2"
STORAGE_PROFILE = "loan-servicing-bundle/3"
FUNDING_PROFILE = "loan-servicing-bundle/4"
BORROWER_PROFILE = "loan-servicing-bundle/5"
COLLATERAL_PROFILE = "loan-servicing-bundle/6"
AGREEMENT_PROFILE = "loan-servicing-bundle/7"
IDENTITY_PROFILES = {BORROWER_PROFILE, COLLATERAL_PROFILE, AGREEMENT_PROFILE}
PROFILES = {PROFILE, CORRECTION_PROFILE, STORAGE_PROFILE, FUNDING_PROFILE, *IDENTITY_PROFILES}


def financial_profile(document):
    if document["profile"] not in IDENTITY_PROFILES:
        return document["profile"]
    value = document.get("financial_profile")
    require(value in PROFILES - IDENTITY_PROFILES, "Select a published underlying financial profile.")
    return value
MAX_BYTES = 32 * 1024 * 1024
MAX_ROWS = 5000
MAX_LOANS = 20
MAX_FILES = 200
BASE_ROWS = json.loads((Path(settings.BASE_DIR) / "docs/contracts/loan-servicing-bundle-v1-rows.json").read_text())
STORAGE_ROWS = json.loads((Path(settings.BASE_DIR) / "docs/contracts/loan-servicing-bundle-v3-rows.json").read_text())
ROWS = json.loads((Path(settings.BASE_DIR) / "docs/contracts/loan-servicing-bundle-v4-rows.json").read_text())
MANIFEST_FIELDS = {"profile", "namespace", "workspace_id", "root_loan_id", "as_of", "coverage", "exclusions", "tables", "setup", "positions", "files", "documents", "sha256"}
EXCLUSIONS = ["workspace_configuration", "party_master", "funding", "storage", "outbound_notification_jobs"]
STORAGE_EXCLUSIONS = ["workspace_configuration_except_referenced_storage_locations", "party_master", "funding", "outbound_notification_jobs"]
FUNDING_EXCLUSIONS = ["workspace_configuration_except_referenced_storage_and_funding_counter", "party_master", "outbound_notification_jobs"]
ISSUE_FIELDS = ('id','workspace_id','document_type','issue_kind','source_type','source_id','source_fingerprint','revision_id',
    'print_profile_revision_id','print_profile_name','print_profile_version','print_profile_hash','print_profile_source_scope',
    'fixed_renderer_version','source_snapshot','payload_schema_version','payload_hash','layout_hash','asset_hashes','pdf_hash',
    'artifact','prior_issue_id','issued_at','issued_by_id')


def require(condition, message):
    if not condition:
        raise HistoryError(message)


def sha(content):
    return hashlib.sha256(content).hexdigest()


def scalar(value, spec):
    if value is None:
        require(spec["nullable"], "A required portable value is missing.")
        return None
    require('choices' not in spec or value in spec['choices'], 'Unsupported portable enum value.')
    typ = spec["type"]
    if typ in {"BigAutoField", "AutoField", "ForeignKey", "OneToOneField", "PositiveBigIntegerField", "PositiveIntegerField", "PositiveSmallIntegerField", "IntegerField", "BigIntegerField", "SmallIntegerField"}:
        require(type(value) is int, "Portable integers must be integers.")
        require(typ not in {"ForeignKey", "OneToOneField", "BigAutoField", "AutoField"} or value > 0, "Portable references must be positive.")
        return value
    if typ == "BooleanField":
        require(type(value) is bool, "Portable booleans must be booleans.")
        return value
    if typ == "JSONField":
        require(type(value) in (dict, list), "Portable JSON must be an object or list.")
        return value
    require(type(value) is str, "Portable scalar values must be text.")
    if typ == "DecimalField":
        result = Decimal(value)
        require(result.is_finite(), "Portable amounts must be finite.")
        return result
    if typ == "UUIDField":
        return UUID(value)
    if typ == "DateField":
        result = parse_date(value)
        require(result is not None, "Invalid portable date.")
        return result
    if typ == "DateTimeField":
        result = parse_datetime(value)
        require(result is not None and timezone.is_aware(result) and result <= timezone.now(), "Portable timestamps must be known, aware and no later than now.")
        return result
    require(typ in {"CharField", "TextField", "FileField"}, "Unsupported portable wire type.")
    return value


def row(kind, obj, *, profile=None):
    result = {}
    for key, spec in ROWS[kind].items():
        value = getattr(obj, key)
        if isinstance(value, (Decimal, date, datetime, UUID)):
            value = value.isoformat() if isinstance(value, (date, datetime)) else str(value)
        if spec["type"] == "FileField":
            value = value.name
        result[key] = value
    if profile == AGREEMENT_PROFILE and kind == "PawnLoanInterestAccrual":
        result["agreement_revision"] = obj.agreement_revision
    return result


def decode(kind, value, *, profile=None):
    schema = dict(ROWS[kind])
    if profile == AGREEMENT_PROFILE and kind == "PawnLoanInterestAccrual":
        schema["agreement_revision"] = dict(type="PositiveIntegerField", nullable=False)
    require(type(value) is dict and set(value) == set(schema), "Unexpected fields in portable " + kind)
    result = {}
    for key, spec in schema.items():
        if profile == AGREEMENT_PROFILE and kind == "PawnLoanEvent" and key == "event_kind":
            spec = dict(spec, choices=[*spec["choices"], "OPENING_CORRECTION"])
        if profile == AGREEMENT_PROFILE and kind == "PawnLoanDisbursalSnapshot" and key == "basis":
            spec = dict(spec, choices=[*spec["choices"], "CORRECTED"])
        if profile in IDENTITY_PROFILES and kind == 'LoanChangeLog' and key == 'event_kind':
            spec = dict(spec, choices=[*spec['choices'], 'BORROWER_CORRECTED', *(['COLLATERAL_CORRECTED'] if profile in {COLLATERAL_PROFILE, AGREEMENT_PROFILE} else [])])
        result[key] = scalar(value[key], spec)
        if kind == "PawnLoanInterestAccrual" and key == "agreement_revision":
            require(result[key] >= 1, "Monthly agreement revision must be positive.")
    return result


def read_bundle(content):
    try:
        require(type(content) is bytes and 0 < len(content) <= MAX_BYTES, "Use a servicing bundle of at most 32 MiB.")
        with ZipFile(BytesIO(content)) as archive:
            entries = archive.infolist()
            require(len(entries) <= MAX_FILES + 1 and len({r.filename for r in entries}) == len(entries), "Duplicate or excessive bundle entries.")
            require(sum(r.file_size for r in entries) <= MAX_BYTES, "Servicing bundle exceeds its expanded size bound.")
            require(all(not r.flag_bits & 1 and not r.is_dir() and not PurePosixPath(r.filename).is_absolute() and ".." not in PurePosixPath(r.filename).parts and "\\" not in r.filename for r in entries), "Unsafe bundle paths.")
            require("manifest.json" in archive.namelist(), "Missing servicing manifest.")
            def invalid(value):
                raise HistoryError("Non-finite JSON is unsupported.")
            document = json.loads(archive.read("manifest.json"), object_pairs_hook=_pairs, parse_constant=invalid)
            require(type(document) is dict and document.get('profile') in PROFILES and set(document) ==
                (MANIFEST_FIELDS | ({'financial_profile','agreement_parties'} if document['profile'] in IDENTITY_PROFILES else set()) | ({'funding_setup','funding_positions'} if financial_profile(document)==FUNDING_PROFILE else set())), "Unsupported servicing bundle profile.")
            require(document["coverage"] == "SOURCE_FINANCIAL_AND_CUSTODY_GRAPH" and document["exclusions"] ==
                (FUNDING_EXCLUSIONS if financial_profile(document)==FUNDING_PROFILE else STORAGE_EXCLUSIONS if financial_profile(document) == STORAGE_PROFILE else EXCLUSIONS), "Portable coverage must be explicit.")
            require(document["sha256"] == sha(dump({k:v for k,v in document.items() if k != "sha256"}).encode()), "Portable manifest checksum differs.")
            UUID(document["namespace"])
            require(type(document["workspace_id"]) is int and document["workspace_id"] > 0, "Invalid source Workspace.")
            as_of = date.fromisoformat(document["as_of"])
            require(as_of <= timezone.localdate(), "Portable cutover cannot be in the future.")
            tables = document["tables"]
            require(type(tables) is dict and set(tables) == set(ROWS if financial_profile(document)==FUNDING_PROFILE else STORAGE_ROWS if financial_profile(document) == STORAGE_PROFILE else BASE_ROWS), "Portable row inventory differs.")
            require(all(type(rows) is list for rows in tables.values()), "Portable tables must be lists.")
            require(sum(len(rows) for rows in tables.values()) <= MAX_ROWS and 1 <= len(tables["PawnLoan"]) <= MAX_LOANS, "Portable graph exceeds its bounds.")
            for kind, rows in tables.items():
                require(type(rows) is list and len({r["id"] for r in rows}) == len(rows), "Duplicate portable row identity.")
                require([r["id"] for r in rows] == sorted(r["id"] for r in rows), "Portable rows must retain source recording order.")
                for source in rows:
                    decode(kind, source, profile=document['profile'])
                    if kind == "LoanChangeLog" and document["profile"] not in {COLLATERAL_PROFILE, AGREEMENT_PROFILE}:
                        require(source["event_kind"] != "COLLATERAL_CORRECTED" and "collateral_correction" not in source["metadata"],
                            "Collateral correction evidence requires servicing bundle version 6.")
                    if document["profile"] != AGREEMENT_PROFILE:
                        for field in ("payload", "metadata", "evidence"):
                            require("agreement_correction" not in source.get(field, {}),
                                "Agreement correction evidence requires servicing bundle version 7.")
                    if kind == "LoanChangeLog" and document["profile"] not in IDENTITY_PROFILES:
                        require(source["event_kind"] != "BORROWER_CORRECTED" and "borrower_correction" not in source["metadata"],
                            "Borrower correction evidence requires a profile that maps both Party identities.")
                    require(source["workspace_id"] == document["workspace_id"], "Foreign Workspace row in servicing bundle.")
            require(type(document["root_loan_id"]) is int and document["root_loan_id"] in {r["id"] for r in tables["PawnLoan"]}, "Missing root loan.")
            require(type(document["setup"]) is dict and type(document["positions"]) is dict and type(document["documents"]) is list, "Invalid portable setup/position/document inventory.")
            require(type(document["files"]) is dict and set(archive.namelist()) == {"manifest.json"} | {"files/" + key for key in document["files"]}, "Portable file inventory differs.")
            files = {}
            source_names = set()
            for key, facts in document["files"].items():
                require(type(key) is str and len(key) == 64 and key == facts["sha256"] and set(facts) == {"sha256", "size", "source_names"}, "Invalid portable file claim.")
                require(type(facts['size']) is int and type(facts['source_names']) is list and facts['source_names'] and all(type(n) is str and n for n in facts['source_names']), "Invalid file size/source names.")
                require(len(set(facts['source_names'])) == len(facts['source_names']) and not source_names.intersection(facts['source_names']), 'Ambiguous portable file names.')
                source_names.update(facts['source_names'])
                data = archive.read("files/" + key)
                require(sha(data) == key and len(data) == facts["size"], "Portable file bytes differ.")
                files[key] = data
            return document, files
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError, InvalidOperation, RecursionError, BadZipFile, UnicodeError, RuntimeError, ZlibError) as exc:
        if isinstance(exc, HistoryError):
            raise
        raise HistoryError("Invalid bounded servicing bundle: " + str(exc)) from exc
