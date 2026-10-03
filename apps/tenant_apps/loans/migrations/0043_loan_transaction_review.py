import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from apps.tenancy.rls import EnableWorkspaceRLS


class Migration(migrations.Migration):
    dependencies = [("loans", "0042_archive_admission_link"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name="LoanTransactionReview", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("through_date", models.DateField()),
            ("confirmed_complete", models.BooleanField()),
            ("source_reference", models.CharField(max_length=500)),
            ("source_fingerprint", models.CharField(max_length=64)),
            ("request_key", models.CharField(max_length=120)),
            ("reviewed_at", models.DateTimeField(auto_now_add=True)),
            ("loan", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="transaction_reviews", to="loans.pawnloan")),
            ("reviewed_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL)),
            ("workspace", models.ForeignKey(editable=False, on_delete=django.db.models.deletion.PROTECT, related_name="+", to="orgs.company")),
        ], options={"ordering": ("loan_id", "id"), "constraints": [models.UniqueConstraint(fields=("loan", "request_key"), name="loans_tx_review_request_unique")]}),
        EnableWorkspaceRLS("LoanTransactionReview"),
        migrations.RunSQL("""
CREATE FUNCTION loans_transaction_review_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'Transaction reviews are immutable'; END IF;
 IF NEW.source_fingerprint !~ '^[0-9a-f]{64}$' OR btrim(NEW.source_reference) = '' OR btrim(NEW.request_key) = ''
 OR NOT EXISTS (SELECT 1 FROM loans_pawnloan l WHERE l.id=NEW.loan_id AND l.workspace_id=NEW.workspace_id
   AND l.state IN ('ACTIVE','CLOSED') AND NEW.through_date >= l.loan_date)
 THEN RAISE EXCEPTION 'Invalid transaction review binding'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER loans_transaction_review_guard BEFORE INSERT OR UPDATE OR DELETE ON loans_loantransactionreview
FOR EACH ROW EXECUTE FUNCTION loans_transaction_review_guard();
""", "DROP TRIGGER loans_transaction_review_guard ON loans_loantransactionreview; DROP FUNCTION loans_transaction_review_guard();"),
    ]
