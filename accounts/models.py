from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


class CustomUser(AbstractUser):
    workspace = models.ForeignKey(
        "orgs.Company",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        default=None,
        verbose_name=_("Workspace"),
    )

    def __str__(self):
        return self.email
