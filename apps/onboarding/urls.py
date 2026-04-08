"""
Onboarding URL Configuration
"""

from django.urls import path

from . import views

urlpatterns = [
    path("start/", views.onboarding_start, name="onboarding_start"),
    path("profile/", views.onboarding_profile, name="onboarding_profile"),
    path("company/", views.onboarding_company, name="onboarding_company"),
    path("team/", views.onboarding_team, name="onboarding_team"),
    path("tour/", views.onboarding_tour, name="onboarding_tour"),
    path("complete/", views.onboarding_complete, name="onboarding_complete"),
    path("skip/", views.onboarding_skip, name="onboarding_skip"),
]
