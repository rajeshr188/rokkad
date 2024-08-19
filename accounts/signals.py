from allauth.socialaccount.signals import social_account_added, social_account_updated
from django.dispatch import receiver
from .models import CustomUser

@receiver(social_account_added)
@receiver(social_account_updated)
def save_profile_picture(request, sociallogin, **kwargs):
    user = sociallogin.user
    if sociallogin.account.provider == 'google':
        extra_data = sociallogin.account.extra_data
        picture_url = extra_data.get('picture')
        if picture_url:
            user.social_profile_picture = picture_url
            user.save()