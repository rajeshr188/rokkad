"""
Management command to setup default roles and permissions.
Run with: python manage.py setup_permissions
"""

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.orgs.models import Company, Role
from apps.orgs.permissions import ALL_PERMISSIONS, get_permissions_for_role


class Command(BaseCommand):
    help = "Setup default roles and permissions for the application"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing roles and recreate them",
        )

    def handle(self, *args, **options):
        reset = options["reset"]

        self.stdout.write(self.style.SUCCESS("=" * 70))
        self.stdout.write(self.style.SUCCESS("Setting up permissions and roles"))
        self.stdout.write(self.style.SUCCESS("=" * 70))

        with transaction.atomic():
            # Step 1: Create content type for Company (used for permissions)
            company_ct = ContentType.objects.get_for_model(Company)

            # Step 2: Create all permissions
            self.stdout.write("\n📝 Creating permissions...")
            created_perms = self.create_permissions(company_ct)
            self.stdout.write(
                self.style.SUCCESS(f"✓ Created {created_perms} permissions")
            )

            # Step 3: Reset roles if requested
            if reset:
                self.stdout.write("\n🗑️  Deleting existing roles...")
                deleted = Role.objects.all().delete()[0]
                self.stdout.write(self.style.WARNING(f"✓ Deleted {deleted} roles"))

            # Step 4: Create default roles
            self.stdout.write("\n👥 Creating default roles...")
            self.create_default_roles()
            self.stdout.write(self.style.SUCCESS("✓ Created default roles"))

            # Step 5: Summary
            self.print_summary()

        self.stdout.write(self.style.SUCCESS("\n✅ Setup complete!"))

    def create_permissions(self, content_type):
        """Create all custom permissions"""
        created = 0

        for codename, name, description in ALL_PERMISSIONS:
            perm, created_now = Permission.objects.get_or_create(
                codename=codename, content_type=content_type, defaults={"name": name}
            )
            if created_now:
                created += 1
                self.stdout.write(f"  + {codename}: {name}")

        return created

    def create_default_roles(self):
        """Create default roles with permissions"""
        # Map desired names to alternative names that might exist
        role_mappings = {
            "Owner": ["Owner"],
            "Admin": ["Admin", "Administrator"],
            "Member": ["Member", "User"],
            "Viewer": ["Viewer", "Customer", "Guest", "Read-Only"],
        }

        for role_name, alternatives in role_mappings.items():
            role = None
            created = False

            # Try to find existing role by name or alternatives
            for alt_name in alternatives:
                try:
                    role = Role.objects.get(name__iexact=alt_name)
                    self.stdout.write(f"  Found existing role: {role.name}")
                    break
                except Role.DoesNotExist:
                    continue
                except Role.MultipleObjectsReturned:
                    role = Role.objects.filter(name__iexact=alt_name).first()
                    self.stdout.write(
                        f"  ⚠️  Multiple {alt_name} roles found, using first"
                    )
                    break

            # If not found, create it
            if not role:
                role = Role.objects.create(name=role_name)
                created = True
                self.stdout.write(f"  ✨ Created new role: {role.name}")

            # Get permissions for this role (use the canonical name)
            perm_codenames = get_permissions_for_role(role_name)

            # Assign permissions
            perms = Permission.objects.filter(codename__in=perm_codenames)
            role.permissions.set(perms)

            status = "✨ Created" if created else "♻️  Updated"
            self.stdout.write(
                f'  {status} {role_name} (as "{role.name}"): {perms.count()} permissions'
            )

    def print_summary(self):
        """Print summary of created roles and permissions"""
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("SUMMARY"))
        self.stdout.write("=" * 70)

        total_permissions = Permission.objects.filter(
            codename__in=[p[0] for p in ALL_PERMISSIONS]
        ).count()
        self.stdout.write(f"\nTotal Permissions: {total_permissions}")

        self.stdout.write("\nRoles:")
        for role in Role.objects.all().order_by("name"):
            perm_count = role.permissions.count()
            self.stdout.write(f"  • {role.name}: {perm_count} permissions")

        self.stdout.write("\n" + "=" * 70)
