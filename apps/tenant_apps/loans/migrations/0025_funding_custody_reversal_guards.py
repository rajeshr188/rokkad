from django.db import migrations


FORWARD_SQL = r"""
CREATE TRIGGER loans_funding_pledge_reversal_immutable
BEFORE UPDATE OR DELETE ON loans_fundingpledgereversal
FOR EACH ROW EXECUTE FUNCTION loans_guard_funding_immutable();

CREATE TRIGGER loans_funding_return_reversal_immutable
BEFORE UPDATE OR DELETE ON loans_fundingreturnreversal
FOR EACH ROW EXECUTE FUNCTION loans_guard_funding_immutable();

CREATE OR REPLACE FUNCTION loans_guard_funding_reversal_header()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF BTRIM(NEW.reason) = '' THEN
        RAISE EXCEPTION 'Funding custody reversal reason is required.';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER loans_funding_pledge_reversal_insert_guard
BEFORE INSERT ON loans_fundingpledgereversal
FOR EACH ROW EXECUTE FUNCTION loans_guard_funding_reversal_header();

CREATE TRIGGER loans_funding_return_reversal_insert_guard
BEFORE INSERT ON loans_fundingreturnreversal
FOR EACH ROW EXECUTE FUNCTION loans_guard_funding_reversal_header();

CREATE OR REPLACE FUNCTION loans_guard_funding_pledge_item()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    collateral_loan_id bigint;
    collateral_custody varchar(32);
    pawn_workspace_id bigint;
    pawn_state varchar(16);
    pledge_workspace_id bigint;
    funding_workspace_id bigint;
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Funding pledge items cannot be deleted.';
    END IF;
    IF TG_OP = 'UPDATE' THEN
        IF OLD.funding_pledge_id IS DISTINCT FROM NEW.funding_pledge_id
           OR OLD.collateral_item_id IS DISTINCT FROM NEW.collateral_item_id
           OR OLD.source_pawn_loan_id IS DISTINCT FROM NEW.source_pawn_loan_id
           OR OLD.selected_collateral_value IS DISTINCT FROM NEW.selected_collateral_value
           OR OLD.valuation_snapshot IS DISTINCT FROM NEW.valuation_snapshot
           OR OLD.valuation_fingerprint IS DISTINCT FROM NEW.valuation_fingerprint
           OR OLD.created_at IS DISTINCT FROM NEW.created_at THEN
            RAISE EXCEPTION 'Funding pledge item snapshots are immutable.';
        END IF;
        IF OLD.released_at IS NULL AND NEW.released_at IS NOT NULL THEN
            IF NOT EXISTS (
                SELECT 1
                  FROM loans_fundingreturnitem return_item
                  JOIN loans_fundingreturn funding_return
                    ON funding_return.id = return_item.funding_return_id
                  LEFT JOIN loans_fundingreturnreversal reversal
                    ON reversal.funding_return_id = funding_return.id
                 WHERE return_item.pledge_item_id = NEW.id
                   AND reversal.id IS NULL
            ) AND NOT EXISTS (
                SELECT 1 FROM loans_fundingpledgereversal reversal
                 WHERE reversal.funding_pledge_id = NEW.funding_pledge_id
            ) THEN
                RAISE EXCEPTION 'Funding pledge release requires return or reversal evidence.';
            END IF;
            RETURN NEW;
        END IF;
        IF OLD.released_at IS NOT NULL AND NEW.released_at IS NULL THEN
            IF NOT EXISTS (
                SELECT 1
                  FROM loans_fundingreturnitem return_item
                  JOIN loans_fundingreturnreversal reversal
                    ON reversal.funding_return_id = return_item.funding_return_id
                 WHERE return_item.pledge_item_id = NEW.id
            ) THEN
                RAISE EXCEPTION 'Funding pledge reactivation requires return reversal evidence.';
            END IF;
            RETURN NEW;
        END IF;
        RAISE EXCEPTION 'Funding pledge release state must change.';
    END IF;
    IF NEW.released_at IS NOT NULL THEN
        RAISE EXCEPTION 'A funding pledge item must be created active.';
    END IF;

    SELECT item.loan_id, item.custody_state, loan.workspace_id, loan.state
      INTO collateral_loan_id, collateral_custody, pawn_workspace_id, pawn_state
      FROM loans_pawncollateralitem item
      JOIN loans_pawnloan loan ON loan.id = item.loan_id
     WHERE item.id = NEW.collateral_item_id;
    SELECT pledge.workspace_id, funding.workspace_id
      INTO pledge_workspace_id, funding_workspace_id
      FROM loans_fundingpledge pledge
      JOIN loans_fundingloan funding ON funding.id = pledge.funding_loan_id
     WHERE pledge.id = NEW.funding_pledge_id;

    IF collateral_loan_id IS DISTINCT FROM NEW.source_pawn_loan_id THEN
        RAISE EXCEPTION 'Funding pledge source PawnLoan does not own collateral.';
    END IF;
    IF pawn_workspace_id IS DISTINCT FROM pledge_workspace_id
       OR pledge_workspace_id IS DISTINCT FROM funding_workspace_id THEN
        RAISE EXCEPTION 'Funding pledge workspace does not match collateral workspace.';
    END IF;
    IF pawn_state IS DISTINCT FROM 'ACTIVE' THEN
        RAISE EXCEPTION 'Funding pledge collateral requires an active PawnLoan.';
    END IF;
    IF collateral_custody IS DISTINCT FROM 'IN_VAULT' THEN
        RAISE EXCEPTION 'Funding pledge collateral must be in vault custody.';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION loans_guard_funding_return_item_insert()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM loans_fundingreturn funding_return
          JOIN loans_fundingpledgeitem pledge_item
            ON pledge_item.id = NEW.pledge_item_id
          JOIN loans_fundingpledge pledge
            ON pledge.id = pledge_item.funding_pledge_id
         WHERE funding_return.id = NEW.funding_return_id
           AND funding_return.funding_loan_id = pledge.funding_loan_id
    ) THEN
        RAISE EXCEPTION 'Returned pledge item must belong to the FundingLoan.';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM loans_fundingreturnitem prior_item
          JOIN loans_fundingreturn prior_return
            ON prior_return.id = prior_item.funding_return_id
          LEFT JOIN loans_fundingreturnreversal reversal
            ON reversal.funding_return_id = prior_return.id
         WHERE prior_item.pledge_item_id = NEW.pledge_item_id
           AND reversal.id IS NULL
    ) THEN
        RAISE EXCEPTION 'Funding pledge item already has an unreversed return.';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION loans_guard_funding_custody_insert()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    projected_state varchar(32);
    original loans_pawncollateralcustodyevent%ROWTYPE;
BEGIN
    SELECT custody_state INTO projected_state
      FROM loans_pawncollateralitem
     WHERE id = NEW.collateral_item_id
     FOR UPDATE;
    IF projected_state IS DISTINCT FROM NEW.from_state THEN
        RAISE EXCEPTION 'Custody movement must start at the projected state.';
    END IF;
    IF NEW.funding_pledge_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM loans_fundingpledgeitem item
         WHERE item.funding_pledge_id = NEW.funding_pledge_id
           AND item.collateral_item_id = NEW.collateral_item_id
    ) THEN
        RAISE EXCEPTION 'Funding pledge custody source does not contain collateral.';
    END IF;
    IF NEW.funding_return_id IS NOT NULL AND NOT EXISTS (
        SELECT 1
          FROM loans_fundingreturnitem return_item
          JOIN loans_fundingpledgeitem pledge_item
            ON pledge_item.id = return_item.pledge_item_id
         WHERE return_item.funding_return_id = NEW.funding_return_id
           AND pledge_item.collateral_item_id = NEW.collateral_item_id
    ) THEN
        RAISE EXCEPTION 'Funding return custody source does not contain collateral.';
    END IF;
    IF NEW.funding_pledge_reversal_id IS NOT NULL THEN
        IF NEW.funding_pledge_id IS NULL OR NEW.funding_return_reversal_id IS NOT NULL THEN
            RAISE EXCEPTION 'Funding pledge reversal custody requires only its pledge source.';
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM loans_fundingpledgereversal reversal
             WHERE reversal.id = NEW.funding_pledge_reversal_id
               AND reversal.funding_pledge_id = NEW.funding_pledge_id
        ) THEN
            RAISE EXCEPTION 'Funding pledge reversal must match its pledge.';
        END IF;
        SELECT * INTO original
          FROM loans_pawncollateralcustodyevent custody
         WHERE custody.collateral_item_id = NEW.collateral_item_id
           AND custody.funding_pledge_id = NEW.funding_pledge_id
           AND custody.funding_pledge_reversal_id IS NULL
         ORDER BY custody.id DESC
         LIMIT 1;
    ELSIF NEW.funding_return_reversal_id IS NOT NULL THEN
        IF NEW.funding_return_id IS NULL OR NEW.funding_pledge_reversal_id IS NOT NULL THEN
            RAISE EXCEPTION 'Funding return reversal custody requires only its return source.';
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM loans_fundingreturnreversal reversal
             WHERE reversal.id = NEW.funding_return_reversal_id
               AND reversal.funding_return_id = NEW.funding_return_id
        ) THEN
            RAISE EXCEPTION 'Funding return reversal must match its return.';
        END IF;
        SELECT * INTO original
          FROM loans_pawncollateralcustodyevent custody
         WHERE custody.collateral_item_id = NEW.collateral_item_id
           AND custody.funding_return_id = NEW.funding_return_id
           AND custody.funding_return_reversal_id IS NULL
         ORDER BY custody.id DESC
         LIMIT 1;
    ELSE
        RETURN NEW;
    END IF;
    IF original.id IS NULL
       OR NEW.from_state IS DISTINCT FROM original.to_state
       OR NEW.to_state IS DISTINCT FROM original.from_state THEN
        RAISE EXCEPTION 'Funding custody reversal must exactly invert its original movement.';
    END IF;
    IF EXISTS (
        SELECT 1 FROM loans_pawncollateralcustodyevent later
         WHERE later.collateral_item_id = NEW.collateral_item_id
           AND later.id > original.id
    ) THEN
        RAISE EXCEPTION 'Later collateral custody movements must be reversed first.';
    END IF;
    RETURN NEW;
END;
$$;
"""


REVERSE_SQL = r"""
DROP TRIGGER IF EXISTS loans_funding_return_reversal_insert_guard ON loans_fundingreturnreversal;
DROP TRIGGER IF EXISTS loans_funding_pledge_reversal_insert_guard ON loans_fundingpledgereversal;
DROP FUNCTION IF EXISTS loans_guard_funding_reversal_header();
DROP TRIGGER IF EXISTS loans_funding_return_reversal_immutable ON loans_fundingreturnreversal;
DROP TRIGGER IF EXISTS loans_funding_pledge_reversal_immutable ON loans_fundingpledgereversal;

CREATE OR REPLACE FUNCTION loans_guard_funding_pledge_item()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    collateral_loan_id bigint;
    collateral_custody varchar(32);
    pawn_workspace_id bigint;
    pawn_state varchar(16);
    pledge_workspace_id bigint;
    funding_workspace_id bigint;
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Funding pledge items cannot be deleted.';
    END IF;
    IF TG_OP = 'UPDATE' THEN
        IF OLD.funding_pledge_id IS DISTINCT FROM NEW.funding_pledge_id
           OR OLD.collateral_item_id IS DISTINCT FROM NEW.collateral_item_id
           OR OLD.source_pawn_loan_id IS DISTINCT FROM NEW.source_pawn_loan_id
           OR OLD.selected_collateral_value IS DISTINCT FROM NEW.selected_collateral_value
           OR OLD.valuation_snapshot IS DISTINCT FROM NEW.valuation_snapshot
           OR OLD.valuation_fingerprint IS DISTINCT FROM NEW.valuation_fingerprint
           OR OLD.created_at IS DISTINCT FROM NEW.created_at THEN
            RAISE EXCEPTION 'Funding pledge item snapshots are immutable.';
        END IF;
        IF OLD.released_at IS NOT NULL OR NEW.released_at IS NULL THEN
            RAISE EXCEPTION 'Funding pledge release can be recorded only once.';
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM loans_fundingreturnitem return_item
             WHERE return_item.pledge_item_id = NEW.id
        ) THEN
            RAISE EXCEPTION 'Funding pledge release requires return evidence.';
        END IF;
        RETURN NEW;
    END IF;
    IF NEW.released_at IS NOT NULL THEN
        RAISE EXCEPTION 'A funding pledge item must be created active.';
    END IF;
    SELECT item.loan_id, item.custody_state, loan.workspace_id, loan.state
      INTO collateral_loan_id, collateral_custody, pawn_workspace_id, pawn_state
      FROM loans_pawncollateralitem item
      JOIN loans_pawnloan loan ON loan.id = item.loan_id
     WHERE item.id = NEW.collateral_item_id;
    SELECT pledge.workspace_id, funding.workspace_id
      INTO pledge_workspace_id, funding_workspace_id
      FROM loans_fundingpledge pledge
      JOIN loans_fundingloan funding ON funding.id = pledge.funding_loan_id
     WHERE pledge.id = NEW.funding_pledge_id;
    IF collateral_loan_id IS DISTINCT FROM NEW.source_pawn_loan_id THEN
        RAISE EXCEPTION 'Funding pledge source PawnLoan does not own collateral.';
    END IF;
    IF pawn_workspace_id IS DISTINCT FROM pledge_workspace_id
       OR pledge_workspace_id IS DISTINCT FROM funding_workspace_id THEN
        RAISE EXCEPTION 'Funding pledge workspace does not match collateral workspace.';
    END IF;
    IF pawn_state IS DISTINCT FROM 'ACTIVE' THEN
        RAISE EXCEPTION 'Funding pledge collateral requires an active PawnLoan.';
    END IF;
    IF collateral_custody IS DISTINCT FROM 'IN_VAULT' THEN
        RAISE EXCEPTION 'Funding pledge collateral must be in vault custody.';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION loans_guard_funding_return_item_insert()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM loans_fundingreturn funding_return
          JOIN loans_fundingpledgeitem pledge_item
            ON pledge_item.id = NEW.pledge_item_id
          JOIN loans_fundingpledge pledge
            ON pledge.id = pledge_item.funding_pledge_id
         WHERE funding_return.id = NEW.funding_return_id
           AND funding_return.funding_loan_id = pledge.funding_loan_id
    ) THEN
        RAISE EXCEPTION 'Returned pledge item must belong to the FundingLoan.';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION loans_guard_funding_custody_insert()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    projected_state varchar(32);
BEGIN
    SELECT custody_state INTO projected_state
      FROM loans_pawncollateralitem
     WHERE id = NEW.collateral_item_id
     FOR UPDATE;
    IF projected_state IS DISTINCT FROM NEW.from_state THEN
        RAISE EXCEPTION 'Custody movement must start at the projected state.';
    END IF;
    IF NEW.funding_pledge_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM loans_fundingpledgeitem item
         WHERE item.funding_pledge_id = NEW.funding_pledge_id
           AND item.collateral_item_id = NEW.collateral_item_id
    ) THEN
        RAISE EXCEPTION 'Funding pledge custody source does not contain collateral.';
    END IF;
    IF NEW.funding_return_id IS NOT NULL AND NOT EXISTS (
        SELECT 1
          FROM loans_fundingreturnitem return_item
          JOIN loans_fundingpledgeitem pledge_item
            ON pledge_item.id = return_item.pledge_item_id
         WHERE return_item.funding_return_id = NEW.funding_return_id
           AND pledge_item.collateral_item_id = NEW.collateral_item_id
    ) THEN
        RAISE EXCEPTION 'Funding return custody source does not contain collateral.';
    END IF;
    RETURN NEW;
END;
$$;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("loans", "0024_pawncollateralcustodyevent_loans_funding_pledge_custody_reversal_uniq_and_more"),
    ]

    operations = [
        migrations.RunSQL(sql=FORWARD_SQL, reverse_sql=REVERSE_SQL),
    ]
