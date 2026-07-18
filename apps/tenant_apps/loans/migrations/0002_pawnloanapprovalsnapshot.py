from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("loans", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PawnLoanApprovalSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("version", models.PositiveIntegerField()),
                ("payload", models.JSONField()),
                ("fingerprint", models.CharField(max_length=64)),
                ("approved_at", models.DateTimeField(auto_now_add=True)),
                ("approved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="pawn_loan_approvals", to=settings.AUTH_USER_MODEL)),
                ("loan", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="approval_snapshots", to="loans.pawnloan")),
            ],
            options={"ordering": ("loan_id", "version")},
        ),
        migrations.AddConstraint(
            model_name="pawnloanapprovalsnapshot",
            constraint=models.UniqueConstraint(fields=("loan", "version"), name="loans_approval_loan_version_uniq"),
        ),
        migrations.AddConstraint(
            model_name="pawnloanapprovalsnapshot",
            constraint=models.CheckConstraint(condition=models.Q(("version__gt", 0)), name="loans_approval_version_positive"),
        ),
    ]
