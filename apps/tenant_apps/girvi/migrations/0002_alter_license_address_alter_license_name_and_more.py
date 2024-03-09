# Generated by Django 5.0.1 on 2024-02-26 08:35

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("contact", "0002_alter_address_customer_alter_address_area_and_more"),
        ("girvi", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="license",
            name="address",
            field=models.TextField(max_length=100, verbose_name="Address"),
        ),
        migrations.AlterField(
            model_name="license",
            name="name",
            field=models.CharField(max_length=255, verbose_name="Name"),
        ),
        migrations.AlterField(
            model_name="license",
            name="propreitor",
            field=models.CharField(max_length=30, verbose_name="Propreitor"),
        ),
        migrations.AlterField(
            model_name="license",
            name="shopname",
            field=models.CharField(max_length=30, verbose_name="Shop Name"),
        ),
        migrations.AlterField(
            model_name="license",
            name="type",
            field=models.CharField(
                choices=[
                    ("PBL", "Pawn Brokers License"),
                    ("GST", "Goods & Service Tax"),
                ],
                default="PBL",
                max_length=30,
                verbose_name="Type",
            ),
        ),
        migrations.AlterField(
            model_name="loan",
            name="loan_date",
            field=models.DateTimeField(
                default=django.utils.timezone.now, verbose_name="Loan Date"
            ),
        ),
        migrations.AlterField(
            model_name="loan",
            name="series",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to="girvi.series",
                verbose_name="Series",
            ),
        ),
        migrations.AlterField(
            model_name="release",
            name="created_by",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="created_releases",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Created By",
            ),
        ),
        migrations.AlterField(
            model_name="release",
            name="release_id",
            field=models.CharField(
                blank=True,
                max_length=255,
                null=True,
                unique=True,
                verbose_name="Release ID",
            ),
        ),
        migrations.AlterField(
            model_name="release",
            name="released_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="released_by",
                to="contact.customer",
                verbose_name="Released By",
            ),
        ),
        migrations.AlterField(
            model_name="series",
            name="is_active",
            field=models.BooleanField(default=True, verbose_name="Is Active"),
        ),
        migrations.AlterField(
            model_name="series",
            name="license",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to="girvi.license",
                verbose_name="License",
            ),
        ),
        migrations.AlterField(
            model_name="series",
            name="name",
            field=models.CharField(
                blank=True,
                default="",
                max_length=30,
                unique=True,
                verbose_name="Series Name",
            ),
        ),
    ]