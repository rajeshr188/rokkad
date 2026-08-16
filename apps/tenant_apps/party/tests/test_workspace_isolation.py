from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.tenant_apps.party.models import (
    Party,
    PartyRelationship,
    PartyRole,
    PartyRoleType,
)


class PartyWorkspaceIsolationTests(SimpleTestCase):
    def test_root_party_rejects_conflicting_active_workspace(self):
        party = Party(workspace_id=2, display_name="Borrower", party_code="P-1")

        with (
            patch("apps.tenancy.models.current_workspace_id", return_value=1),
            self.assertRaises(ValidationError),
        ):
            party.save()

    def test_relationship_rejects_cross_workspace_parties(self):
        relationship = PartyRelationship(
            from_party=Party(id=1, workspace_id=1),
            to_party=Party(id=2, workspace_id=2),
            relationship_type=PartyRelationship.RelationshipType.FAMILY,
        )

        with self.assertRaises(ValidationError):
            relationship.save()

    def test_role_rejects_cross_workspace_role_type(self):
        role = PartyRole(
            party=Party(id=1, workspace_id=1),
            role_type=PartyRoleType(id=1, workspace_id=2, key="BORROWER"),
        )

        with self.assertRaises(ValidationError):
            role.save()
