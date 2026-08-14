from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("dea", "0041_alter_businesseventdraft_event_type"),
    ]

    operations = [
        migrations.AlterField(
            model_name="businesseventdraft",
            name="event_type",
            field=models.CharField(
                choices=[
                    ("FIXED_PURCHASE", "Fixed purchase"),
                    ("UNFIXED_PURCHASE", "Unfixed purchase"),
                    ("PURCHASE_RATE_FIXING", "Purchase rate fixing"),
                    ("FIXED_SALE", "Fixed sale"),
                    ("UNFIXED_SALE", "Unfixed sale"),
                    ("SALE_RATE_FIXING", "Sale rate fixing"),
                    ("CUSTOMER_RECEIPT", "Customer receipt"),
                    ("SUPPLIER_PAYMENT", "Supplier payment"),
                ],
                max_length=32,
            ),
        ),
    ]
