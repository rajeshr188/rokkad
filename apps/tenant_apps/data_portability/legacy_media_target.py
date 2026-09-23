"""Explicit non-secret binding for production legacy-media admission."""
import hashlib
import ipaddress
import json
import re
from pathlib import Path
from uuid import UUID

from django.core.management.base import CommandError

PROFILE = "linode-media-target/1"
PLAN_PROFILE = "linode-media-plan/2"


def require(condition, message):
    if not condition:
        raise CommandError(message)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON property in reviewed media input.")
        result[key] = value
    return result


def workspace_mapping(value):
    try:
        result = json.loads(value, object_pairs_hook=unique_object)
    except (TypeError, ValueError) as exc:
        raise CommandError("Use a JSON source-schema to Workspace-ID mapping.") from exc
    require(type(result) is dict and 1 <= len(result) <= 100, "Select a nonempty bounded Workspace mapping.")
    require(all(type(k) is str and re.fullmatch(r"[a-z][a-z0-9_]{0,62}", k) and k != "public" and
                type(v) is int and v > 0 for k, v in result.items()), "Invalid source schema or Workspace ID.")
    require(len(set(result.values())) == len(result), "Each source branch must have a distinct Workspace.")
    return result


def load_target(path, expected_sha256):
    try:
        with Path(path).open("rb") as source:
            raw = source.read(65537)
        require(0 < len(raw) <= 65536, "Target manifest must be at most 64 KiB.")
        require(hashlib.sha256(raw).hexdigest() == expected_sha256, "Target manifest checksum differs from the reviewed target.")
        target = json.loads(raw, object_pairs_hook=unique_object)
        require(type(target) is dict and set(target) == {"profile", "database", "storage", "source", "workspaces"} and
                target["profile"] == PROFILE, "Use the supported media target manifest.")
        db, storage, source, branches = (target[k] for k in ("database", "storage", "source", "workspaces"))
        require(type(db) is dict and set(db) == {"name", "host", "port", "user", "server_address", "server_port"},
                "Target database requires its exact connection and server identity.")
        require(all(type(db[k]) is str and db[k] and db[k] == db[k].strip() and len(db[k]) <= 255 and
                    not any(ord(c) < 32 for c in db[k]) for k in ("name", "host", "user", "server_address")),
                "Target database identity must contain nonempty explicit values.")
        ipaddress.ip_address(db["server_address"])
        require(all(type(db[k]) is int and 1 <= db[k] <= 65535 for k in ("port", "server_port")), "Invalid target database port.")
        require(not db["name"].startswith("rokkad_baseline_rehearsal_"), "Production target cannot select a rehearsal database.")
        require(type(storage) is dict and set(storage) == {"endpoint", "bucket", "location"}, "Use an exact R2 storage binding.")
        require(type(storage["endpoint"]) is str and re.fullmatch(r"https://[a-f0-9]{32}\.r2\.cloudflarestorage\.com", storage["endpoint"]),
                "Target storage requires the HTTPS R2 account endpoint.")
        require(type(storage["bucket"]) is str and re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", storage["bucket"]), "Invalid target bucket.")
        require(type(storage["location"]) is str and re.fullmatch(r"media/application/production/[a-z0-9][a-z0-9_-]{0,62}", storage["location"]),
                "Select a dedicated production application prefix.")
        require(type(source) is dict and set(source) == {"namespace", "archive_sha256"} and
                str(UUID(source["namespace"])) == source["namespace"] and
                type(source["archive_sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", source["archive_sha256"]),
                "Use the exact source installation UUID and archive checksum.")
        require(type(branches) is dict, "Target workspaces must be an explicit map.")
        require(all(type(v) is dict and set(v) == {"id", "slug"} and type(v["slug"]) is str and
                    re.fullmatch(r"[a-z0-9_-]{1,63}", v["slug"]) for v in branches.values()), "Bind each Workspace by ID and slug.")
        workspace_mapping(json.dumps({k: v["id"] for k, v in branches.items()}))
        require(len({v["slug"] for v in branches.values()}) == len(branches), "Workspace slugs must be distinct.")
        return target
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        raise CommandError("Invalid or unreadable media target manifest.") from exc


def check_storage(target, storage):
    try:
        actual = {"endpoint": storage.endpoint_url, "bucket": storage.bucket_name, "location": storage.location}
        require(actual == target["storage"], "Configured media storage differs from the reviewed target.")
        require(storage.default_acl in (None, "private") and not storage.custom_domain and storage.querystring_auth is True and
                storage.use_ssl is True and storage.verify is not False and storage.file_overwrite is False and
                storage.object_parameters.get("ACL") in (None, "private"),
                "Production media admission requires private storage and verified TLS.")
    except AttributeError as exc:
        raise CommandError("Configure the production private R2 storage backend.") from exc


def check_target(target, *, connection, database, workspaces, storage):
    db = target["database"]
    actual = connection.settings_dict
    require(db["name"] == database == actual["NAME"] and db["host"] == actual.get("HOST") and
            str(db["port"]) == str(actual.get("PORT") or 5432) and db["user"] == actual.get("USER"),
            "Database connection differs from the reviewed media target.")
    require({k: v["id"] for k, v in target["workspaces"].items()} == workspaces,
            "Workspace mapping differs from the reviewed media target.")
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database(), current_user, host(inet_server_addr()), inet_server_port()")
        identity = cursor.fetchone()
    require(tuple(identity) == (db["name"], db["user"], db["server_address"], db["server_port"]),
            "Connected database server or role differs from the reviewed media target.")
    check_storage(target, storage)


def check_source(target, evidence):
    require(evidence.get("namespace") == target["source"]["namespace"] and
            evidence.get("archive_sha256") == target["source"]["archive_sha256"],
            "Media source differs from the reviewed installation or snapshot.")
    require(evidence.get("verified_source_file", {}).get("bucket") == target["storage"]["bucket"],
            "Preserved media bucket differs from the reviewed target.")
