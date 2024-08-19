import requests
from django.core.management.base import BaseCommand
from allauth.socialaccount.models import SocialAccount
from your_app.models import CustomUser

class Command(BaseCommand):
    help = 'Fetch and update Google profile pictures for existing users'

    def handle(self, *args, **kwargs):
        google_accounts = SocialAccount.objects.filter(provider='google')
        for account in google_accounts:
            user = account.user
            extra_data = account.extra_data
            picture_url = extra_data.get('picture')
            if picture_url:
                user.social_profile_picture = picture_url
                user.save()
                self.stdout.write(self.style.SUCCESS(f'Updated profile picture for user {user.username}'))
            else:
                self.stdout.write(self.style.WARNING(f'No profile picture found for user {user.username}'))