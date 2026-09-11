"""Owner-only provisioning for a NEW runtime login; never alters existing roles."""
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def provision():
    import django
    from django.db import connection, transaction
    from psycopg2 import sql

    if os.environ.get("DJANGO_SETTINGS_MODULE") != "django_project.settings.migration":
        raise RuntimeError("Provisioning requires the owner-only migration settings.")
    django.setup()
    role_name = os.environ["DB_RUNTIME_USER"]
    password = os.environ["DB_RUNTIME_PASSWORD"]
    if not role_name or not password:
        raise ValueError("Runtime role and password must be nonempty.")
    role = sql.Identifier(role_name)
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("SELECT current_user, current_database()")
        owner, database = cursor.fetchone()
        if owner == role_name:
            raise ValueError("Migration and runtime roles must be different.")
        cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", [role_name])
        if cursor.fetchone():
            raise ValueError("Runtime role already exists; review it explicitly instead of changing its credentials or grants.")
        cursor.execute(sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD %s").format(role), [password])
        cursor.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(database), role))
        cursor.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(role))
        cursor.execute(sql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {}").format(role))
        cursor.execute(sql.SQL("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {}").format(role))
        cursor.execute(sql.SQL("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {}").format(role))
        cursor.execute(sql.SQL("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO {}").format(role))
    connection.close()
    print("Runtime role created; default grants apply to objects created by this migration owner.")


if __name__ == "__main__":
    provision()
