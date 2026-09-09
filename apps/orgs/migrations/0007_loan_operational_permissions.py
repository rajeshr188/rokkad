from django.db import migrations


def add_permissions(apps, schema_editor):
    content_type, _ = apps.get_model("contenttypes", "ContentType").objects.get_or_create(app_label="orgs", model="company")
    for code, name in (
        ("loan_repay", "Can record loan repayments"),
        ("loan_release", "Can release loan collateral"),
        ("loan_accrue", "Can finalize loan interest"),
        ("loan_capitalize", "Can capitalize loan interest"),
    ):
        apps.get_model("auth", "Permission").objects.get_or_create(
            content_type=content_type, codename=code, defaults={"name": name},
        )


class Migration(migrations.Migration):
    dependencies = [("orgs", "0006_company_loan_workflow")]
    operations = [migrations.RunPython(add_permissions, migrations.RunPython.noop)]
