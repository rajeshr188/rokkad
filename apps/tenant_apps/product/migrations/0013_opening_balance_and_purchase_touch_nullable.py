from django.db import migrations, models


def ensure_opening_balance_movement(apps, schema_editor):
    Movement = apps.get_model("product", "Movement")
    Movement.objects.update_or_create(
        id="OB",
        defaults={"name": "Opening Balance", "direction": "+"},
    )


def remove_opening_balance_movement(apps, schema_editor):
    Movement = apps.get_model("product", "Movement")
    Movement.objects.filter(id="OB").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("product", "0012_pr7_physical_audit_reconciliation"),
    ]

    operations = [
        migrations.AlterField(
            model_name="stock",
            name="purchase_touch",
            field=models.DecimalField(
                max_digits=10,
                decimal_places=3,
                null=True,
                blank=True,
            ),
        ),
        migrations.AlterField(
            model_name="stockitem",
            name="purchase_touch",
            field=models.DecimalField(
                max_digits=10,
                decimal_places=3,
                null=True,
                blank=True,
            ),
        ),
        migrations.RunPython(
            ensure_opening_balance_movement,
            remove_opening_balance_movement,
        ),
    ]
