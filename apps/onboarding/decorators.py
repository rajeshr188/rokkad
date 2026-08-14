"""
Onboarding Decorators - Enforce onboarding completion
"""

import functools
from django.shortcuts import redirect

from .models import OnboardingProgress


def onboarding_required(view_func=None, allow_skip=False):
    """
    Decorator to enforce onboarding completion before accessing views.

    Usage:
        @onboarding_required
        def my_view(request):
            ...

    Args:
        allow_skip: If True, allows users who skipped onboarding
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(request, *args, **kwargs):
            # Skip check for anonymous users
            if not request.user.is_authenticated:
                return func(request, *args, **kwargs)

            # Skip check for onboarding URLs themselves
            onboarding_urls = [
                "onboarding_start",
                "onboarding_profile",
                "onboarding_company",
                "onboarding_team",
                "onboarding_tour",
                "onboarding_complete",
                "onboarding_skip",
            ]
            if (
                request.resolver_match
                and request.resolver_match.url_name in onboarding_urls
            ):
                return func(request, *args, **kwargs)

            # Check onboarding progress
            try:
                progress = OnboardingProgress.objects.get(user=request.user)
                if not progress.is_complete:
                    # Redirect to current onboarding step
                    return redirect(progress.next_step_url)
            except OnboardingProgress.DoesNotExist:
                # Create progress and redirect to onboarding
                progress = OnboardingProgress.objects.create(user=request.user)
                return redirect("onboarding_start")

            return func(request, *args, **kwargs)

        return wrapper

    # Handle both @onboarding_required and @onboarding_required()
    if view_func:
        return decorator(view_func)
    return decorator


def onboarding_optional(view_func):
    """
    Decorator that allows access but shows onboarding banner if incomplete.

    Adds 'onboarding_incomplete' to context if onboarding not complete.
    """

    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated:
            try:
                progress = OnboardingProgress.objects.get(user=request.user)
                if not progress.is_complete:
                    request.onboarding_incomplete = True
                    request.onboarding_progress = progress
            except OnboardingProgress.DoesNotExist:
                request.onboarding_incomplete = True
                request.onboarding_progress = None

        return view_func(request, *args, **kwargs)

    return wrapper
