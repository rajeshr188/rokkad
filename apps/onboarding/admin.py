"""
Onboarding Admin
"""

from django.contrib import admin

from .models import OnboardingChoice, OnboardingProgress


@admin.register(OnboardingProgress)
class OnboardingProgressAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "current_step",
        "progress_percentage",
        "is_complete",
        "created_at",
    )
    list_filter = ("current_step", "is_complete", "created_at")
    search_fields = ("user__email", "user__first_name", "user__last_name")
    readonly_fields = (
        "created_at",
        "updated_at",
        "completed_at",
        "progress_percentage",
    )

    fieldsets = (
        ("User", {"fields": ("user",)}),
        (
            "Progress",
            {
                "fields": (
                    "current_step",
                    "progress_percentage",
                    "profile_completed",
                    "company_created",
                    "team_setup_completed",
                    "tour_completed",
                    "is_complete",
                )
            },
        ),
        (
            "Skipped Steps",
            {"fields": ("skipped_team", "skipped_tour"), "classes": ("collapse",)},
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at", "completed_at"),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(OnboardingChoice)
class OnboardingChoiceAdmin(admin.ModelAdmin):
    list_display = ("progress", "step", "choice_key", "choice_value", "created_at")
    list_filter = ("step", "created_at")
    search_fields = ("progress__user__email", "choice_key", "choice_value")
    readonly_fields = ("created_at",)
