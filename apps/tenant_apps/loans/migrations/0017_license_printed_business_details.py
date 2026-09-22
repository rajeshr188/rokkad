from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("loans", "0016_document_source_snapshot")]

    operations = [
        migrations.AddField(
            model_name="loanlicense", name="business_name",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="loanlicense", name="business_address",
            field=models.TextField(blank=True, default="", max_length=1000),
        ),
        migrations.AddField(
            model_name="loanlicenserevision", name="business_name",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="loanlicenserevision", name="business_address",
            field=models.TextField(blank=True, default="", max_length=1000),
        ),
    ]
