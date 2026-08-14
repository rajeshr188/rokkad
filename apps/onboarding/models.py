"""
Onboarding Progress Tracking Models
"""

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class OnboardingProgress(models.Model):
    """
    Track a user's progress through the onboarding flow.

    Steps:
    1. Profile Setup (name, role, picture)
    2. Company Setup (name, industry, timezone)
    3. Team Invites (optional)
    4. Feature Tour (optional)
    5. Complete
    """

    STEP_CHOICES = [
        (1, "Profile Setup"),
        (2, "Company Setup"),
        (3, "Team Setup"),
        (4, "Feature Tour"),
        (5, "Complete"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="onboarding_progress",
        verbose_name=_("User"),
    )

    current_step = models.IntegerField(
        choices=STEP_CHOICES, default=1, verbose_name=_("Current Step")
    )

    profile_completed = models.BooleanField(
        default=False, verbose_name=_("Profile Completed")
    )
    company_created = models.BooleanField(
        default=False, verbose_name=_("Company Created")
    )
    team_setup_completed = models.BooleanField(
        default=False, verbose_name=_("Team Setup")
    )
    tour_completed = models.BooleanField(
        default=False, verbose_name=_("Tour Completed")
    )

    is_complete = models.BooleanField(
        default=False, verbose_name=_("Onboarding Complete")
    )
    completed_at = models.DateTimeField(
        null=True, blank=True, verbose_name=_("Completed At")
    )

    skipped_tour = models.BooleanField(default=False, verbose_name=_("Skipped Tour"))
    skipped_team = models.BooleanField(default=False, verbose_name=_("Skipped Team"))

    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))

    class Meta:
        verbose_name = _("Onboarding Progress")
        verbose_name_plural = _("Onboarding Progress")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} - Step {self.current_step}"

    def mark_step_complete(self, step_number):
        """Mark a specific step as complete and advance"""
        if step_number == 1:
            self.profile_completed = True
            self.current_step = 2
        elif step_number == 2:
            self.company_created = True
            self.current_step = 3
        elif step_number == 3:
            self.team_setup_completed = True
            self.current_step = 4
        elif step_number == 4:
            self.tour_completed = True
            self.current_step = 5
            self.complete_onboarding()

        self.save()

    def complete_onboarding(self):
        """Mark onboarding as fully complete"""
        self.is_complete = True
        self.completed_at = timezone.now()
        self.current_step = 5
        self.save()

    def skip_step(self, step_number):
        """Skip an optional step"""
        if step_number == 3:
            self.skipped_team = True
            self.current_step = 4
        elif step_number == 4:
            self.skipped_tour = True
            self.complete_onboarding()
        self.save()

    @property
    def progress_percentage(self):
        """Calculate completion percentage"""
        completed = sum(
            [
                self.profile_completed,
                self.company_created,
                self.team_setup_completed or self.skipped_team,
                self.tour_completed or self.skipped_tour,
            ]
        )
        return int((completed / 4) * 100)

    @property
    def next_step_url(self):
        """Get URL for the next step"""
        from django.urls import reverse

        step_urls = {
            1: "onboarding_profile",
            2: "onboarding_company",
            3: "onboarding_team",
            4: "onboarding_tour",
            5: "onboarding_complete",
        }
        return reverse(step_urls.get(self.current_step, "onboarding_complete"))


class OnboardingChoice(models.Model):
    """
    Track user choices during onboarding for analytics.
    """

    progress = models.ForeignKey(
        OnboardingProgress,
        on_delete=models.CASCADE,
        related_name="choices",
        verbose_name=_("Progress"),
    )

    step = models.IntegerField(verbose_name=_("Step"))
    choice_key = models.CharField(max_length=100, verbose_name=_("Choice Key"))
    choice_value = models.TextField(verbose_name=_("Choice Value"))

    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))

    class Meta:
        verbose_name = _("Onboarding Choice")
        verbose_name_plural = _("Onboarding Choices")
        ordering = ["step", "created_at"]

    def __str__(self):
        return f"{self.progress.user.email} - {self.choice_key}: {self.choice_value}"


class WorkspaceSetupState(models.Model):
    """User-specific workspace setup checklist display state."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="workspace_setup_states",
        verbose_name=_("User"),
    )
    workspace = models.ForeignKey(
        "orgs.Company",
        on_delete=models.CASCADE,
        related_name="setup_states",
        verbose_name=_("Workspace"),
    )
    dismissed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Dismissed At"),
    )
    marked_complete_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Marked Complete At"),
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))

    class Meta:
        verbose_name = _("Workspace Setup State")
        verbose_name_plural = _("Workspace Setup States")
        constraints = [
            models.UniqueConstraint(
                fields=["user", "workspace"],
                name="onboarding_workspace_setup_state_unique_user_workspace",
            ),
        ]

    @property
    def is_dismissed(self):
        return self.dismissed_at is not None

    @property
    def is_marked_complete(self):
        return self.marked_complete_at is not None

    def __str__(self):
        return f"{self.user} - {self.workspace} setup state"
