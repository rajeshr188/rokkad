"""
Check onboarding setup and ensure all users have progress records
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.onboarding.models import OnboardingProgress

User = get_user_model()


class Command(BaseCommand):
    help = "Check onboarding setup and create missing progress records"

    def add_arguments(self, parser):
        parser.add_argument(
            "--fix",
            action="store_true",
            help="Create missing OnboardingProgress records for all users",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("🔍 Checking Onboarding Setup...\n"))

        # Get all users
        total_users = User.objects.count()
        users_with_progress = (
            OnboardingProgress.objects.values("user_id").distinct().count()
        )

        self.stdout.write(f"Total Users: {total_users}")
        self.stdout.write(f"Users with Onboarding Progress: {users_with_progress}")

        # Find users without progress
        users_without_progress = User.objects.exclude(onboarding_progress__isnull=False)
        missing_count = users_without_progress.count()

        if missing_count > 0:
            self.stdout.write(
                self.style.WARNING(
                    f"\n⚠️  {missing_count} users missing progress records"
                )
            )

            if options["fix"]:
                self.stdout.write("\n📝 Creating missing progress records...")
                created = 0
                for user in users_without_progress:
                    OnboardingProgress.objects.create(user=user)
                    created += 1

                self.stdout.write(
                    self.style.SUCCESS(f"\n✅ Created {created} new progress records!")
                )
        else:
            self.stdout.write(
                self.style.SUCCESS("\n✅ All users have onboarding progress records!")
            )

        # Show completion stats
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("📊 Onboarding Completion Stats:")
        self.stdout.write("=" * 60)

        completed = OnboardingProgress.objects.filter(is_complete=True).count()
        incomplete = OnboardingProgress.objects.filter(is_complete=False).count()

        completion_rate = (completed / total_users * 100) if total_users > 0 else 0

        self.stdout.write(
            f"Completed Onboarding: {completed}/{total_users} ({completion_rate:.1f}%)"
        )
        self.stdout.write(f"Incomplete Onboarding: {incomplete}/{total_users}")

        # Show step completion
        profile_done = OnboardingProgress.objects.filter(profile_completed=True).count()
        company_done = OnboardingProgress.objects.filter(company_created=True).count()
        team_done = (
            OnboardingProgress.objects.filter(
                team_setup_completed=True, is_complete=False
            ).count()
            + OnboardingProgress.objects.filter(skipped_team=True).count()
        )

        self.stdout.write("\n📋 Step Completion:")
        self.stdout.write(f"  Step 1 (Profile): {profile_done}/{total_users}")
        self.stdout.write(f"  Step 2 (Company): {company_done}/{total_users}")
        self.stdout.write(f"  Step 3 (Team): {team_done}/{total_users}")

        if not options["fix"] and missing_count > 0:
            self.stdout.write(
                self.style.WARNING(
                    "\n💡 Run with --fix flag to create missing progress records"
                )
            )
