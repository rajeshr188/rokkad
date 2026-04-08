"""
Onboarding Signals - Auto-create progress for new users
"""

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import OnboardingProgress

User = get_user_model()


@receiver(post_save, sender=User)
def create_onboarding_progress(sender, instance, created, **kwargs):
    """
    Automatically create OnboardingProgress when a new user signs up
    """
    if created:
        OnboardingProgress.objects.get_or_create(user=instance)
