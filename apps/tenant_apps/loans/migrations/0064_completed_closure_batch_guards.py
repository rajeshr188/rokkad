"""Permit unknown cash/return only through exactly bound completed closure evidence."""
from django.db import migrations

FORWARD = r"""
CREATE OR REPLACE FUNCTION loans_release_batch_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE unspecified boolean;
            BEGIN
                IF TG_OP <> 'INSERT' THEN
                    RAISE EXCEPTION 'Release batch evidence is immutable';
                END IF;
                IF TG_TABLE_NAME = 'loans_pawnreleasebatchline' THEN
                    IF NOT EXISTS (
                        SELECT 1 FROM loans_pawnreleasebatch b, loans_pawnloanrelease r
                        WHERE b.id = NEW.batch_id AND r.id = NEW.release_id
                          AND b.workspace_id = NEW.workspace_id AND r.workspace_id = NEW.workspace_id
                          AND b.effective_date = r.effective_date
                    ) THEN RAISE EXCEPTION 'Batch release must share workspace and effective date'; END IF;
                    unspecified := EXISTS (SELECT 1 FROM loans_pawnreleasebatch b JOIN loans_pawnloanrelease r ON r.id=NEW.release_id JOIN loans_pawnloanevent e ON e.id=r.loan_event_id
 WHERE b.id=NEW.batch_id AND b.mode='PAPER' AND b.workspace_id=NEW.workspace_id AND r.workspace_id=NEW.workspace_id
 AND e.workspace_id=NEW.workspace_id AND e.payload#>>'{release,paper_closure,profile}'='recorded-history-closure/1'
 AND e.payload#>>'{release,paper_closure,closure_basis}'='PAPER_SETTLEMENT'
 AND e.payload#>>'{release,paper_closure,batch_id}'=NEW.batch_id::text);
                    IF unspecified AND (btrim(NEW.paid_by) <> '' OR btrim(NEW.collector_name) <> '' OR btrim(NEW.relationship) <> '' OR btrim(NEW.authorization_note) <> '')
                    THEN RAISE EXCEPTION 'Unspecified cash and handover cannot assert payer or collector'; END IF;
                    IF NOT unspecified AND (btrim(NEW.collector_name) = '' OR (NOT NEW.collector_is_borrower AND
                        (btrim(NEW.relationship) = '' OR btrim(NEW.authorization_note) = '')))
                    THEN RAISE EXCEPTION 'Collector confirmation is required'; END IF;
                END IF;
                RETURN NEW;
            END $$;
CREATE OR REPLACE FUNCTION loans_paper_release_guard() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
              IF TG_TABLE_NAME = 'loans_pawnreleasebatch' THEN
                IF NEW.mode NOT IN ('COUNTER', 'PAPER') THEN RAISE EXCEPTION 'Invalid batch mode'; END IF;
              ELSIF TG_TABLE_NAME = 'loans_pawnreleasebatchline' THEN
                IF EXISTS (SELECT 1 FROM loans_pawnreleasebatch WHERE id=NEW.batch_id AND mode='PAPER')
                   AND btrim(NEW.paid_by) = '' AND NOT EXISTS (SELECT 1 FROM loans_pawnreleasebatch b JOIN loans_pawnloanrelease r ON r.id=NEW.release_id JOIN loans_pawnloanevent e ON e.id=r.loan_event_id
 WHERE b.id=NEW.batch_id AND b.mode='PAPER' AND b.workspace_id=NEW.workspace_id AND r.workspace_id=NEW.workspace_id
 AND e.workspace_id=NEW.workspace_id AND e.payload#>>'{release,paper_closure,profile}'='recorded-history-closure/1'
 AND e.payload#>>'{release,paper_closure,closure_basis}'='PAPER_SETTLEMENT'
 AND e.payload#>>'{release,paper_closure,batch_id}'=NEW.batch_id::text) THEN RAISE EXCEPTION 'Paper closure payer required'; END IF;
              ELSIF NEW.returned_at IS NULL THEN
                IF NOT EXISTS (SELECT 1 FROM loans_pawnloanrelease r JOIN loans_pawnloanevent e ON e.id=r.loan_event_id
                    WHERE r.id=NEW.release_id AND e.payload->'release'->'paper_closure'->>'date_precision'='DAY')
                THEN RAISE EXCEPTION 'Date-only return requires paper closure evidence'; END IF;
              END IF;
              RETURN NEW;
            END $$;
"""
REVERSE = r"""
CREATE OR REPLACE FUNCTION loans_release_batch_guard() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF TG_OP <> 'INSERT' THEN
                    RAISE EXCEPTION 'Release batch evidence is immutable';
                END IF;
                IF TG_TABLE_NAME = 'loans_pawnreleasebatchline' THEN
                    IF NOT EXISTS (
                        SELECT 1 FROM loans_pawnreleasebatch b, loans_pawnloanrelease r
                        WHERE b.id = NEW.batch_id AND r.id = NEW.release_id
                          AND b.workspace_id = NEW.workspace_id AND r.workspace_id = NEW.workspace_id
                          AND b.effective_date = r.effective_date
                    ) THEN RAISE EXCEPTION 'Batch release must share workspace and effective date'; END IF;
                    IF btrim(NEW.collector_name) = '' OR (NOT NEW.collector_is_borrower AND
                        (btrim(NEW.relationship) = '' OR btrim(NEW.authorization_note) = ''))
                    THEN RAISE EXCEPTION 'Collector confirmation is required'; END IF;
                END IF;
                RETURN NEW;
            END $$;
CREATE OR REPLACE FUNCTION loans_paper_release_guard() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
              IF TG_TABLE_NAME = 'loans_pawnreleasebatch' THEN
                IF NEW.mode NOT IN ('COUNTER', 'PAPER') THEN RAISE EXCEPTION 'Invalid batch mode'; END IF;
              ELSIF TG_TABLE_NAME = 'loans_pawnreleasebatchline' THEN
                IF EXISTS (SELECT 1 FROM loans_pawnreleasebatch WHERE id=NEW.batch_id AND mode='PAPER')
                   AND btrim(NEW.paid_by) = '' THEN RAISE EXCEPTION 'Paper closure payer required'; END IF;
              ELSIF NEW.returned_at IS NULL THEN
                IF NOT EXISTS (SELECT 1 FROM loans_pawnloanrelease r JOIN loans_pawnloanevent e ON e.id=r.loan_event_id
                    WHERE r.id=NEW.release_id AND e.payload->'release'->'paper_closure'->>'date_precision'='DAY')
                THEN RAISE EXCEPTION 'Date-only return requires paper closure evidence'; END IF;
              END IF;
              RETURN NEW;
            END $$;
"""

class Migration(migrations.Migration):
    dependencies = [("loans", "0063_loanoriginationsettings_maximum_quote_age_days_and_more")]
    operations = [migrations.RunSQL(FORWARD, reverse_sql=REVERSE)]
