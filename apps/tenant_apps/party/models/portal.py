from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class PartyPortalAccess(models.Model):
    class Status(models.TextChoices):
        INVITED = "INVITED", _("Invited")
        ACTIVE = "ACTIVE", _("Active")
        SUSPENDED = "SUSPENDED", _("Suspended")
        REVOKED = "REVOKED", _("Revoked")

    party = models.ForeignKey(
        "party.Party",
        on_delete=models.PROTECT,
        related_name="portal_access_grants",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="party_portal_access_grants",
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.INVITED,
        db_index=True,
    )
    invited_at = models.DateTimeField(default=timezone.now)
    activated_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("party", "user", "status")
        constraints = [
            models.UniqueConstraint(
                fields=["party", "user"],
                condition=models.Q(status__in=["INVITED", "ACTIVE", "SUSPENDED"]),
                name="party_one_live_portal_access_per_user_party",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["party", "status"]),
        ]
        verbose_name = _("Party Portal Access")
        verbose_name_plural = _("Party Portal Access Grants")

    def __str__(self):
        return f"{self.user} -> {self.party} ({self.status})"

    def activate(self, *, save=True):
        self.status = self.Status.ACTIVE
        if not self.activated_at:
            self.activated_at = timezone.now()
        if save:
            self.save(update_fields=["status", "activated_at", "updated_at"])
        return self

    def revoke(self, *, save=True):
        self.status = self.Status.REVOKED
        self.revoked_at = timezone.now()
        if save:
            self.save(update_fields=["status", "revoked_at", "updated_at"])
        return self
