from django.db import migrations


def seed_girvi_payment_vouchertypes(apps, schema_editor):
    VoucherType = apps.get_model("dea", "VoucherType")

    seeds = [
        (
            "GIVENLOAN_RECEIPT",
            "GivenLoan repayment receipt (cash received from borrower)",
        ),
        (
            "GIVENLOAN_PAYMENT",
            "GivenLoan disbursal payment (cash paid to borrower)",
        ),
        (
            "TAKENLOAN_RECEIPT",
            "TakenLoan disbursal receipt (cash received from lender)",
        ),
        (
            "TAKENLOAN_PAYMENT",
            "TakenLoan repayment payment (cash paid to lender)",
        ),
    ]

    for name, description in seeds:
        VoucherType.objects.update_or_create(
            name=name,
            defaults={"description": description},
        )


def unseed_girvi_payment_vouchertypes(apps, schema_editor):
    VoucherType = apps.get_model("dea", "VoucherType")
    VoucherType.objects.filter(
        name__in=[
            "GIVENLOAN_RECEIPT",
            "GIVENLOAN_PAYMENT",
            "TAKENLOAN_RECEIPT",
            "TAKENLOAN_PAYMENT",
        ]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("dea", "0008_alter_purchaseinvoicevoucher_vendor"),
    ]

    operations = [
        migrations.RunPython(
            seed_girvi_payment_vouchertypes,
            reverse_code=unseed_girvi_payment_vouchertypes,
        ),
    ]
