# Create your models here.
import datetime

from colorfield.fields import ColorField
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.sites.shortcuts import get_current_site
from django.db import IntegrityError, models, transaction
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _
from invitations import signals
from invitations.adapters import get_invitations_adapter
from invitations.app_settings import app_settings
from invitations.base_invitation import AbstractBaseInvitation

User = get_user_model()


class CompanyManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(lifecycle_state="ACTIVE")

class Company(models.Model):
    class LifecycleState(models.TextChoices):
        ACTIVE = "ACTIVE", _("Active")
        SUSPENDED = "SUSPENDED", _("Suspended")
        ARCHIVED = "ARCHIVED", _("Archived")
        DELETION_PENDING = "DELETION_PENDING", _("Deletion pending")

    # Transitional routing key. It remains named schema_name until all callers
    # move to the shared-schema Workspace slug contract.
    schema_name = models.CharField(max_length=63, unique=True, db_index=True)
    name = models.CharField(_("Name"), max_length=200, unique=True)
    theme = ColorField(default="#FF0000")
    logo = models.ImageField(upload_to="company_logos/", null=True, blank=True)
    members = models.ManyToManyField(
        User,
        through="Membership",
        through_fields=("company", "user"),
    )
    owner = models.ForeignKey(
        verbose_name=_("Owner"),
        to=User,
        related_name="owned_companies",
        on_delete=models.PROTECT,
    )
    creator = models.ForeignKey(
        verbose_name=_("Creator"),
        to=User,
        related_name="created_companies",
        on_delete=models.CASCADE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    lifecycle_state = models.CharField(
        max_length=20,
        choices=LifecycleState.choices,
        default=LifecycleState.ACTIVE,
        db_index=True,
    )
    lifecycle_changed_at = models.DateTimeField(default=timezone.now)
    lifecycle_reason = models.TextField(blank=True)

    objects = CompanyManager()  # Use custom manager
    all_objects = models.Manager()  # Include soft-deleted instances

    class Meta:
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
        return reverse("workspace_detail", kwargs={"workspace_id": self.id})

    @property
    def slug(self):
        """Compatibility routing slug during the schema-name rename."""

        return self.schema_name

    def delete(self, *args, **kwargs):
        """Physical erasure is not an ordinary model operation."""
        raise ValueError("Use the privileged retention workflow for Workspace erasure.")


class Domain(models.Model):
    domain = models.CharField(max_length=253, unique=True, db_index=True)
    tenant = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="domains",
    )
    is_primary = models.BooleanField(default=True, db_index=True)

    def __str__(self):
        return self.domain


class Membership(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="memberships",
        verbose_name=_("User"),
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="memberships",
        verbose_name=_("Company"),
    )
    role = models.ForeignKey(
        "Role",
        on_delete=models.CASCADE,
        related_name="memberships",
        verbose_name=_("Role"),
    )
    date_joined = models.DateTimeField(auto_now_add=True, verbose_name=_("Date joined"))
    invite_reason = models.CharField(
        max_length=64, blank=True, verbose_name=_("Invite reason")
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "company"],
                name="orgs_membership_unique_user_company",
            ),
        ]
        # permissions = [
        #     ("invite_to_company", "Can invite to company"),
        #     ("remove_from_company", "Can remove from company"),
        #     ("change_role", "Can change role"),

        # ]

    def __str__(self):
        return f"{self.user} as {self.role} in {self.company} since {self.date_joined}"


class Role(models.Model):
    name = models.CharField(_("name"), max_length=100, unique=True)
    permissions = models.ManyToManyField(
        Permission, blank=True, verbose_name=_("permissions")
    )

    class Meta:
        verbose_name = _("role")
        verbose_name_plural = _("roles")

    def __str__(self):
        return self.name


class CompanyInvitation(AbstractBaseInvitation):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"
        REVOKED = "revoked", "Revoked"

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="invitations",
        verbose_name=_("company"),
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name="invitations",
        verbose_name=_("role"),
    )
    email = models.EmailField(
        # unique=True,
        verbose_name=_("e-mail address"),
        max_length=app_settings.EMAIL_MAX_LENGTH,
    )
    created = models.DateTimeField(verbose_name=_("created"), default=timezone.now)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["email", "company"],
                name="orgs_companyinvitation_unique_email_company",
            ),
        ]

    @classmethod
    def pending_queryset(cls):
        return cls.objects.filter(status=cls.Status.PENDING, accepted=False)

    def lifecycle_state(self):
        if self.status == self.Status.PENDING and self.key_expired():
            return "expired"
        return self.status

    @property
    def is_pending(self):
        return self.lifecycle_state() == "pending"

    def mark_declined(self):
        self.accepted = False
        self.status = self.Status.DECLINED
        self.responded_at = timezone.now()
        self.save(update_fields=["accepted", "status", "responded_at"])

    def mark_revoked(self):
        self.accepted = False
        self.status = self.Status.REVOKED
        self.responded_at = timezone.now()
        self.save(update_fields=["accepted", "status", "responded_at"])

    @classmethod
    def create(cls, email, company, role, inviter=None, **kwargs):
        key = get_random_string(64).lower()
        try:
            with transaction.atomic():
                instance = cls._default_manager.create(
                    company=company,
                    role=role,
                    email=email,
                    key=key,
                    inviter=inviter,
                    **kwargs,
                )
        except IntegrityError:
            raise ValidationError("This email address is already invited for this company.")
        return instance

    def key_expired(self):
        if not self.sent:
            return False
        expiration_date = self.sent + datetime.timedelta(
            days=app_settings.INVITATION_EXPIRY,
        )
        return expiration_date <= timezone.now()

    def accept(self, *args, **kwargs):
        self.accepted = True
        self.status = self.Status.ACCEPTED
        self.responded_at = timezone.now()
        self.save(update_fields=["accepted", "status", "responded_at"])
        return self

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
        return f"Invited: {self.email} Status: {self.lifecycle_state()} "


from dynamic_preferences.models import PerInstancePreferenceModel


class CompanyPreferenceModel(PerInstancePreferenceModel):
    instance = models.ForeignKey(Company, on_delete=models.CASCADE)

    class Meta:
        app_label = "orgs"


# Import AuditLog model to make it discoverable by migrations
from apps.orgs.audit import AuditLog  # noqa: E402, F401
