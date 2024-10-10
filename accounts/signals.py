from allauth.socialaccount.signals import social_account_added, social_account_updated
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import CustomUser, UserProfile


@receiver(social_account_added)
@receiver(social_account_updated)
def save_profile_picture(request, sociallogin, **kwargs):
    user = sociallogin.user
    if sociallogin.account.provider == "google":
        extra_data = sociallogin.account.extra_data
        picture_url = extra_data.get("picture")
        if picture_url:
            user.profile.social_profile_picture = picture_url
            user.profile.save()


@receiver(post_save, sender=CustomUser)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
    else:
        # Ensure that the UserProfile exists for existing users
        UserProfile.objects.get_or_create(user=instance)
