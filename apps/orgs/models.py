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
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django_tenants.models import TenantMixin, DomainMixin
from django.utils.translation import gettext_lazy as _

User = get_user_model()


class Company(TenantMixin):
    name = models.CharField(_("Name"),max_length=200,unique=True)
    members = models.ManyToManyField(User, through='Membership',
        through_fields=('company', 'user'),)
    owner = models.ForeignKey(verbose_name = _("Owner"), to = User, related_name='owned_companies', on_delete=models.CASCADE)
    creator = models.ForeignKey(verbose_name = _("Creator"),to = User, related_name='created_companies', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    auto_create_schema = True
    auto_drop_schema = True

    class Meta:
        unique_together = ('name', 'owner')
        verbose_name = _("Company")
        verbose_name_plural = _("Companies")
        # permissions = [
        #     ("view_company", "Can view company"),
        #     ("edit_company", "Can edit company"),
        #     ("delete_company", "Can delete company"),
        #     ("invite_to_company", "Can invite to company"),
        #     ("remove_from_company", "Can remove from company"),
        #     ("change_role", "Can change role"),
        # ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('orgs_company_detail', args=[str(self.id)])

class Domain(DomainMixin):
    pass

class CompanyOwnership(models.Model):
    user = models.ForeignKey(verbose_name = _("User"),to = User, on_delete=models.CASCADE)
    company = models.ForeignKey(verbose_name = _("Company"), to =Company, on_delete=models.CASCADE)
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('user', 'company')

    def __str__(self):
        return f"{self.user} owns {self.company} since {self.start_date}"

    from django.utils import timezone

# Transfer ownership of a company to a new user
# def transfer_ownership(company, new_owner):
#     # End the current ownership
#     current_ownership = CompanyOwnership.objects.filter(company=company, end_date__isnull=True).first()
#     if current_ownership:
#         current_ownership.end_date = timezone.now()
#         current_ownership.save()

#     # Start a new ownership
#     new_ownership = CompanyOwnership(user=new_owner, company=company)
#     new_ownership.save()

class Membership(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,related_name='memberships')
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    role = models.ForeignKey('Role', on_delete=models.CASCADE,null=True,blank=True,related_name = 'memberships')
    date_joined = models.DateTimeField(auto_now_add=True)
    invite_reason = models.CharField(max_length=64)

    class Meta:
        unique_together = ('user', 'company')
        # permissions = [
        #     ("invite_to_company", "Can invite to company"),
        #     ("remove_from_company", "Can remove from company"),
        #     ("change_role", "Can change role"),

        # ]

    def __str__(self):
        return f"{self.user} as {self.role} in {self.company} since {self.date_joined}"


class Role(models.Model):
    name = models.CharField(_("name"),max_length=100)
    permissions = models.ManyToManyField(Permission)

    class Meta:
        verbose_name = _("role")
        verbose_name_plural = _("roles")

    def __str__(self):
        return self.name


class CompanyInvitation(AbstractBaseInvitation):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="invitations")
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
        return f"Invited: {self.email} Accepted: {self.accepted} "
