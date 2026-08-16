from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from apps.tenancy.models import WorkspaceOwnedModel


class PartyRelationship(WorkspaceOwnedModel):
    class RelationshipType(models.TextChoices):
        CONTACT_PERSON = "CONTACT_PERSON", _("Contact Person")
        EMPLOYER = "EMPLOYER", _("Employer")
        EMPLOYEE = "EMPLOYEE", _("Employee")
        BROKER = "BROKER", _("Broker")
        AGENT = "AGENT", _("Agent")
        RELATED_BUSINESS = "RELATED_BUSINESS", _("Related Business")
        FAMILY = "FAMILY", _("Family")
        OTHER = "OTHER", _("Other")

    from_party = models.ForeignKey(
        "party.Party",
        on_delete=models.CASCADE,
        related_name="relationships_from",
    )
    to_party = models.ForeignKey(
        "party.Party",
        on_delete=models.CASCADE,
        related_name="relationships_to",
    )
    relationship_type = models.CharField(
        max_length=32,
        choices=RelationshipType.choices,
    )
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("from_party", "to_party", "relationship_type")
        constraints = [
            models.UniqueConstraint(
                fields=["from_party", "to_party", "relationship_type"],
                name="party_relationship_uniq",
            ),
            models.CheckConstraint(
                condition=~models.Q(from_party=models.F("to_party")),
                name="party_relationship_not_self",
            ),
        ]
        indexes = [
            models.Index(fields=["from_party", "relationship_type"]),
            models.Index(fields=["to_party", "relationship_type"]),
        ]
        verbose_name = _("Party Relationship")
        verbose_name_plural = _("Party Relationships")

    def __str__(self):
        return f"{self.from_party} -> {self.to_party} ({self.relationship_type})"

    def save(self, *args, **kwargs):
        if self.from_party.workspace_id != self.to_party.workspace_id:
            raise ValidationError("Related Parties must belong to the same Workspace.")
        self.workspace_id = self.from_party.workspace_id
        super().save(*args, **kwargs)
