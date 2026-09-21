"""Parsing preserves source values. No filesystem extraction or format guessing."""
import csv
import io
import json
from pathlib import PureWindowsPath

MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 1000
MAX_COLUMNS = 40
MAX_CELL = 4096


class PortabilityError(ValueError):
    """A safe operator-facing error; never wrap arbitrary exception text."""


def json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise PortabilityError("Duplicate JSON fields are not supported.")
        result[key] = value
    return result


def decode_json(value):
    try:
        return json.loads(value, object_pairs_hook=json_object,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, RecursionError, TypeError) as exc:
        raise PortabilityError("Invalid JSON data.") from exc


def parse_source(content, filename):
    if not isinstance(content, bytes) or not content or len(content) > MAX_BYTES:
        raise PortabilityError("Upload a nonempty file of at most 5 MiB.")
    name = PureWindowsPath(str(filename)).name
    if not name or len(name) > 255 or any(ord(c) < 32 for c in name):
        raise PortabilityError("Invalid source filename.")
    suffix = PureWindowsPath(name).suffix.lower()
    if suffix == ".xlsx":
        from .xlsx import parse_xlsx
        headers, rows = parse_xlsx(content)
        return name, "xlsx", headers, rows
    if suffix not in {".csv", ".jsonl"}:
        raise PortabilityError("Only CSV, XLSX and canonical JSONL files are supported.")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise PortabilityError("The source must be UTF-8 text.") from exc
    if "\x00" in text:
        raise PortabilityError("NUL characters are not supported.")
    rows = []
    if suffix == ".csv":
        reader = csv.reader(io.StringIO(text, newline=""), strict=True)
        try:
            headers = next(reader)
            if not headers or len(headers) > MAX_COLUMNS or len(set(headers)) != len(headers):
                raise PortabilityError("Use 1–40 unique, nonempty column headers.")
            if any(not h.strip() or len(h) > 255 for h in headers):
                raise PortabilityError("Invalid column header.")
            while True:
                start = reader.line_num + 1
                values = next(reader, None)
                if values is None:
                    break
                if not values:
                    continue
                if len(values) != len(headers):
                    raise PortabilityError(f"Row {start} has a different column count.")
                rows.append((start, dict(zip(headers, values))))
                _check_limits(rows)
        except (csv.Error, StopIteration) as exc:
            raise PortabilityError("Malformed CSV file.") from exc
    else:
        headers = []
        for number, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            if len(line) > 64 * 1024:
                raise PortabilityError("A JSONL row exceeds 64 KiB.")
            value = decode_json(line)
            if not isinstance(value, dict) or len(value) > MAX_COLUMNS:
                raise PortabilityError("Each JSONL row must be one bounded object.")
            rows.append((number, value))
            _check_limits(rows)
    if not rows:
        raise PortabilityError("The file contains no records.")
    return name, suffix[1:], headers, rows


def _check_limits(rows):
    if len(rows) > MAX_ROWS:
        raise PortabilityError("A batch may contain at most 1,000 rows.")
    if any(len(json.dumps(v, ensure_ascii=False)) > MAX_CELL for v in rows[-1][1].values()):
        raise PortabilityError("A field exceeds 4,096 characters.")
