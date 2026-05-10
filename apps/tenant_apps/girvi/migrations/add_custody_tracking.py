"""
Django migration to add custody tracking to LoanItem.

Run this migration to:
1. Add custody_status, repledged_to, repledged_amount, repledged_at to LoanItem
2. Create RepledgeHistory model
3. Migrate existing RepledgedLoanItem data
4. Keep RepledgedLoanItem for backward compatibility (mark as read-only)

Usage:
    python manage.py makemigrations girvi --name add_custody_tracking
    python manage.py migrate girvi
"""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def migrate_repledged_items_forward(apps, schema_editor):
    """
    Migrate existing RepledgedLoanItem records to new custody system.
    """
    # Some legacy tenant schemas never had this table. Skip safely.
    if "girvi_repledgedloanitem" not in schema_editor.connection.introspection.table_names():
        return

    LoanItem = apps.get_model("girvi", "LoanItem")
    RepledgedLoanItem = apps.get_model("girvi", "RepledgedLoanItem")
    RepledgeHistory = apps.get_model("girvi", "RepledgeHistory")

    migrated = 0
    skipped = 0

    for repledge in RepledgedLoanItem.objects.all():
        item = repledge.original_loanitem

        # Update item custody
        item.custody_status = "with_lender"
        item.repledged_to = repledge.loan
        item.repledged_amount = repledge.repledged_loanamount
        item.repledged_at = repledge.repledged_date
        item.save()

        # Create history record
        RepledgeHistory.objects.create(
            loan_item=item,
            taken_loan=repledge.loan,
            repledged_amount=repledge.repledged_loanamount,
            item_value_at_repledge=repledge.repledged_loanamount,  # Approximate
            repledged_at=repledge.repledged_date,
            notes="Migrated from RepledgedLoanItem",
        )

        migrated += 1

    print(f"Migrated {migrated} repledged items, skipped {skipped}")


def migrate_repledged_items_reverse(apps, schema_editor):
    """
    Reverse migration - restore old RepledgedLoanItem state.
    """
    LoanItem = apps.get_model("girvi", "LoanItem")

    # Reset all items to in_vault
    LoanItem.objects.update(
        custody_status="in_vault",
        repledged_to=None,
        repledged_amount=None,
        repledged_at=None,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("girvi", "0003_loan_auto_post_to_accounting_loan_updated_by_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Add custody tracking fields to LoanItem
        migrations.AddField(
            model_name="loanitem",
            name="custody_status",
            field=models.CharField(
                choices=[
                    ("in_vault", "In Our Vault"),
                    ("with_lender", "Pledged to Lender"),
                    ("with_customer", "Released to Customer"),
                ],
                default="in_vault",
                max_length=20,
                help_text="Current physical location of item",
                db_index=True,
            ),
        ),
        migrations.AddField(
            model_name="loanitem",
            name="repledged_to",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="collateral_items",
                to="girvi.loan",
                help_text="Active repledge - item is currently with this lender",
            ),
        ),
        migrations.AddField(
            model_name="loanitem",
            name="repledged_amount",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=10,
                null=True,
                help_text="Amount borrowed using this item as collateral",
            ),
        ),
        migrations.AddField(
            model_name="loanitem",
            name="repledged_at",
            field=models.DateTimeField(
                blank=True, null=True, help_text="When item was most recently repledged"
            ),
        ),
        # Create RepledgeHistory model
        migrations.CreateModel(
            name="RepledgeHistory",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "repledged_amount",
                    models.DecimalField(
                        decimal_places=2,
                        help_text="Amount borrowed using this item as collateral",
                        max_digits=10,
                    ),
                ),
                (
                    "item_value_at_repledge",
                    models.DecimalField(
                        decimal_places=2,
                        help_text="Market value of item when repledged",
                        max_digits=10,
                    ),
                ),
                (
                    "repledged_at",
                    models.DateTimeField(
                        auto_now_add=True, help_text="When item was given to lender"
                    ),
                ),
                (
                    "returned_at",
                    models.DateTimeField(
                        blank=True,
                        help_text="When item was returned to our vault",
                        null=True,
                    ),
                ),
                (
                    "notes",
                    models.TextField(blank=True, help_text="Notes when repledging"),
                ),
                (
                    "return_notes",
                    models.TextField(blank=True, help_text="Notes when returning"),
                ),
                (
                    "loan_item",
                    models.ForeignKey(
                        help_text="The item that was repledged",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="repledge_history",
                        to="girvi.loanitem",
                    ),
                ),
                (
                    "repledged_by",
                    models.ForeignKey(
                        help_text="User who repledged the item",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="repledges_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "returned_by",
                    models.ForeignKey(
                        blank=True,
                        help_text="User who returned the item",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="repledges_returned",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "taken_loan",
                    models.ForeignKey(
                        help_text="The TakenLoan where this item was used as collateral",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="repledge_history_items",
                        to="girvi.loan",
                    ),
                ),
            ],
            options={
                "verbose_name": "Repledge History",
                "verbose_name_plural": "Repledge Histories",
                "ordering": ["-repledged_at"],
            },
        ),
        # Add indexes for RepledgeHistory
        migrations.AddIndex(
            model_name="repledgehistory",
            index=models.Index(
                fields=["loan_item", "repledged_at"], name="girvi_repl_loan_it_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="repledgehistory",
            index=models.Index(
                fields=["taken_loan", "repledged_at"], name="girvi_repl_taken_l_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="repledgehistory",
            index=models.Index(fields=["returned_at"], name="girvi_repl_returne_idx"),
        ),
        # Migrate existing data
        migrations.RunPython(
            migrate_repledged_items_forward, migrate_repledged_items_reverse
        ),
    ]
