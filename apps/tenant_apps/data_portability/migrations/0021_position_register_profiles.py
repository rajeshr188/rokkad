from django.db import migrations


GUARD = """
CREATE OR REPLACE FUNCTION portability_guided_opening_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE item jsonb;
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Guided import history cannot be deleted'; END IF;
 IF NEW.source_sha256 !~ '^[0-9a-f]{64}$' OR NEW.source_key !~ '^[a-z0-9][a-z0-9-]{0,47}$'
 OR NEW.state NOT IN ('STAGED','READY','COMPLETED','CANCELLED')
 THEN RAISE EXCEPTION 'Invalid guided import identity or state'; END IF;
 IF TG_OP='INSERT' THEN
  IF NEW.state<>'STAGED' OR NEW.results<>'[]'::jsonb OR NEW.mapping<>'{}'::jsonb
  OR NEW.preview<>'{}'::jsonb OR NEW.approval_digest<>'' OR NEW.committed_by_id IS NOT NULL
  OR NEW.committed_at IS NOT NULL OR COALESCE(NEW.document->>'profile','') NOT IN ('outstanding-register/1','outstanding-register/2','closed-register/1')
  OR jsonb_typeof(NEW.document->'rows') IS DISTINCT FROM 'array'
  OR NOT jsonb_array_length(NEW.document->'rows') BETWEEN 1 AND 200
  THEN RAISE EXCEPTION 'New guided imports require bounded staged source evidence'; END IF;
 ELSE
  IF OLD.state IN ('COMPLETED','CANCELLED') OR
   (NEW.workspace_id,NEW.public_id,NEW.source_key,NEW.source_name,NEW.source_sha256,NEW.created_by_id,NEW.created_at)
   IS DISTINCT FROM
   (OLD.workspace_id,OLD.public_id,OLD.source_key,OLD.source_name,OLD.source_sha256,OLD.created_by_id,OLD.created_at)
  THEN RAISE EXCEPTION 'Guided source identity and completed evidence are immutable'; END IF;
  IF NEW.state='CANCELLED' THEN
   IF NEW.document<>'{}'::jsonb OR NEW.mapping<>'{}'::jsonb OR NEW.preview<>'{}'::jsonb OR NEW.approval_digest<>''
   THEN RAISE EXCEPTION 'Cancelled staging must clear private source and review'; END IF;
  ELSIF NEW.document IS DISTINCT FROM OLD.document THEN
   RAISE EXCEPTION 'Guided source rows are immutable';
  END IF;
  IF NEW.state='READY' AND (NEW.approval_digest !~ '^[0-9a-f]{64}$'
    OR NEW.preview->'issues' IS DISTINCT FROM '[]'::jsonb)
  THEN RAISE EXCEPTION 'Ready guided imports require a successful reviewed preview'; END IF;
  IF NEW.state='COMPLETED' THEN
   IF OLD.state<>'READY' OR NEW.mapping IS DISTINCT FROM OLD.mapping OR NEW.preview IS DISTINCT FROM OLD.preview
   OR NEW.approval_digest IS DISTINCT FROM OLD.approval_digest OR NEW.committed_by_id IS NULL OR NEW.committed_at IS NULL
   OR jsonb_typeof(NEW.results)<>'array' OR NOT jsonb_array_length(NEW.results) BETWEEN 1 AND 20
   OR jsonb_array_length(NEW.results) IS DISTINCT FROM (NEW.preview->>'loans')::int
   THEN RAISE EXCEPTION 'Completion requires the exact reviewed batch and all results'; END IF;
   FOR item IN SELECT * FROM jsonb_array_elements(NEW.results) LOOP
    IF NOT EXISTS (SELECT 1 FROM loans_historicalloanimport r WHERE r.workspace_id=NEW.workspace_id
      AND r.id=(item->>'origin_id')::bigint AND r.loan_id=(item->>'loan_id')::bigint
      AND r.source_sha256=item->>'source_sha256' AND (
       (NEW.document->>'profile'='outstanding-register/1' AND r.document->>'profile'='loan-opening-commit/1')
       OR (NEW.document->>'profile'='outstanding-register/2' AND r.document->>'profile'='loan-opening-commit/1' AND r.document->'review'->>'profile'='loan-opening-review/4')
       OR (NEW.document->>'profile'='closed-register/1' AND r.document->>'profile' IN ('loan-closed-position-admission/1','loan-closed-position-admission/2'))))
    THEN RAISE EXCEPTION 'Guided results must match immutable openings in this Workspace'; END IF;
   END LOOP;
   IF (SELECT count(DISTINCT x->>'origin_id') FROM jsonb_array_elements(NEW.results) x) <> jsonb_array_length(NEW.results)
   THEN RAISE EXCEPTION 'Each guided result must be distinct'; END IF;
  END IF;
 END IF;
 IF NEW.state<>'COMPLETED' AND (NEW.results<>'[]'::jsonb OR NEW.committed_by_id IS NOT NULL OR NEW.committed_at IS NOT NULL)
 THEN RAISE EXCEPTION 'Only completed guided imports may have results'; END IF;
 RETURN NEW;
END; $$;
"""
REVERSE = """DO $$ BEGIN
 IF EXISTS (SELECT 1 FROM data_portability_guidedopeningbatch WHERE document->>'profile' IN ('outstanding-register/2','closed-register/1'))
 THEN RAISE EXCEPTION 'Cannot retire register profiles while retained source batches exist'; END IF;
END; $$;

CREATE OR REPLACE FUNCTION portability_guided_opening_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE item jsonb;
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Guided import history cannot be deleted'; END IF;
 IF NEW.source_sha256 !~ '^[0-9a-f]{64}$' OR NEW.source_key !~ '^[a-z0-9][a-z0-9-]{0,47}$'
 OR NEW.state NOT IN ('STAGED','READY','COMPLETED','CANCELLED')
 THEN RAISE EXCEPTION 'Invalid guided import identity or state'; END IF;
 IF TG_OP='INSERT' THEN
  IF NEW.state<>'STAGED' OR NEW.results<>'[]'::jsonb OR NEW.mapping<>'{}'::jsonb
  OR NEW.preview<>'{}'::jsonb OR NEW.approval_digest<>'' OR NEW.committed_by_id IS NOT NULL
  OR NEW.committed_at IS NOT NULL OR NEW.document->>'profile' IS DISTINCT FROM 'outstanding-register/1'
  OR jsonb_typeof(NEW.document->'rows') IS DISTINCT FROM 'array'
  OR NOT jsonb_array_length(NEW.document->'rows') BETWEEN 1 AND 200
  THEN RAISE EXCEPTION 'New guided imports require bounded staged source evidence'; END IF;
 ELSE
  IF OLD.state IN ('COMPLETED','CANCELLED') OR
   (NEW.workspace_id,NEW.public_id,NEW.source_key,NEW.source_name,NEW.source_sha256,NEW.created_by_id,NEW.created_at)
   IS DISTINCT FROM
   (OLD.workspace_id,OLD.public_id,OLD.source_key,OLD.source_name,OLD.source_sha256,OLD.created_by_id,OLD.created_at)
  THEN RAISE EXCEPTION 'Guided source identity and completed evidence are immutable'; END IF;
  IF NEW.state='CANCELLED' THEN
   IF NEW.document<>'{}'::jsonb OR NEW.mapping<>'{}'::jsonb OR NEW.preview<>'{}'::jsonb OR NEW.approval_digest<>''
   THEN RAISE EXCEPTION 'Cancelled staging must clear private source and review'; END IF;
  ELSIF NEW.document IS DISTINCT FROM OLD.document THEN
   RAISE EXCEPTION 'Guided source rows are immutable';
  END IF;
  IF NEW.state='READY' AND (NEW.approval_digest !~ '^[0-9a-f]{64}$'
    OR NEW.preview->'issues' IS DISTINCT FROM '[]'::jsonb)
  THEN RAISE EXCEPTION 'Ready guided imports require a successful reviewed preview'; END IF;
  IF NEW.state='COMPLETED' THEN
   IF OLD.state<>'READY' OR NEW.mapping IS DISTINCT FROM OLD.mapping OR NEW.preview IS DISTINCT FROM OLD.preview
   OR NEW.approval_digest IS DISTINCT FROM OLD.approval_digest OR NEW.committed_by_id IS NULL OR NEW.committed_at IS NULL
   OR jsonb_typeof(NEW.results)<>'array' OR NOT jsonb_array_length(NEW.results) BETWEEN 1 AND 20
   OR jsonb_array_length(NEW.results) IS DISTINCT FROM (NEW.preview->>'loans')::int
   THEN RAISE EXCEPTION 'Completion requires the exact reviewed batch and all results'; END IF;
   FOR item IN SELECT * FROM jsonb_array_elements(NEW.results) LOOP
    IF NOT EXISTS (SELECT 1 FROM loans_historicalloanimport r WHERE r.workspace_id=NEW.workspace_id
      AND r.id=(item->>'origin_id')::bigint AND r.loan_id=(item->>'loan_id')::bigint
      AND r.source_sha256=item->>'source_sha256' AND r.document->>'profile'='loan-opening-commit/1')
    THEN RAISE EXCEPTION 'Guided results must match immutable openings in this Workspace'; END IF;
   END LOOP;
   IF (SELECT count(DISTINCT x->>'origin_id') FROM jsonb_array_elements(NEW.results) x) <> jsonb_array_length(NEW.results)
   THEN RAISE EXCEPTION 'Each guided result must be distinct'; END IF;
  END IF;
 END IF;
 IF NEW.state<>'COMPLETED' AND (NEW.results<>'[]'::jsonb OR NEW.committed_by_id IS NOT NULL OR NEW.committed_at IS NOT NULL)
 THEN RAISE EXCEPTION 'Only completed guided imports may have results'; END IF;
 RETURN NEW;
END; $$;
"""


class Migration(migrations.Migration):
    dependencies = [('data_portability', '0020_loan_restore_batch')]
    operations = [migrations.RunSQL(GUARD, REVERSE)]
