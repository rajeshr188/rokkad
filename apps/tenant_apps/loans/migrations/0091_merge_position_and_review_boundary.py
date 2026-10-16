"""Merge independent notice-position and book-review checkpoint guards."""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("loans", "0090_recorded_position_notice"),
        ("loans", "0090_transaction_review_history_boundary"),
    ]
    operations = []
