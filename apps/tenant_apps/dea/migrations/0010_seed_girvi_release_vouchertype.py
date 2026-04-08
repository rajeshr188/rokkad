from django.db import migrations


def noop_forward(apps, schema_editor):
    # Seed moved to apps.orgs.management.commands.seed_tenant_defaults.
    pass


def seed_girvi_release_vouchertype(apps, schema_editor):
    VoucherType = apps.get_model("dea", "VoucherType")
    VoucherType.objects.update_or_create(
        name="GIVENLOAN_RELEASE",
        defaults={
            "description": "GivenLoan release write-off / closure entry",
        },
    )


def unseed_girvi_release_vouchertype(apps, schema_editor):
    VoucherType = apps.get_model("dea", "VoucherType")
    VoucherType.objects.filter(name="GIVENLOAN_RELEASE").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("dea", "0009_seed_girvi_payment_vouchertypes"),
    ]

    operations = [
        migrations.RunPython(noop_forward, reverse_code=migrations.RunPython.noop),
    ]
