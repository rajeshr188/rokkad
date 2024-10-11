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
    profile_picture = models.ImageField(
        upload_to="profile_pictures/", null=True, blank=True
    )
    social_profile_picture = models.URLField(max_length=200, null=True, blank=True)

    def __str__(self):
        return self.email

    def set_workspace(self, workspace):
        self.workspace = workspace
        self.save()

    # def delete(self, *args, **kwargs):
    #     for tenant in self.memberships.all():
    #         with tenant_context(tenant.company.schema_name):
    #             # Handle deletion in tenant schema
    #             # Replace 'MyModel' and 'created_by' with your model and field names

    #             # MyModel.objects.filter(created_by=self).update(created_by=None)
    #             self.customers_created.all().update(created_by=None)
    #             self.loans_created.all().update(created_by=None)
    #             self.loan_payments_created.all().update(created_by=None)
    #             self.loans_statements_created.all().update(created_by=None)
    #             self.releases_created.all().update(created_by=None)

    #     super().delete(*args, **kwargs)


class UserProfile(models.Model):
    user = models.OneToOneField(
        CustomUser, on_delete=models.CASCADE, related_name="profile"
    )
    workspace = models.ForeignKey(
        "orgs.Company",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=None,
        verbose_name=_("Workspace"),
    )
    timezone = models.CharField(
        max_length=63, null=True, blank=True, default="Asia/Kolkata"
    )
    profile_picture = models.ImageField(
        upload_to="profile_pictures/", null=True, blank=True
    )
    social_profile_picture = models.URLField(max_length=200, null=True, blank=True)
    phone_number = models.CharField(max_length=15, null=True, blank=True)
    address = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"Profile for {self.user.email}"

    # def delete(self, *args, **kwargs):
    #     self.user.delete()
    #     super().delete(*args, **kwargs)

    def set_workspace(self, workspace):
        self.workspace = workspace
        self.save()
