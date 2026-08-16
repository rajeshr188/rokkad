from django.db import migrations

from apps.tenancy.rls import EnableWorkspaceRLS


class Migration(migrations.Migration):
    dependencies = [
        ("party", "0008_alter_party_workspace_alter_partyaddress_workspace_and_more"),
    ]

    operations = [
        EnableWorkspaceRLS("Party"),
        EnableWorkspaceRLS("PartyAddress"),
        EnableWorkspaceRLS("PartyCodeSequence"),
        EnableWorkspaceRLS("PartyContactMethod"),
        EnableWorkspaceRLS("PartyDocument"),
        EnableWorkspaceRLS("PartyIdentifier"),
        EnableWorkspaceRLS("PartyPortalAccess"),
        EnableWorkspaceRLS("PartyRelationship"),
        EnableWorkspaceRLS("PartyRole"),
        EnableWorkspaceRLS("PartyRoleType"),
    ]
