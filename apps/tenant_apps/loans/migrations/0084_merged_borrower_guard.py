"""Serialize borrower admission with Party merge; never attach to a merged alias."""
from django.db import migrations


FORWARD = """
CREATE FUNCTION loans_merged_borrower_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE borrower_metadata jsonb;
BEGIN
 -- Party merge holds FOR UPDATE on both identities. Take a compatible FK lock
 -- before reading metadata, so either admission commits first and is moved by
 -- the merge, or the insert waits and rejects the now-archived duplicate.
 SELECT metadata INTO borrower_metadata FROM party_party
 WHERE id=NEW.borrower_id AND workspace_id=NEW.workspace_id FOR KEY SHARE;
 IF NOT FOUND OR borrower_metadata ? 'merged_into_party_id' THEN
   RAISE EXCEPTION 'Select the retained customer; this borrower identity is missing or merged'
     USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER loans_merged_borrower_insert_guard BEFORE INSERT ON loans_pawnloan
FOR EACH ROW EXECUTE FUNCTION loans_merged_borrower_guard();
CREATE TRIGGER loans_merged_borrower_update_guard BEFORE UPDATE OF borrower_id ON loans_pawnloan
FOR EACH ROW WHEN (OLD.borrower_id IS DISTINCT FROM NEW.borrower_id)
EXECUTE FUNCTION loans_merged_borrower_guard();
CREATE TRIGGER khata_merged_borrower_insert_guard BEFORE INSERT ON loans_khataaccount
FOR EACH ROW EXECUTE FUNCTION loans_merged_borrower_guard();
CREATE TRIGGER khata_merged_borrower_update_guard BEFORE UPDATE OF borrower_id ON loans_khataaccount
FOR EACH ROW WHEN (OLD.borrower_id IS DISTINCT FROM NEW.borrower_id)
EXECUTE FUNCTION loans_merged_borrower_guard();
"""
REVERSE = """
DROP TRIGGER khata_merged_borrower_update_guard ON loans_khataaccount;
DROP TRIGGER khata_merged_borrower_insert_guard ON loans_khataaccount;
DROP TRIGGER loans_merged_borrower_update_guard ON loans_pawnloan;
DROP TRIGGER loans_merged_borrower_insert_guard ON loans_pawnloan;
DROP FUNCTION loans_merged_borrower_guard();
"""


class Migration(migrations.Migration):
    dependencies = [("loans", "0082_party_merge_borrowers")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
