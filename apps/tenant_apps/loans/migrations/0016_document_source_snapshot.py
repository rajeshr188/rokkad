from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("loans", "0015_license_continuation")]
    operations = [
        migrations.AddField(
            model_name="loandocumentissue", name="source_snapshot",
            field=models.JSONField(null=True, blank=True),
        ),
        migrations.RunSQL(
            sql="""
            ALTER TABLE loans_loandocumentissue ADD CONSTRAINT loans_issue_snapshot_workspace
            CHECK (source_snapshot IS NULL OR COALESCE(
                jsonb_typeof(source_snapshot) = 'object'
                AND source_snapshot->>'schema_version' = '2'
                AND source_snapshot->>'workspace_id' = workspace_id::text, false));
            ALTER TABLE loans_loandocumentissue ADD CONSTRAINT loans_ticket_snapshot_required
            CHECK (payload_schema_version <> 2 OR document_type <> 'loan_ticket' OR source_snapshot IS NOT NULL);
            CREATE FUNCTION loans_issue_snapshot_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF TG_OP = 'DELETE' THEN
                    IF OLD.source_snapshot IS NOT NULL THEN
                        RAISE EXCEPTION 'Document source evidence is immutable' USING ERRCODE = '23514';
                    END IF;
                    RETURN OLD;
                END IF;
                IF NEW.source_snapshot IS DISTINCT FROM OLD.source_snapshot THEN
                    RAISE EXCEPTION 'Document source evidence is immutable' USING ERRCODE = '23514';
                END IF;
                RETURN NEW;
            END; $$;
            CREATE TRIGGER loans_issue_snapshot_immutable BEFORE UPDATE OR DELETE ON loans_loandocumentissue
            FOR EACH ROW EXECUTE FUNCTION loans_issue_snapshot_immutable();
            """,
            reverse_sql="""
            DROP TRIGGER loans_issue_snapshot_immutable ON loans_loandocumentissue;
            DROP FUNCTION loans_issue_snapshot_immutable();
            ALTER TABLE loans_loandocumentissue DROP CONSTRAINT loans_issue_snapshot_workspace;
            ALTER TABLE loans_loandocumentissue DROP CONSTRAINT IF EXISTS loans_ticket_snapshot_required;
            """,
        ),
    ]
