from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connection

# set search_path to jsk_now;
# BEGIN;
# SELECT setval(pg_get_serial_sequence('"contact_customer"','id'), coalesce(max("id"), 1), max("id") IS NOT null) FROM "contact_customer";
# SELECT setval(pg_get_serial_sequence('"contact_customerrelationship"','id'), coalesce(max("id"), 1), max("id")
#  IS NOT null) FROM "contact_customerrelationship";
# SELECT setval(pg_get_serial_sequence('"contact_address"','id'), coalesce(max("id"), 1), max("id") IS NOT null)
#  FROM "contact_address";
# SELECT setval(pg_get_serial_sequence('"contact_contact"','id'), coalesce(max("id"), 1), max("id") IS NOT null)
#  FROM "contact_contact";
# SELECT setval(pg_get_serial_sequence('"contact_proof"','id'), coalesce(max("id"), 1), max("id") IS NOT null) FROM "contact_proof";
# SELECT setval(pg_get_serial_sequence('"girvi_license"','id'), coalesce(max("id"), 1), max("id") IS NOT null) FROM "girvi_license";
# SELECT setval(pg_get_serial_sequence('"girvi_series"','id'), coalesce(max("id"), 1), max("id") IS NOT null) FROM "girvi_series";
# SELECT setval(pg_get_serial_sequence('"girvi_loan"','id'), coalesce(max("id"), 1), max("id") IS NOT null) FROM
#  "girvi_loan";
# SELECT setval(pg_get_serial_sequence('"girvi_loanitem"','id'), coalesce(max("id"), 1), max("id") IS NOT null) FROM "girvi_loanitem";
# SELECT setval(pg_get_serial_sequence('"girvi_loanpayment"','id'), coalesce(max("id"), 1), max("id") IS NOT null) FROM "girvi_loanpayment";
# SELECT setval(pg_get_serial_sequence('"girvi_statement"','id'), coalesce(max("id"), 1), max("id") IS NOT null)
#  FROM "girvi_statement";
# SELECT setval(pg_get_serial_sequence('"girvi_statementitem"','id'), coalesce(max("id"), 1), max("id") IS NOT null) FROM "girvi_statementitem";
# SELECT setval(pg_get_serial_sequence('"girvi_release"','id'), coalesce(max("id"), 1), max("id") IS NOT null) FROM "girvi_release";
# COMMIT;


class Command(BaseCommand):
    help = "Reset SQL sequences in all schemas"

    def handle(self, *args, **kwargs):
        schemas = [
            "jcl",
        ]  # replace with your schema names
        # apps = [app.split('.')[-1] for app in settings.INSTALLED_APPS if 'django' not in app]
        apps = ["girvi", "contact"]
        with connection.cursor() as cursor:
            for schema in schemas:
                cursor.execute(f"SET search_path TO {schema};")
                for app in apps:
                    sql_statements = call_command("sqlsequencereset", app)
                    for statement in sql_statements:
                        cursor.execute(statement)
                cursor.execute("SET search_path TO public;")
        self.stdout.write(
            self.style.SUCCESS("Successfully reset SQL sequences in all schemas")
        )
