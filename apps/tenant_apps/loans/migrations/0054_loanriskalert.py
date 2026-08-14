from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("loans", "0053_loanrisksnapshot_source_provenance")]

    operations = [
        migrations.CreateModel(
            name="LoanRiskAlert",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("alert_kind", models.CharField(choices=[("DPD_WORSENING", "Worsening delinquency"), ("LTV_BREACH", "LTV breach"), ("MATURITY", "Maturity attention"), ("ASSESSMENT_FAILURE", "Assessment failure")], max_length=24)),
                ("severity", models.CharField(max_length=16)),
                ("message", models.CharField(max_length=500)),
                ("recommended_action", models.CharField(max_length=255)),
                ("status", models.CharField(choices=[("OPEN", "Open"), ("RESOLVED", "Resolved")], db_index=True, default="OPEN", max_length=12)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("loan", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="risk_alerts", to="loans.pawnloan")),
                ("resolved_by_event", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="resolved_operational_alerts", to="loans.loanriskevent")),
                ("source_event", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="operational_alerts", to="loans.loanriskevent")),
                ("workspace", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="loan_risk_alerts", to="orgs.company")),
            ],
            options={"ordering": ("-created_at", "-pk")},
        ),
        migrations.AddConstraint(
            model_name="loanriskalert",
            constraint=models.UniqueConstraint(fields=("source_event", "alert_kind"), name="loans_risk_alert_event_kind_uniq"),
        ),
        migrations.AddConstraint(
            model_name="loanriskalert",
            constraint=models.UniqueConstraint(condition=models.Q(("status", "OPEN")), fields=("workspace", "loan", "alert_kind"), name="loans_risk_alert_one_open_kind"),
        ),
        migrations.AddIndex(
            model_name="loanriskalert",
            index=models.Index(fields=["workspace", "status", "severity"], name="loans_risk_alert_work_idx"),
        ),
    ]
