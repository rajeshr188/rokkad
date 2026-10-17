"""Allow explicit aggregate checkpoints without changing their economic rule."""

from importlib import import_module

from django.db import migrations


OLD = import_module(
    "apps.tenant_apps.loans.migrations.0080_opening_checkpoint_corrections"
).GUARD.split("CREATE TRIGGER loans_opening_correction_guard")[0].replace(
    "CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1
)
NEW = OLD.replace(
    "('loan-opening-review/4','loan-opening-review/5')",
    "('loan-opening-review/2','loan-opening-review/4','loan-opening-review/5')",
)
assert NEW != OLD

OLD_NATIVE = import_module(
    "apps.tenant_apps.loans.migrations.0079_agreement_financial_corrections"
).GUARD.split("CREATE TRIGGER loans_corrected_agreement_guard")[0].replace(
    "CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1
)
NEW_NATIVE = OLD_NATIVE.replace(
    " c:=NEW.evidence->'agreement_correction';",
    """ c:=NEW.evidence->'agreement_correction';
 IF EXISTS (SELECT 1 FROM loans_loanpolicysnapshot p WHERE p.id=NEW.policy_snapshot_id AND p.policy_version=1)
 AND (c->>'policy_version' IS DISTINCT FROM '1'
   OR EXISTS (SELECT 1 FROM loans_pawnloanevent history_event WHERE history_event.loan_id=NEW.loan_id AND history_event.workspace_id=NEW.workspace_id
     AND history_event.id<NEW.loan_event_id AND history_event.event_kind NOT IN ('DISBURSAL','REVERSAL'))
   OR EXISTS (SELECT 1 FROM loans_pawnloaninterestaccrual a WHERE a.loan_id=NEW.loan_id AND a.workspace_id=NEW.workspace_id))
 THEN RAISE EXCEPTION 'Legacy agreement correction requires its unserviced retained policy'; END IF;
""",
)
assert NEW_NATIVE != OLD_NATIVE


class Migration(migrations.Migration):
    dependencies = [("loans", "0091_merge_position_and_review_boundary")]
    operations = [
        migrations.RunSQL(
            NEW + NEW_NATIVE,
            """
            DO $$ BEGIN
              IF EXISTS (SELECT 1 FROM loans_pawnloanevent
                WHERE event_kind='OPENING_CORRECTION'
                AND payload#>>'{opening,review,profile}'='loan-opening-review/2')
                OR EXISTS (SELECT 1 FROM loans_pawnloandisbursalsnapshot s
                  JOIN loans_loanpolicysnapshot p ON p.id=s.policy_snapshot_id
                  WHERE s.basis='CORRECTED' AND p.policy_version=1)
              THEN RAISE EXCEPTION 'Retained aggregate or legacy corrections require compatible readers'; END IF;
            END; $$;
            """ + OLD + OLD_NATIVE,
        )
    ]
