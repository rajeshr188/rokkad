"""Offline adapter for the inspected legacy custom archive; never executes SQL."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import hashlib
import io
import os
from pathlib import Path
import re
import shutil
import subprocess
from tempfile import TemporaryDirectory

from .parsers import PortabilityError

MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_EXTRACT_BYTES = 128 * 1024 * 1024
MAX_TOC_BYTES = 4 * 1024 * 1024
MAX_ROWS = 100_000
MAX_LINE_BYTES = 128 * 1024
MAX_FIELD_BYTES = 4096
EXTRACT_TIMEOUT = 60
IDENTIFIER = re.compile(r"[a-z][a-z0-9_]{0,62}\Z")
PRIMARY_KEY = re.compile(r"[1-9][0-9]{0,18}\Z")

# Exact observed column sets: changed schemas need an explicitly reviewed adapter.
COLUMNS = {
    "contact_customer": "id created updated name firstname lastname gender religion customer_type relatedas relatedto active created_by_id",
    "contact_contact": "id created contact_type phone_number last_updated customer_id is_verified is_default",
    "contact_address": "id area created doorno zipcode last_updated street city customer_id is_verified is_default",
    "girvi_license": "id name created updated type shopname address phonenumber propreitor renewal_date",
    "girvi_series": "id name created last_updated is_active license_id max_limit",
    "girvi_loan": "id created_at updated_at loan_date lid loan_id loan_type item_desc loan_amount interest created_by_id customer_id series_id interest_type tenure value weight",
    "girvi_loanitem": "id pic itemtype quantity weight purity loanamount interestrate interest itemdesc loan_id item_id",
    "girvi_loanpayment": "id created_at updated_at payment_date payment_amount principal_payment interest_payment with_release created_by_id loan_id",
    "girvi_release": "id created_at updated_at release_date release_id created_by_id loan_id released_by_id",
}
COLUMNS = {table: frozenset(fields.split()) for table, fields in COLUMNS.items()}
# Exact later shapes present in the September dump and the reviewed source commit.
# Keep absent fields absent; never default an older archive's custody claims.
COLUMN_VARIANTS = {
    "girvi_loanitem": (COLUMNS["girvi_loanitem"], COLUMNS["girvi_loanitem"] | {"is_repledged"}),
    "girvi_series": (COLUMNS["girvi_series"], COLUMNS["girvi_series"] | {"loan_type"}),
}


def source_schema(value):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value) or value == "public":
        raise PortabilityError("Select a lowercase legacy business schema; public is not supported.")
    return value


def archive_inventory(content, *, schema=None):
    if schema is not None:
        source_schema(schema)
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PortabilityError("The archive inventory must use UTF-8 identifiers.") from exc
    found = {}
    for line in text.splitlines():
        parts = line.partition(";")[2].split()
        if len(parts) < 6 or parts[2] != "TABLE" or parts[3] in {"DATA", "ATTACH"}:
            continue
        owner, table = parts[3:5]
        # An unrelated tenant's unsupported identifier cannot invalidate an
        # explicitly selected, supported tenant. Its rows are never extracted.
        if schema is not None and owner != schema:
            continue
        if not IDENTIFIER.fullmatch(owner) or not IDENTIFIER.fullmatch(table):
            raise PortabilityError("The archive contains unsupported table identifiers.")
        if table in found.setdefault(owner, set()):
            raise PortabilityError("The archive has duplicate table definitions.")
        found[owner].add(table)
    return {schema: sorted(tables) for schema, tables in sorted(found.items())
            if schema != "public" and "girvi_loan" in tables}


def _run_restore(executable, args, limit):
    # No shell, connection string, database argument, startup file, or stdin input.
    env = {key: value for key, value in os.environ.items() if not key.upper().startswith("PG")}
    try:
        process = subprocess.Popen(
            [executable, "--no-password", *args], stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except OSError as exc:
        raise PortabilityError("Could not start pg_restore; provide its installed executable path.") from exc
    with ThreadPoolExecutor(max_workers=1) as reader:
        future = reader.submit(process.stdout.read, limit + 1)
        try:
            output = future.result(timeout=EXTRACT_TIMEOUT)
            if len(output) > limit:
                raise PortabilityError("The archive extraction exceeds the preview byte limit.")
            if process.wait(timeout=5):
                raise PortabilityError("pg_restore could not read this archive. Check archive/version compatibility.")
            return output
        except (TimeoutError, subprocess.TimeoutExpired) as exc:
            raise PortabilityError("The archive extraction exceeded its time limit.") from exc
        finally:
            if process.poll() is None:
                process.kill()
            process.wait()
            # Killing the child unblocks its pipe reader before executor shutdown.
            future.result()
            process.stdout.close()


def decode_copy_field(raw):
    if raw == b"\\N":
        return None
    result = bytearray()
    escaped = {ord("b"): 8, ord("f"): 12, ord("n"): 10, ord("r"): 13,
               ord("t"): 9, ord("v"): 11, ord("\\"): 92}
    index = 0
    while index < len(raw):
        value = raw[index]
        index += 1
        if value != 92:
            result.append(value)
            continue
        if index == len(raw):
            raise PortabilityError("A COPY field has an incomplete escape.")
        value = raw[index]
        index += 1
        if value in escaped:
            result.append(escaped[value])
        elif 48 <= value <= 55:
            digits = bytes([value])
            while index < len(raw) and len(digits) < 3 and 48 <= raw[index] <= 55:
                digits += bytes([raw[index]])
                index += 1
            number = int(digits, 8)
            if number > 255:
                raise PortabilityError("A COPY field has an invalid byte escape.")
            result.append(number)
        elif value == ord("x"):
            digits = b""
            while index < len(raw) and len(digits) < 2 and raw[index] in b"0123456789abcdefABCDEF":
                digits += bytes([raw[index]])
                index += 1
            if not digits:
                raise PortabilityError("A COPY field has an invalid hex escape.")
            result.append(int(digits, 16))
        else:
            raise PortabilityError("A COPY field has an unsupported escape.")
    if len(result) > MAX_FIELD_BYTES or 0 in result:
        raise PortabilityError("A source field exceeds 4 KiB or contains NUL.")
    try:
        return result.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PortabilityError("Source values must be UTF-8.") from exc


def parse_copy(content, schema):
    source_schema(schema)
    if len(content) > MAX_EXTRACT_BYTES:
        raise PortabilityError("The archive extraction exceeds the preview byte limit.")
    result, active, count = {}, None, 0
    stream = io.BytesIO(content)
    while line := stream.readline(MAX_LINE_BYTES + 1):
        if len(line) > MAX_LINE_BYTES:
            raise PortabilityError("A source row exceeds 128 KiB.")
        line = line.rstrip(b"\r\n")
        if active is None:
            if not line.startswith(b"COPY "):
                continue  # SQL is inert text, never executed.
            match = re.fullmatch(rb'COPY ([a-z][a-z0-9_]*)\.([a-z][a-z0-9_]*) \(([^)]+)\) FROM stdin;', line)
            if not match:
                raise PortabilityError("Only supported text COPY sections can be previewed.")
            try:
                owner, table, fields = (part.decode("ascii") for part in match.groups())
            except UnicodeDecodeError as exc:
                raise PortabilityError("Source column identifiers must be ASCII.") from exc
            headers = [field.strip().strip('"') for field in fields.split(",")]
            if owner != schema or table not in COLUMNS:
                raise PortabilityError("Extraction contains records outside the selected schema/table scope.")
            if (table in result or len(headers) != len(set(headers))
                    or set(headers) not in COLUMN_VARIANTS.get(table, (COLUMNS[table],))):
                raise PortabilityError(f"Source columns or duplicate COPY sections do not match the adapter: {table}.")
            result[table] = {}
            active = table
        elif line == b"\\.":
            active = None
        else:
            values = line.split(b"\t")
            if len(values) != len(headers):
                raise PortabilityError("A source row has the wrong field count.")
            row = dict(zip(headers, map(decode_copy_field, values)))
            key = row["id"]
            if not key or not PRIMARY_KEY.fullmatch(key) or key in result[active]:
                raise PortabilityError(f"Invalid or duplicate source primary key in {active}.")
            count += 1
            if count > MAX_ROWS:
                raise PortabilityError("A source preview may contain at most 100,000 records.")
            result[active][key] = row
    if active is not None or set(result) != set(COLUMNS):
        raise PortabilityError("The extraction is incomplete or missing required source tables.")
    return result


def inspect_archive(path, *, schema=None, pg_restore="pg_restore"):
    if schema is not None:
        source_schema(schema)
    try:
        with Path(path).open("rb") as source:
            content = source.read(MAX_ARCHIVE_BYTES + 1)
    except OSError as exc:
        raise PortabilityError("Could not read the selected archive.") from exc
    if not content.startswith(b"PGDMP") or len(content) > MAX_ARCHIVE_BYTES:
        raise PortabilityError("Select a PostgreSQL custom archive of at most 64 MiB.")
    executable = shutil.which(str(pg_restore))
    if executable is None:
        raise PortabilityError("pg_restore was not found; provide --pg-restore with its installed path.")
    fingerprint = hashlib.sha256(content).hexdigest()
    # A fixed private snapshot prevents the source changing between inventory/data extraction.
    with TemporaryDirectory(prefix="rokkad-legacy-preview-") as directory:
        snapshot = Path(directory) / "source.dump"
        snapshot.write_bytes(content)
        inventory = archive_inventory(_run_restore(executable, ["--list", str(snapshot)], MAX_TOC_BYTES), schema=schema)
        if schema is None:
            return {"archive_sha256": fingerprint, "schemas": inventory}
        if schema not in inventory or not set(COLUMNS) <= set(inventory[schema]):
            raise PortabilityError("The selected schema is absent or lacks required legacy tables.")
        args = ["--data-only", "--no-owner", "--no-privileges", "--file=-", f"--schema={schema}"]
        args.extend(f"--table={table}" for table in COLUMNS)
        rows = parse_copy(_run_restore(executable, [*args, str(snapshot)], MAX_EXTRACT_BYTES), schema)
    return {"archive_sha256": fingerprint, "source_schema": schema, "schemas": inventory, "tables": rows}
