from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("loans", "0018_owner_attested_continuation")]

    operations = [
        migrations.AlterField(
            model_name="loannumbersequence",
            name="prefix",
            field=models.CharField(blank=True, max_length=24),
        ),
    ]
