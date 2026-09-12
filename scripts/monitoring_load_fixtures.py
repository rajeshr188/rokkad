"""SQL copies of synthetic read evidence, confined to the monitoring load database.

Preserves the existing benchmark's relational/JSON identity remapping. Copies
are not valid servicing/audit fixtures; only command-created seed loans are
serviced by the load driver. No triggers or RLS policies are disabled.
"""
import json

from django.db import connection, transaction
from benchmark_monitoring import JSON_IDENTITIES


def _identity(mapping, key):
    start, stride = mapping[key]
    return f"({start} + (g.i - 1) * {stride})"


def _json(value, mapping):
    if isinstance(value, dict):
        parts, params = [], []
        for key, item in value.items():
            model = JSON_IDENTITIES.get(key)
            if model and isinstance(item, int) and (model, item) in mapping:
                expression, arguments = f"to_jsonb({_identity(mapping, (model, item))})", []
            else:
                expression, arguments = _json(item, mapping)
            parts.append(f"%s::text, {expression}")
            params.extend([key, *arguments])
        return "jsonb_build_object(" + ", ".join(parts) + ")", params
    if isinstance(value, list):
        parts, params = [], []
        for item in value:
            expression, arguments = _json(item, mapping)
            parts.append(expression)
            params.extend(arguments)
        return "jsonb_build_array(" + ", ".join(parts) + ")", params
    return "%s::jsonb", [json.dumps(value)]


@transaction.atomic
def copy_load_loans(templates, count):
    if connection.settings_dict["NAME"] != "test_rokkad_monitoring_load":
        raise RuntimeError("Synthetic copies require the dedicated load-test database.")
    if count < 0:
        raise ValueError("Negative copy count")
    if not count:
        return
    mapping = {}
    with connection.cursor() as cursor:
        # Only ID reservation is serialized. Independent Workspace inserts can
        # proceed in parallel without interleaving the reserved sequence ranges.
        cursor.execute("SELECT pg_advisory_lock(hashtext('monitoring-fixture-sequences'))")
        try:
            for model, rows in templates:
                if not rows:
                    continue
                cursor.execute("SELECT min(id), max(id) FROM (SELECT nextval(pg_get_serial_sequence(%s, 'id')) AS id FROM generate_series(1, %s)) ids",
                               [model._meta.db_table, count * len(rows)])
                first, last = cursor.fetchone()
                if last - first + 1 != count * len(rows):
                    raise RuntimeError("Fixture sequence allocation overlapped another writer.")
                for offset, row in enumerate(rows):
                    mapping[(model.__name__, row.pk)] = (first + offset, len(rows))
        finally:
            cursor.execute("SELECT pg_advisory_unlock(hashtext('monitoring-fixture-sequences'))")
        for model, rows in templates:
            fields = model._meta.concrete_fields
            columns = ", ".join(connection.ops.quote_name(field.column) for field in fields)
            table = connection.ops.quote_name(model._meta.db_table)
            for row in rows:
                expressions, params = [], []
                for field in fields:
                    value = getattr(row, field.attname)
                    if field.primary_key:
                        expression = _identity(mapping, (model.__name__, row.pk))
                    elif field.is_relation and (field.related_model.__name__, value) in mapping:
                        expression = _identity(mapping, (field.related_model.__name__, value))
                    elif field.get_internal_type() == "JSONField":
                        expression, arguments = _json(value, mapping)
                        params.extend(arguments)
                    elif field.name == "public_id":
                        expression = "gen_random_uuid()"
                    elif field.name in ("loan_number", "idempotency_key", "release_number"):
                        expression = "'load-' || gen_random_uuid()::text"
                    else:
                        expression = f"%s::{field.db_type(connection)}"
                        params.append(field.get_db_prep_save(value, connection))
                    expressions.append(expression)
                cursor.execute(f"INSERT INTO {table} ({columns}) SELECT {', '.join(expressions)} FROM generate_series(1, %s) g(i)", [*params, count])
