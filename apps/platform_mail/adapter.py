from allauth.account.adapter import DefaultAccountAdapter
from allauth.account.signals import user_signed_up
from django.conf import settings
from invitations.adapters import BaseInvitationsAdapter

from .account_mail import enqueue_account_email
from .models import AccountEmail


class AccountAdapter(DefaultAccountAdapter):
    """Keep invitation signup policy and allauth rate limits; replace two mail hooks."""
    def is_open_for_signup(self, request):
        return BaseInvitationsAdapter.is_open_for_signup(self, request)

    def get_user_signed_up_signal(self):
        return user_signed_up

    def send_confirmation_mail(self, request, emailconfirmation, signup):
        if not settings.ACCOUNT_EMAIL_ENABLED:
            return super().send_confirmation_mail(request, emailconfirmation, signup)
        address = emailconfirmation.email_address
        return enqueue_account_email(user=address.user, email=address.email,
                                     email_address=address, kind=AccountEmail.Kind.VERIFICATION)

    def send_password_reset_mail(self, user, email, context):
        if not settings.ACCOUNT_EMAIL_ENABLED:
            return super().send_password_reset_mail(user, email, context)
        # Deliberately discard the request-host URL and pre-generated token.
        return enqueue_account_email(user=user, email=email, kind=AccountEmail.Kind.PASSWORD_RESET)
