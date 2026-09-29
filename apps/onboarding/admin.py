"""
Onboarding Admin
"""

from django.contrib import admin
from django import forms
from django.template.response import TemplateResponse
from django.urls import path
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_GET

from .models import OnboardingChoice, OnboardingProgress
from .services.monitoring import onboarding_report, require_report_access


class ReportFilters(forms.Form):
    since = forms.DateTimeField(required=False, label="Signed up since")
    query = forms.CharField(required=False, max_length=200, label="Email or Workspace")
    page = forms.IntegerField(required=False, min_value=1, widget=forms.HiddenInput)


@admin.register(OnboardingProgress)
class OnboardingProgressAdmin(admin.ModelAdmin):
    change_list_template = "admin/onboarding/progress_list.html"

    def get_urls(self):
        return [path("report/", self.admin_site.admin_view(self.report),
                     name="onboarding_progress_report")] + super().get_urls()

    @method_decorator(require_GET)
    def report(self, request):
        require_report_access(request.user)
        filters = ReportFilters(request.GET)
        report = None
        if filters.is_valid():
            report = onboarding_report(actor=request.user, **filters.cleaned_data)
        return TemplateResponse(request, "admin/onboarding/report.html", {
            **self.admin_site.each_context(request), "title": "Onboarding report",
            "opts": self.model._meta, "filters": filters, "report": report,
        }, status=200 if report is not None else 400)

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
