from django.db import models
from django.conf import settings
# Create your models here.
import datetime
from invitations.base_invitation import AbstractBaseInvitation
from invitations.app_settings import app_settings
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _
from django.contrib.sites.shortcuts import get_current_site
from django.urls import reverse
from invitations import signals
from invitations.adapters import get_invitations_adapter

class Company(models.Model):
    name = models.CharField(max_length=200)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='owned_companies', on_delete=models.CASCADE)

    class Meta:
        unique_together = ('name', 'owner')

    def __str__(self):
        return self.name
    

class Membership(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    role = models.ForeignKey('Role', on_delete=models.CASCADE,null=True,blank=True)
    date_joined = models.DateTimeField(auto_now_add=True)
    invite_reason = models.CharField(max_length=64)

    class Meta:
        unique_together = ('user', 'company')

    def __str__(self):
        return f"{self.user} in {self.company}"

class Role(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class CompanyInvitation(AbstractBaseInvitation):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    email = models.EmailField(
        unique=True,
        verbose_name=_("e-mail address"),
        max_length=app_settings.EMAIL_MAX_LENGTH,
    )
    created = models.DateTimeField(verbose_name=_("created"), default=timezone.now)

    @classmethod
    def create(cls, email, company,inviter=None, **kwargs):
        key = get_random_string(64).lower()
        instance = cls._default_manager.create(
            company = company,
            email=email, key=key, inviter=inviter, **kwargs
        )
        return instance

    def key_expired(self):
        expiration_date = self.sent + datetime.timedelta(
            days=app_settings.INVITATION_EXPIRY,
        )
        return expiration_date <= timezone.now()

    def send_invitation(self, request, **kwargs):
        current_site = get_current_site(request)
        invite_url = reverse(app_settings.CONFIRMATION_URL_NAME, args=[self.key])
        invite_url = request.build_absolute_uri(invite_url)
        ctx = kwargs
        ctx.update(
            {
                "invite_url": invite_url,
                "site_name": current_site.name,
                "email": self.email,
                "key": self.key,
                "inviter": self.inviter,
            },
        )

        email_template = "invitations/email/email_invite"

        get_invitations_adapter().send_mail(email_template, self.email, ctx)
        self.sent = timezone.now()
        self.save()

        signals.invite_url_sent.send(
            sender=self.__class__,
            instance=self,
            invite_url_sent=invite_url,
            inviter=self.inviter,
        )

    def __str__(self):
        return f"Invite: {self.email}"
