from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("loans", "0003_alter_loanchangelog_event_kind"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PawnLoanAccountingEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_kind", models.CharField(choices=[("DISBURSAL", "Disbursal"), ("REPAYMENT", "Repayment"), ("INTEREST_ACCRUAL", "Interest Accrual"), ("INTEREST_CAPITALIZATION", "Interest Capitalization"), ("RELEASE_RECEIPT", "Release Receipt"), ("REVERSAL", "Reversal")], max_length=32)),
                ("effective_date", models.DateField(db_index=True)),
                ("payload", models.JSONField()),
                ("payload_fingerprint", models.CharField(max_length=64)),
                ("idempotency_key", models.CharField(max_length=180, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="pawn_loan_accounting_events", to=settings.AUTH_USER_MODEL)),
                ("loan", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="accounting_events", to="loans.pawnloan")),
            ],
            options={"ordering": ("loan_id", "created_at", "id")},
        ),
        migrations.CreateModel(
            name="PawnLoanAccountingOutbox",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("idempotency_key", models.CharField(max_length=180, unique=True)),
                ("payload", models.JSONField()),
                ("payload_fingerprint", models.CharField(max_length=64)),
                ("contract_version", models.PositiveSmallIntegerField(default=1)),
                ("status", models.CharField(choices=[("PENDING", "Pending"), ("PROCESSING", "Processing"), ("POSTED", "Posted"), ("FAILED", "Failed")], db_index=True, default="PENDING", max_length=16)),
                ("attempt_count", models.PositiveIntegerField(default=0)),
                ("available_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("claimed_at", models.DateTimeField(blank=True, null=True)),
                ("delivered_at", models.DateTimeField(blank=True, null=True)),
                ("last_error", models.TextField(blank=True, default="")),
                ("dea_voucher_id", models.PositiveBigIntegerField(blank=True, null=True)),
                ("dea_journal_entry_id", models.PositiveBigIntegerField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("event", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="outbox", to="loans.pawnloanaccountingevent")),
            ],
            options={"ordering": ("id",)},
        ),
        migrations.AddIndex(model_name="pawnloanaccountingevent", index=models.Index(fields=["loan", "event_kind", "effective_date"], name="loans_acct_event_lookup_idx")),
        migrations.AddIndex(model_name="pawnloanaccountingoutbox", index=models.Index(fields=["status", "available_at"], name="loans_outbox_due_idx")),
    ]
