"""Preflight retained links; protect risk evidence without freezing projections."""
from django.db import migrations, models


# Also used by the owner-only read-only command: inspect exactly this upgrade.
REFERENCE_CHECKS = (
    ("SNAPSHOT_LOAN_SCOPE", """
        SELECT count(*) FROM loans_loanrisksnapshot s
        LEFT JOIN loans_pawnloan l ON l.id=s.loan_id AND l.workspace_id=s.workspace_id
        WHERE l.id IS NULL
    """),
    ("EVENT_SNAPSHOT_SCOPE", """
        SELECT count(*) FROM loans_loanriskevent e
        LEFT JOIN loans_loanrisksnapshot s ON s.id=e.snapshot_id
            AND s.workspace_id=e.workspace_id AND s.loan_id=e.loan_id
        WHERE s.id IS NULL
    """),
    ("ALERT_SOURCE_SCOPE", """
        SELECT count(*) FROM loans_loanriskalert a
        LEFT JOIN loans_loanriskevent e ON e.id=a.source_event_id
            AND e.workspace_id=a.workspace_id AND e.loan_id=a.loan_id
        WHERE e.id IS NULL
    """),
    ("ALERT_RECOVERY_SCOPE", """
        SELECT count(*) FROM loans_loanriskalert a
        LEFT JOIN loans_loanriskevent e ON e.id=a.resolved_by_event_id
            AND e.workspace_id=a.workspace_id AND e.loan_id=a.loan_id
        WHERE a.resolved_by_event_id IS NOT NULL AND e.id IS NULL
    """),
    ("NOTICE_RISK_BINDING", """
        SELECT count(*) FROM loans_pawnloannotice n
        LEFT JOIN loans_loanriskalert a ON a.id=n.source_risk_alert_id
            AND a.workspace_id=n.workspace_id AND a.loan_id=n.loan_id
            AND a.source_event_id=n.source_risk_event_id
        WHERE (n.source_risk_alert_id IS NOT NULL OR n.source_risk_event_id IS NOT NULL)
            AND a.id IS NULL
    """),
)


def read_preflight(connection):
    if connection.vendor != "postgresql":
        raise RuntimeError("Risk evidence preflight requires PostgreSQL.")
    with connection.cursor() as cursor:
        cursor.execute("SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname=current_user")
        if not cursor.fetchone()[0]:
            raise RuntimeError("Risk evidence preflight requires the owner migration role with RLS bypass.")
        counts = {}
        for name, query in REFERENCE_CHECKS:
            cursor.execute(query)
            counts[name] = cursor.fetchone()[0]
        cursor.execute("""SELECT count(*) FROM loans_loanriskalert
            WHERE status='RESOLVED' AND resolved_by_event_id IS NULL""")
        legacy = cursor.fetchone()[0]
    return {"violations": counts, "legacy_resolved_without_event": legacy}


def preflight(apps, schema_editor):
    report = read_preflight(schema_editor.connection)
    failures = {key: count for key, count in report["violations"].items() if count}
    if failures:
        raise RuntimeError(f"Risk evidence references need explicit review before migration: {failures}")


GUARDS = """
ALTER TABLE loans_loanrisksnapshot ADD CONSTRAINT loans_risk_snapshot_loan_scope_fk
 FOREIGN KEY (workspace_id,loan_id) REFERENCES loans_pawnloan(workspace_id,id);
ALTER TABLE loans_loanriskevent ADD CONSTRAINT loans_risk_event_snapshot_scope_fk
 FOREIGN KEY (workspace_id,loan_id,snapshot_id) REFERENCES loans_loanrisksnapshot(workspace_id,loan_id,id);
ALTER TABLE loans_loanriskalert ADD CONSTRAINT loans_risk_alert_source_scope_fk
 FOREIGN KEY (workspace_id,loan_id,source_event_id) REFERENCES loans_loanriskevent(workspace_id,loan_id,id);
ALTER TABLE loans_loanriskalert ADD CONSTRAINT loans_risk_alert_recovery_scope_fk
 FOREIGN KEY (workspace_id,loan_id,resolved_by_event_id) REFERENCES loans_loanriskevent(workspace_id,loan_id,id);
ALTER TABLE loans_pawnloannotice ADD CONSTRAINT loans_notice_risk_binding_fk
 FOREIGN KEY (workspace_id,loan_id,source_risk_alert_id,source_risk_event_id)
 REFERENCES loans_loanriskalert(workspace_id,loan_id,id,source_event_id);

CREATE FUNCTION loans_risk_event_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 RAISE EXCEPTION 'Risk events are immutable; append a new transition' USING ERRCODE='23514';
END; $$;
CREATE TRIGGER loans_risk_event_immutable_guard BEFORE UPDATE OR DELETE ON loans_loanriskevent
 FOR EACH ROW EXECUTE FUNCTION loans_risk_event_immutable();

CREATE FUNCTION loans_risk_snapshot_identity() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF (NEW.id,NEW.workspace_id,NEW.loan_id) IS DISTINCT FROM (OLD.id,OLD.workspace_id,OLD.loan_id) THEN
  RAISE EXCEPTION 'Risk snapshot identity cannot be reassigned' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER loans_risk_snapshot_identity_guard BEFORE UPDATE ON loans_loanrisksnapshot
 FOR EACH ROW EXECUTE FUNCTION loans_risk_snapshot_identity();

CREATE FUNCTION loans_risk_alert_identity() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF (NEW.id,NEW.workspace_id,NEW.loan_id,NEW.source_event_id,NEW.alert_kind)
  IS DISTINCT FROM (OLD.id,OLD.workspace_id,OLD.loan_id,OLD.source_event_id,OLD.alert_kind) THEN
  RAISE EXCEPTION 'Risk alert source identity cannot be reassigned' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER loans_risk_alert_identity_guard BEFORE UPDATE ON loans_loanriskalert
 FOR EACH ROW EXECUTE FUNCTION loans_risk_alert_identity();

CREATE FUNCTION loans_notice_risk_identity() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF (OLD.source_risk_alert_id IS NOT NULL OR NEW.source_risk_alert_id IS NOT NULL)
  AND (NEW.workspace_id,NEW.loan_id,NEW.source_risk_alert_id,NEW.source_risk_event_id)
   IS DISTINCT FROM (OLD.workspace_id,OLD.loan_id,OLD.source_risk_alert_id,OLD.source_risk_event_id) THEN
  RAISE EXCEPTION 'Notice risk source identity cannot be reassigned' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER loans_notice_risk_identity_guard BEFORE UPDATE ON loans_pawnloannotice
 FOR EACH ROW EXECUTE FUNCTION loans_notice_risk_identity();
"""

REVERSE = """
DROP TRIGGER loans_notice_risk_identity_guard ON loans_pawnloannotice;
DROP FUNCTION loans_notice_risk_identity();
DROP TRIGGER loans_risk_alert_identity_guard ON loans_loanriskalert;
DROP FUNCTION loans_risk_alert_identity();
DROP TRIGGER loans_risk_snapshot_identity_guard ON loans_loanrisksnapshot;
DROP FUNCTION loans_risk_snapshot_identity();
DROP TRIGGER loans_risk_event_immutable_guard ON loans_loanriskevent;
DROP FUNCTION loans_risk_event_immutable();
ALTER TABLE loans_pawnloannotice DROP CONSTRAINT loans_notice_risk_binding_fk;
ALTER TABLE loans_loanriskalert DROP CONSTRAINT loans_risk_alert_recovery_scope_fk;
ALTER TABLE loans_loanriskalert DROP CONSTRAINT loans_risk_alert_source_scope_fk;
ALTER TABLE loans_loanriskevent DROP CONSTRAINT loans_risk_event_snapshot_scope_fk;
ALTER TABLE loans_loanrisksnapshot DROP CONSTRAINT loans_risk_snapshot_loan_scope_fk;
"""


class Migration(migrations.Migration):
    # Monitoring can be released independently of pending portability 0069-0071.
    dependencies = [("loans", "0068_compact_closed_position_evidence")]
    operations = [
        migrations.RunPython(preflight, migrations.RunPython.noop),
        migrations.AddConstraint(model_name="pawnloan", constraint=models.UniqueConstraint(
            fields=("workspace", "id"), name="loans_pawn_workspace_id_uniq")),
        migrations.AddConstraint(model_name="loanrisksnapshot", constraint=models.UniqueConstraint(
            fields=("workspace", "loan", "id"), name="loans_risk_snapshot_identity_uniq")),
        migrations.AddConstraint(model_name="loanriskevent", constraint=models.UniqueConstraint(
            fields=("workspace", "loan", "id"), name="loans_risk_event_identity_uniq")),
        migrations.AddConstraint(model_name="loanriskalert", constraint=models.UniqueConstraint(
            fields=("workspace", "loan", "id", "source_event"), name="loans_risk_alert_identity_uniq")),
        migrations.AddConstraint(model_name="pawnloannotice", constraint=models.CheckConstraint(
            condition=(models.Q(source_risk_alert__isnull=True, source_risk_event__isnull=True)
                       | models.Q(source_risk_alert__isnull=False, source_risk_event__isnull=False)),
            name="loans_notice_risk_pair_complete")),
        migrations.RunSQL(GUARDS, REVERSE),
    ]
