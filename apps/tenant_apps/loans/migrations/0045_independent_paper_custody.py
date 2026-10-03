from django.db import migrations, models


CHOICES = [(value, value.replace("_", " ").title()) for value in (
    "IN_VAULT", "WITH_CUSTOMER", "WITH_FUNDING_LENDER", "AUCTION_DISPOSED",
    "RENEWAL_TRANSFERRED", "RENEWAL_REVERSED", "PAPER_CLOSED",
)]


class Migration(migrations.Migration):
    dependencies = [("loans", "0044_notice_transaction_review")]
    operations = [
        migrations.AlterField(model_name="pawncollateralitem", name="custody_state",
            field=models.CharField(choices=CHOICES, default="IN_VAULT", max_length=32, db_index=True)),
        migrations.AlterField(model_name="pawncollateralcustodyevent", name="from_state",
            field=models.CharField(choices=CHOICES, max_length=32)),
        migrations.AlterField(model_name="pawncollateralcustodyevent", name="to_state",
            field=models.CharField(choices=CHOICES, max_length=32)),
    ]
