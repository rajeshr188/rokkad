import os
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Backup PostgreSQL database"

    def handle(self, *args, **options):
        # Define your PostgreSQL database settings
        db_settings = settings.DATABASES["default"]

        # # Create backup directory if it doesn't exist
        # backup_dir = 'path/to/your/backup/directory'
        # os.makedirs(backup_dir, exist_ok=True)
        # Create backup directory within your Django project if it doesn't exist
        backup_dir = os.path.join(settings.BASE_DIR, "backup")
        os.makedirs(backup_dir, exist_ok=True)

        # Backup filename with timestamp
        backup_file = os.path.join(
            backup_dir, f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
        )

        # Set the PGPASSWORD environment variable with the database user's password
        os.environ["PGPASSWORD"] = db_settings["PASSWORD"]
        # PostgreSQL dump command
        dump_cmd = f"pg_dump -h {db_settings['HOST']} -d {db_settings['NAME']} -U {db_settings['USER']} -Fc -f {backup_file}"

        # Execute the command
        os.system(dump_cmd)

        self.stdout.write(
            self.style.SUCCESS(f"Database backup created at {backup_file}")
        )


import os
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand

# class Command(BaseCommand):
#     help = "Backup PostgreSQL database for a specific schema"

#     def add_arguments(self, parser):
#         parser.add_argument('schema_name', type=str, help='The name of the schema to back up')

#     def handle(self, *args, **options):
#         schema_name = options['schema_name']

#         # Define your PostgreSQL database settings
#         db_settings = settings.DATABASES["default"]

#         # Create backup directory within your Django project if it doesn't exist
#         backup_dir = os.path.join(settings.BASE_DIR, "backup")
#         os.makedirs(backup_dir, exist_ok=True)

#         # Backup filename with timestamp
#         backup_file = os.path.join(
#             backup_dir, f"backup_{schema_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
#         )

#         # Set the PGPASSWORD environment variable with the database user's password
#         os.environ["PGPASSWORD"] = db_settings["PASSWORD"]

#         # PostgreSQL dump command with schema option
#         dump_cmd = f"pg_dump -h {db_settings['HOST']} -d {db_settings['NAME']} -U {db_settings['USER']} --schema={schema_name} -Fc -f {backup_file}"

#         # Execute the command
#         os.system(dump_cmd)

#         self.stdout.write(
#             self.style.SUCCESS(f"Database backup for schema '{schema_name}' created at {backup_file}")
#         )
