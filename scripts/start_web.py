"""Validate the runtime connection and schema before starting a web process."""
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def check_runtime():
    import django
    from django.core.management import call_command, CommandError
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor

    django.setup()
    call_command("check", deploy=True, databases=["default"], fail_level="ERROR")
    executor = MigrationExecutor(connection)
    if executor.migration_plan(executor.loader.graph.leaf_nodes()):
        raise CommandError("Pending migrations: run the separate owner-only migration step first.")
    connection.close()


if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_project.settings.prod")
    check_runtime()
    if len(sys.argv) > 1:
        os.execvp(sys.argv[1], sys.argv[1:])
