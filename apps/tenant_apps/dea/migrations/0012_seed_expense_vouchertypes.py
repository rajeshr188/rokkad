from django.db import migrations

def seed_expense_vouchertypes(apps, schema_editor):
    VoucherType = apps.get_model("dea", "VoucherType")
    seeds = [
        ("EXPENSE_EMP_CLAIM", "Expense voucher for employee claims (reimbursements)"),
        ("EXPENSE_VENDOR_BILL", "Expense voucher for vendor bills (accounts payable)"),
        ("EXPENSE_DIRECT_PAYMENT", "Expense voucher for direct payments/cash expenses"),
        ("EXPENSE_REIMBURSEMENT", "Expense voucher for reimbursement requests"),
        ("EXPENSE_OTHER", "Expense voucher for other miscellaneous expenses"),
    ]
    for name, description in seeds:
        VoucherType.objects.update_or_create(
            name=name,
            defaults={"description": description},
        )

def unseed_expense_vouchertypes(apps, schema_editor):
    VoucherType = apps.get_model("dea", "VoucherType")
    VoucherType.objects.filter(name__in=[
        "EXPENSE_EMP_CLAIM",
        "EXPENSE_VENDOR_BILL",
        "EXPENSE_DIRECT_PAYMENT",
        "EXPENSE_REIMBURSEMENT",
        "EXPENSE_OTHER",
    ]).delete()

class Migration(migrations.Migration):
    dependencies = [
        ("dea", "0011_vouchernumbersequence"),
    ]
    operations = [
        migrations.RunPython(seed_expense_vouchertypes, reverse_code=unseed_expense_vouchertypes),
    ]
