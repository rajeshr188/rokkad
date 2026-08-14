from django.db import migrations


FORWARD_SQL = r"""
CREATE OR REPLACE FUNCTION loans_guard_funding_loan()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.state <> 'DRAFT' THEN
            RAISE EXCEPTION 'FundingLoan must be created in DRAFT state.';
        END IF;
        RETURN NEW;
    END IF;
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'FundingLoan rows cannot be deleted.';
    END IF;
    IF OLD.workspace_id IS DISTINCT FROM NEW.workspace_id
       OR OLD.lender_id IS DISTINCT FROM NEW.lender_id
       OR OLD.funding_number IS DISTINCT FROM NEW.funding_number
       OR OLD.created_at IS DISTINCT FROM NEW.created_at
       OR OLD.created_by_id IS DISTINCT FROM NEW.created_by_id THEN
        RAISE EXCEPTION 'FundingLoan identity is immutable.';
    END IF;
    IF OLD.state IS DISTINCT FROM NEW.state AND NOT (
        (OLD.state = 'DRAFT' AND NEW.state IN ('ACTIVE', 'CANCELLED'))
        OR (OLD.state = 'ACTIVE' AND NEW.state = 'SETTLEMENT_PENDING')
        OR (OLD.state = 'SETTLEMENT_PENDING' AND NEW.state IN ('ACTIVE', 'CLOSED'))
    ) THEN
        RAISE EXCEPTION 'Illegal FundingLoan state transition from % to %.', OLD.state, NEW.state;
    END IF;
    IF OLD.state = 'DRAFT' AND NEW.state = 'ACTIVE' AND (
        NOT EXISTS (
            SELECT 1 FROM loans_fundingloantermssnapshot terms
             WHERE terms.funding_loan_id = NEW.id
        )
        OR NOT EXISTS (
            SELECT 1 FROM loans_fundingloanevent event
             WHERE event.funding_loan_id = NEW.id
               AND event.event_kind = 'ACTIVATION'
        )
        OR NOT EXISTS (
            SELECT 1 FROM loans_fundingpledge pledge
             WHERE pledge.funding_loan_id = NEW.id
        )
                OR NOT EXISTS (
                        SELECT 1
                            FROM loans_fundingpledge pledge
                            JOIN loans_fundingpledgeitem pledge_item
                                ON pledge_item.funding_pledge_id = pledge.id
                         WHERE pledge.funding_loan_id = NEW.id
                )
                OR EXISTS (
                        SELECT 1
                            FROM loans_fundingpledge pledge
                            JOIN loans_fundingpledgeitem pledge_item
                                ON pledge_item.funding_pledge_id = pledge.id
                         WHERE pledge.funding_loan_id = NEW.id
                             AND NOT EXISTS (
                                     SELECT 1 FROM loans_pawncollateralcustodyevent custody
                                        WHERE custody.funding_pledge_id = pledge.id
                                            AND custody.collateral_item_id = pledge_item.collateral_item_id
                                            AND custody.from_state = 'IN_VAULT'
                                            AND custody.to_state = 'WITH_FUNDING_LENDER'
                             )
                )
    ) THEN
                RAISE EXCEPTION 'FundingLoan activation requires terms, event, pledge items, and custody evidence.';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER loans_funding_loan_guard
BEFORE INSERT OR UPDATE OR DELETE ON loans_fundingloan
FOR EACH ROW EXECUTE FUNCTION loans_guard_funding_loan();

CREATE OR REPLACE FUNCTION loans_guard_funding_immutable()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'FundingLoan evidence in % is immutable.', TG_TABLE_NAME;
END;
$$;

CREATE TRIGGER loans_funding_terms_immutable
BEFORE UPDATE OR DELETE ON loans_fundingloantermssnapshot
FOR EACH ROW EXECUTE FUNCTION loans_guard_funding_immutable();
CREATE TRIGGER loans_funding_event_immutable
BEFORE UPDATE OR DELETE ON loans_fundingloanevent
FOR EACH ROW EXECUTE FUNCTION loans_guard_funding_immutable();
CREATE TRIGGER loans_funding_pledge_immutable
BEFORE UPDATE OR DELETE ON loans_fundingpledge
FOR EACH ROW EXECUTE FUNCTION loans_guard_funding_immutable();
CREATE TRIGGER loans_funding_return_immutable
BEFORE UPDATE OR DELETE ON loans_fundingreturn
FOR EACH ROW EXECUTE FUNCTION loans_guard_funding_immutable();
CREATE TRIGGER loans_funding_return_item_immutable
BEFORE UPDATE OR DELETE ON loans_fundingreturnitem
FOR EACH ROW EXECUTE FUNCTION loans_guard_funding_immutable();

CREATE OR REPLACE FUNCTION loans_guard_funding_header_insert()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    funding_workspace_id bigint;
BEGIN
    SELECT workspace_id INTO funding_workspace_id
      FROM loans_fundingloan
     WHERE id = NEW.funding_loan_id;
    IF NEW.workspace_id IS DISTINCT FROM funding_workspace_id THEN
        RAISE EXCEPTION 'Funding evidence workspace must match its FundingLoan.';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER loans_funding_pledge_insert_guard
BEFORE INSERT ON loans_fundingpledge
FOR EACH ROW EXECUTE FUNCTION loans_guard_funding_header_insert();
CREATE TRIGGER loans_funding_return_insert_guard
BEFORE INSERT ON loans_fundingreturn
FOR EACH ROW EXECUTE FUNCTION loans_guard_funding_header_insert();

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

CREATE TRIGGER loans_funding_pledge_item_guard
BEFORE INSERT OR UPDATE OR DELETE ON loans_fundingpledgeitem
FOR EACH ROW EXECUTE FUNCTION loans_guard_funding_pledge_item();

CREATE OR REPLACE FUNCTION loans_guard_funding_event_insert()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    original loans_fundingloanevent%ROWTYPE;
BEGIN
    IF NEW.sequence <> COALESCE((
        SELECT MAX(event.sequence) + 1
          FROM loans_fundingloanevent event
         WHERE event.funding_loan_id = NEW.funding_loan_id
    ), 1) THEN
        RAISE EXCEPTION 'FundingLoan events must use the next sequence.';
    END IF;

    IF NEW.event_kind = 'ACTIVATION' AND NOT (
        NEW.principal_amount > 0 AND NEW.interest_amount = 0 AND NEW.fee_amount = 0
    ) THEN
        RAISE EXCEPTION 'Funding activation amount shape is invalid.';
    ELSIF NEW.event_kind = 'INTEREST_ACCRUAL' AND NOT (
        NEW.principal_amount = 0 AND NEW.interest_amount > 0 AND NEW.fee_amount = 0
    ) THEN
        RAISE EXCEPTION 'Funding interest amount shape is invalid.';
    ELSIF NEW.event_kind = 'FEE_ASSESSMENT' AND NOT (
        NEW.principal_amount = 0 AND NEW.interest_amount = 0 AND NEW.fee_amount > 0
    ) THEN
        RAISE EXCEPTION 'Funding fee amount shape is invalid.';
    ELSIF NEW.event_kind = 'REPAYMENT' AND NOT (
        NEW.principal_amount + NEW.interest_amount + NEW.fee_amount > 0
    ) THEN
        RAISE EXCEPTION 'Funding repayment must allocate a positive amount.';
    END IF;

    IF NEW.event_kind <> 'REVERSAL' THEN
        IF BTRIM(NEW.reason) <> '' THEN
            RAISE EXCEPTION 'Only funding reversals may include a reason.';
        END IF;
        RETURN NEW;
    END IF;
    IF BTRIM(NEW.reason) = '' THEN
        RAISE EXCEPTION 'Funding reversal reason is required.';
    END IF;
    SELECT * INTO original
      FROM loans_fundingloanevent
     WHERE id = NEW.reversal_of_id
     FOR UPDATE;
    IF NOT FOUND OR original.event_kind = 'REVERSAL'
       OR original.funding_loan_id IS DISTINCT FROM NEW.funding_loan_id THEN
        RAISE EXCEPTION 'Funding reversal requires an original event from the same loan.';
    END IF;
    IF NEW.principal_amount IS DISTINCT FROM original.principal_amount
       OR NEW.interest_amount IS DISTINCT FROM original.interest_amount
       OR NEW.fee_amount IS DISTINCT FROM original.fee_amount THEN
        RAISE EXCEPTION 'Funding reversal must exactly compensate the original event.';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM loans_fundingloanevent later
         WHERE later.funding_loan_id = NEW.funding_loan_id
           AND later.sequence > original.sequence
           AND later.event_kind <> 'REVERSAL'
           AND NOT EXISTS (
               SELECT 1 FROM loans_fundingloanevent reversal
                WHERE reversal.reversal_of_id = later.id
           )
    ) THEN
        RAISE EXCEPTION 'Later active funding events must be reversed first.';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER loans_funding_event_insert_guard
BEFORE INSERT ON loans_fundingloanevent
FOR EACH ROW EXECUTE FUNCTION loans_guard_funding_event_insert();

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

CREATE TRIGGER loans_funding_custody_insert_guard
BEFORE INSERT ON loans_pawncollateralcustodyevent
FOR EACH ROW EXECUTE FUNCTION loans_guard_funding_custody_insert();

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

CREATE TRIGGER loans_funding_return_item_insert_guard
BEFORE INSERT ON loans_fundingreturnitem
FOR EACH ROW EXECUTE FUNCTION loans_guard_funding_return_item_insert();

CREATE OR REPLACE FUNCTION loans_verify_funding_return_projection()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
        IF NOT EXISTS (
                SELECT 1 FROM loans_fundingpledgeitem pledge_item
                 WHERE pledge_item.id = NEW.pledge_item_id
                     AND pledge_item.released_at IS NOT NULL
        ) THEN
                RAISE EXCEPTION 'Funding return must release its pledge item in the same transaction.';
        END IF;
        RETURN NULL;
END;
$$;

CREATE CONSTRAINT TRIGGER loans_funding_return_projection_guard
AFTER INSERT ON loans_fundingreturnitem
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION loans_verify_funding_return_projection();

CREATE OR REPLACE FUNCTION loans_verify_custody_projection()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM loans_pawncollateralcustodyevent later
         WHERE later.collateral_item_id = NEW.collateral_item_id
           AND later.id > NEW.id
    ) THEN
        RETURN NULL;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM loans_pawncollateralitem item
         WHERE item.id = NEW.collateral_item_id
           AND item.custody_state = NEW.to_state
    ) THEN
        RAISE EXCEPTION 'Custody projection must match the latest movement.';
    END IF;
    RETURN NULL;
END;
$$;

CREATE CONSTRAINT TRIGGER loans_custody_projection_guard
AFTER INSERT ON loans_pawncollateralcustodyevent
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION loans_verify_custody_projection();

CREATE TRIGGER loans_custody_immutable
BEFORE UPDATE OR DELETE ON loans_pawncollateralcustodyevent
FOR EACH ROW EXECUTE FUNCTION loans_guard_funding_immutable();
"""


REVERSE_SQL = r"""
DROP TRIGGER IF EXISTS loans_custody_immutable ON loans_pawncollateralcustodyevent;
DROP TRIGGER IF EXISTS loans_custody_projection_guard ON loans_pawncollateralcustodyevent;
DROP FUNCTION IF EXISTS loans_verify_custody_projection();
DROP TRIGGER IF EXISTS loans_funding_return_projection_guard ON loans_fundingreturnitem;
DROP FUNCTION IF EXISTS loans_verify_funding_return_projection();
DROP TRIGGER IF EXISTS loans_funding_return_item_insert_guard ON loans_fundingreturnitem;
DROP FUNCTION IF EXISTS loans_guard_funding_return_item_insert();
DROP TRIGGER IF EXISTS loans_funding_custody_insert_guard ON loans_pawncollateralcustodyevent;
DROP FUNCTION IF EXISTS loans_guard_funding_custody_insert();
DROP TRIGGER IF EXISTS loans_funding_event_insert_guard ON loans_fundingloanevent;
DROP FUNCTION IF EXISTS loans_guard_funding_event_insert();
DROP TRIGGER IF EXISTS loans_funding_pledge_item_guard ON loans_fundingpledgeitem;
DROP FUNCTION IF EXISTS loans_guard_funding_pledge_item();
DROP TRIGGER IF EXISTS loans_funding_return_item_immutable ON loans_fundingreturnitem;
DROP TRIGGER IF EXISTS loans_funding_return_immutable ON loans_fundingreturn;
DROP TRIGGER IF EXISTS loans_funding_pledge_immutable ON loans_fundingpledge;
DROP TRIGGER IF EXISTS loans_funding_event_immutable ON loans_fundingloanevent;
DROP TRIGGER IF EXISTS loans_funding_terms_immutable ON loans_fundingloantermssnapshot;
DROP TRIGGER IF EXISTS loans_funding_return_insert_guard ON loans_fundingreturn;
DROP TRIGGER IF EXISTS loans_funding_pledge_insert_guard ON loans_fundingpledge;
DROP FUNCTION IF EXISTS loans_guard_funding_header_insert();
DROP FUNCTION IF EXISTS loans_guard_funding_immutable();
DROP TRIGGER IF EXISTS loans_funding_loan_guard ON loans_fundingloan;
DROP FUNCTION IF EXISTS loans_guard_funding_loan();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("loans", "0019_fundingloan_fundingloanevent_fundingloansequence_and_more"),
    ]

    operations = [migrations.RunSQL(sql=FORWARD_SQL, reverse_sql=REVERSE_SQL)]