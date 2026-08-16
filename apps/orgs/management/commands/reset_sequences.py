"""
reset_sequences — reset all PostgreSQL sequences to max(id)+1 after loading
a production dump into a fresh database.

Usage:
    python manage.py reset_sequences            # public schema only
    python manage.py reset_sequences --all      # public + all tenant schemas
    python manage.py reset_sequences --schema jcl --schema jsk  # specific schemas
"""
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Reset PostgreSQL sequences to max(id) after loading a production dump."

    def add_arguments(self, parser):
        parser.add_argument(
            "--all",
            action="store_true",
            dest="all_schemas",
            help="Reset sequences in all tenant schemas (plus public).",
        )
        parser.add_argument(
            "--schema",
            action="append",
            dest="schemas",
            metavar="SCHEMA",
            help="Reset sequences in a specific schema (repeatable).",
        )

    def handle(self, *args, **options):
        schemas_to_reset = []

        if options["all_schemas"]:
            with connection.cursor() as c:
                c.execute(
                    "SELECT schema_name FROM information_schema.schemata "
                    "WHERE schema_name NOT IN ('pg_catalog','information_schema','pg_toast') "
                    "  AND schema_name NOT LIKE 'pg_%' "
                    "ORDER BY schema_name"
                )
                schemas_to_reset = [row[0] for row in c.fetchall()]
        elif options["schemas"]:
            schemas_to_reset = options["schemas"]
        else:
            schemas_to_reset = ["public"]

        total_reset = 0
        for schema in schemas_to_reset:
            count = self._reset_schema(schema)
            total_reset += count

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Reset {total_reset} sequence(s) across {len(schemas_to_reset)} schema(s)."
            )
        )

    def _reset_schema(self, schema):
        """Reset all sequences in the given schema. Returns count of sequences reset."""
        with connection.cursor() as c:
            # Build SETVAL statements for every serial/identity column in this schema.
            c.execute(
                """
                SELECT
                    'SELECT SETVAL(' ||
                    quote_literal(quote_ident(%(schema)s) || '.' || quote_ident(seq.relname)) ||
                    ', COALESCE((SELECT MAX(' || quote_ident(att.attname) || ') FROM ' ||
                    quote_ident(%(schema)s) || '.' || quote_ident(tbl.relname) ||
                    '), 1))' AS stmt
                FROM pg_class seq
                JOIN pg_depend dep ON dep.objid = seq.oid
                JOIN pg_class tbl ON dep.refobjid = tbl.oid
                JOIN pg_attribute att
                    ON att.attrelid = tbl.oid
                   AND att.attnum = dep.refobjsubid
                JOIN pg_namespace ns ON seq.relnamespace = ns.oid
                WHERE seq.relkind = 'S'
                  AND ns.nspname = %(schema)s
                ORDER BY seq.relname
                """,
                {"schema": schema},
            )
            stmts = [row[0] for row in c.fetchall()]

        if not stmts:
            self.stdout.write(f"  {schema}: no sequences found, skipped.")
            return 0

        with connection.cursor() as c:
            for stmt in stmts:
                c.execute(stmt)

        self.stdout.write(f"  {schema}: reset {len(stmts)} sequence(s).")
        return len(stmts)
