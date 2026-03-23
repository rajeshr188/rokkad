from django.db import migrations


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
        migrations.RunPython(
            seed_girvi_release_vouchertype,
            reverse_code=unseed_girvi_release_vouchertype,
        ),
    ]
