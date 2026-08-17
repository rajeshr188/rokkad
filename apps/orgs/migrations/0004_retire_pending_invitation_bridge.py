from django.db import migrations


def reconcile_pending_bridge(apps, schema_editor):
    PendingInvitation = apps.get_model("orgs", "PendingInvitation")
    CompanyInvitation = apps.get_model("orgs", "CompanyInvitation")

    for pending in PendingInvitation.objects.all().iterator():
        invitation = (
            CompanyInvitation.objects.filter(
                company_id=pending.company_id,
                email__iexact=pending.email,
            )
            .order_by("-created")
            .first()
        )
        if invitation is None:
            raise RuntimeError(
                "Cannot retire orphan PendingInvitation "
                f"{pending.pk}; restore its CompanyInvitation first."
            )
        invitation.role_id = pending.role_id
        invitation.accepted = False
        invitation.status = "pending"
        invitation.responded_at = None
        invitation.save(
            update_fields=["role", "accepted", "status", "responded_at"]
        )


class Migration(migrations.Migration):
    dependencies = [("orgs", "0003_workspace_operational_lifecycle")]

    operations = [
        migrations.RunPython(reconcile_pending_bridge, migrations.RunPython.noop),
        migrations.DeleteModel(name="PendingInvitation"),
    ]
