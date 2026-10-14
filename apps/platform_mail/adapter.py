from allauth.account.adapter import DefaultAccountAdapter
from allauth.account.signals import user_signed_up
from django.conf import settings
from django.urls import reverse
from urllib.parse import urlencode
from invitations.adapters import BaseInvitationsAdapter

from .account_mail import enqueue_account_email
from .models import AccountEmail


class AccountAdapter(DefaultAccountAdapter):
    """Keep invitation signup policy and allauth rate limits; replace two mail hooks."""
    def is_open_for_signup(self, request):
        return BaseInvitationsAdapter.is_open_for_signup(self, request)

    def get_user_signed_up_signal(self):
        return user_signed_up

    def get_email_verification_redirect_url(self, email_address):
        # The token identifies the account, but supplies no business access.
        # Construct only a current owner's canonical navigation destination;
        # its normal authentication/membership/RLS checks still apply.
        from apps.onboarding.services.account_journey import owner_business_setup_url, owner_setup_workspace
        user = email_address.user
        remembered = self.request.session.pop("onboarding_verification_return", None)
        workspace = owner_setup_workspace(user, remembered=remembered)
        target = (owner_business_setup_url(user, workspace=workspace) if workspace
                  and email_address.email.casefold() == (user.email or "").casefold() else None)
        if target:
            if self.request.user.is_authenticated and self.request.user.pk == user.pk:
                return target
            return reverse("account_login") + "?" + urlencode({"next": target})
        return super().get_email_verification_redirect_url(email_address)

    def send_confirmation_mail(self, request, emailconfirmation, signup):
        # Remember only a validated navigation identity, not a token, URL or
        # permission. Revalidate ownership/membership at confirmation time.
        if request and request.user.is_authenticated and request.user.pk == emailconfirmation.email_address.user_id:
            values = request.POST if request.method == "POST" else request.GET
            slug = values.get("setup_workspace")
            if slug:
                from apps.onboarding.services.account_journey import owner_setup_workspace
                workspace = owner_setup_workspace(request.user, slug=slug)
                if workspace:
                    request.session["onboarding_verification_return"] = {
                        "user_id": request.user.pk, "workspace_id": workspace.pk,
                    }
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
