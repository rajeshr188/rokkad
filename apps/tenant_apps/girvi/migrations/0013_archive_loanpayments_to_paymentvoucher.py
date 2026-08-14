"""Retained migration node after removal of obsolete LoanPayment archival."""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        # Last girvi migration
        ("girvi", "0012_remove_loanitem_pic_field"),
        # DEA PaymentVoucher must exist
        ("dea", "0010_seed_girvi_release_vouchertype"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = []
