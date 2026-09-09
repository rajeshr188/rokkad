from django.db import migrations, models


def permissions(apps, schema_editor):
    content_type, _ = apps.get_model("contenttypes", "ContentType").objects.get_or_create(
        app_label="orgs", model="company",
    )
    for code, name in (("loan_approve", "Can approve loans"), ("loan_disburse", "Can disburse loans")):
        apps.get_model("auth", "Permission").objects.get_or_create(
            content_type=content_type, codename=code, defaults={"name": name},
        )


class Migration(migrations.Migration):
    dependencies = [("orgs", "0005_company_immutable_slug"), ("auth", "0012_alter_user_first_name_max_length")]
    operations = [
        migrations.AddField(
            model_name="company", name="loan_workflow",
            field=models.CharField(max_length=10, default="EXTENDED", choices=[
                ("EXTENDED", "Separate approval and disbursal"), ("SIMPLE", "Owner review and disburse"),
            ]),
        ),
        migrations.RunPython(permissions, migrations.RunPython.noop),
    ]
