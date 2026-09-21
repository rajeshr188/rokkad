"""Owner-only provisioning of a restricted runtime login and database grants."""
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
    grant_existing = os.environ.get("ROKKAD_RUNTIME_GRANT_EXISTING") == "1"
    password = os.environ.get("DB_RUNTIME_PASSWORD")
    if not role_name:
        raise ValueError("Runtime role must be nonempty.")
    role = sql.Identifier(role_name)
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("SELECT current_user, current_database()")
        owner, database = cursor.fetchone()
        if owner == role_name:
            raise ValueError("Migration and runtime roles must be different.")
        cursor.execute("SELECT rolcanlogin, rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls FROM pg_roles WHERE rolname = %s", [role_name])
        existing = cursor.fetchone()
        if existing:
            if not grant_existing:
                raise ValueError("Runtime role already exists; set ROKKAD_RUNTIME_GRANT_EXISTING=1 to grant this database without changing the role.")
            if existing != (True, False, False, False, False, False):
                raise ValueError("Existing runtime role is not a restricted login; correct the role outside this grant command.")
        else:
            if not password:
                raise ValueError("Runtime password must be nonempty when creating a new runtime role.")
            cursor.execute(sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD %s").format(role), [password])
        cursor.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(database), role))
        cursor.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(role))
        cursor.execute(sql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {}").format(role))
        cursor.execute(sql.SQL("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {}").format(role))
        cursor.execute(sql.SQL("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {}").format(role))
        cursor.execute(sql.SQL("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO {}").format(role))
    connection.close()
    print("Runtime role grants are ready; default grants apply to objects created by this migration owner.")


if __name__ == "__main__":
    provision()
