from django.db import migrations

def seed_expense_ledgers(apps, schema_editor):
    # Expense ledger seeding is now handled by the unified fixture in 0020_seed_all_initial_data.py
    pass

def unseed_expense_ledgers(apps, schema_editor):
    Ledger = apps.get_model("dea", "Ledger")
    Ledger.objects.filter(
        name__in=[
            "Travel & Transportation",
            "Food & Meals",
            "Accommodation",
            "Professional Services",
            "Office & Supplies",
            "Utilities & Communications",
            "Maintenance & Repair",
            "Marketing & Advertising",
            "Other Expense",
        ]
    ).delete()

class Migration(migrations.Migration):
    dependencies = [
        ("dea", "0013_ledgercodesequence"),
    ]
    operations = [
        migrations.RunPython(seed_expense_ledgers, reverse_code=unseed_expense_ledgers),
    ]
