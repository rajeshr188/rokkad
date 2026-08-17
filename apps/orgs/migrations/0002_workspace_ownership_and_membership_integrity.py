import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def reconcile_workspace_authority(apps, schema_editor):
    Company = apps.get_model("orgs", "Company")
    Membership = apps.get_model("orgs", "Membership")
    Role = apps.get_model("orgs", "Role")

    owner_role, _ = Role.objects.get_or_create(name="Owner")
    member_role, _ = Role.objects.get_or_create(name="Member")
    admin_role, _ = Role.objects.get_or_create(name="Admin")

    Membership.objects.filter(role__isnull=True).update(role=member_role)
    for workspace in Company.objects.all().iterator():
        owner_membership, _ = Membership.objects.get_or_create(
            company_id=workspace.pk,
            user_id=workspace.owner_id,
            defaults={"role": owner_role, "invite_reason": "owner_reconciliation"},
        )
        if owner_membership.role_id != owner_role.pk:
            owner_membership.role_id = owner_role.pk
            owner_membership.save(update_fields=["role"])
        Membership.objects.filter(
            company_id=workspace.pk,
            role_id=owner_role.pk,
        ).exclude(user_id=workspace.owner_id).update(role=admin_role)


class Migration(migrations.Migration):
    # PostgreSQL cannot alter Membership while deferred FK events created by
    # the reconciliation update remain pending in the same transaction.
    # Operation-boundary commits preserve rollback per operation and let the
    # following constraint change run safely.
    atomic = False

    dependencies = [("orgs", "0001_initial")]

    operations = [
        migrations.RunPython(reconcile_workspace_authority, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="company",
            name="owner",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="owned_companies",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Owner",
            ),
        ),
        migrations.AlterField(
            model_name="membership",
            name="role",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="memberships",
                to="orgs.role",
                verbose_name="Role",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="companyownership",
            name="orgs_companyownership_unique_user_company",
        ),
        migrations.DeleteModel(name="CompanyOwnership"),
    ]
