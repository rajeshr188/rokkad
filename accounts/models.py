from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    workspace = models.ForeignKey(
        'orgs.Company', on_delete=models.CASCADE, 
        null=True, blank=True,default=None
        )

    def __str__(self):
        return self.email