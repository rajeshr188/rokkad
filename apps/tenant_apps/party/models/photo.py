"""Private customer photographs; Party.profile_photo selects the default."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from apps.tenancy.models import WorkspaceOwnedModel
from .party import party_profile_photo_upload_to


class PartyPhoto(WorkspaceOwnedModel):
    party = models.ForeignKey("party.Party", on_delete=models.CASCADE, related_name="photos")
    file = models.ImageField(upload_to=party_profile_photo_upload_to)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ("pk",)
        constraints = [models.UniqueConstraint(fields=("party", "file"), name="party_photo_file_uniq")]

    def save(self, *args, **kwargs):
        if self.workspace_id is not None and self.workspace_id != self.party.workspace_id:
            raise ValidationError("Photo must belong to the customer's Workspace.")
        self.workspace_id = self.party.workspace_id
        super().save(*args, **kwargs)
