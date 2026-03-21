from django.db import migrations


INVENTORY_TXN_PROJECTION_SQL = """
CREATE OR REPLACE VIEW inventory_txn_projection AS
SELECT
    st.id AS transaction_id,
    st.created,
    CASE WHEN st.stock_id IS NOT NULL THEN 'LOT' ELSE 'ITEM' END AS subject_type,
    COALESCE(st.stock_id, st.stock_item_id) AS subject_id,
    st.stock_id,
    st.stock_item_id,
    st.quantity,
    st.weight,
    st.movement_type_id,
    mv.direction AS movement_direction,
    st.journal_entry_id,
    st.description
FROM product_stocktransaction st
JOIN product_movement mv ON mv.id = st.movement_type_id;
"""


INVENTORY_BALANCE_SQL = """
CREATE OR REPLACE VIEW inventory_balance AS
WITH latest_statements AS (
    SELECT DISTINCT ON (subject_type, subject_id)
        subject_type,
        subject_id,
        method AS statement_method,
        created AS statement_created,
        COALESCE("Closing_wt", 0.0)::numeric(14, 3) AS closing_wt,
        COALESCE("Closing_qty", 0)::integer AS closing_qty,
        COALESCE(total_wt_in, 0.0)::numeric(14, 3) AS total_wt_in,
        COALESCE(total_wt_out, 0.0)::numeric(14, 3) AS total_wt_out,
        COALESCE(total_qty_in, 0)::integer AS total_qty_in,
        COALESCE(total_qty_out, 0)::integer AS total_qty_out
    FROM (
        SELECT
            CASE WHEN ss.stock_id IS NOT NULL THEN 'LOT' ELSE 'ITEM' END AS subject_type,
            COALESCE(ss.stock_id, ss.stock_item_id) AS subject_id,
            ss.method,
            ss.created,
            ss."Closing_wt",
            ss."Closing_qty",
            ss.total_wt_in,
            ss.total_wt_out,
            ss.total_qty_in,
            ss.total_qty_out
        FROM product_stockstatement ss
    ) statements
    ORDER BY subject_type, subject_id, statement_created DESC
),
subjects AS (
    SELECT
        'LOT'::varchar(4) AS subject_type,
        s.id AS subject_id,
        s.id AS stock_id,
        NULL::bigint AS stock_item_id
    FROM product_stock s
    UNION ALL
    SELECT
        'ITEM'::varchar(4) AS subject_type,
        si.id AS subject_id,
        NULL::bigint AS stock_id,
        si.id AS stock_item_id
    FROM product_stockitem si
)
SELECT
    subj.subject_type,
    subj.subject_id,
    subj.stock_id,
    subj.stock_item_id,
    ls.statement_method,
    ls.statement_created,
    COALESCE(ls.closing_wt, 0.0)::numeric(14, 3) AS closing_wt,
    COALESCE(ls.closing_qty, 0)::integer AS closing_qty,
    COALESCE(ls.total_wt_in, 0.0)::numeric(14, 3) AS total_wt_in,
    COALESCE(ls.total_wt_out, 0.0)::numeric(14, 3) AS total_wt_out,
    COALESCE(ls.total_qty_in, 0)::integer AS total_qty_in,
    COALESCE(ls.total_qty_out, 0)::integer AS total_qty_out,
    COALESCE(SUM(CASE WHEN txn.movement_direction = '+' THEN txn.quantity ELSE 0 END), 0)::integer AS in_qty,
    COALESCE(SUM(CASE WHEN txn.movement_direction = '-' THEN txn.quantity ELSE 0 END), 0)::integer AS out_qty,
    COALESCE(SUM(CASE WHEN txn.movement_direction = '+' THEN txn.weight ELSE 0 END), 0.0)::numeric(14, 3) AS in_wt,
    COALESCE(SUM(CASE WHEN txn.movement_direction = '-' THEN txn.weight ELSE 0 END), 0.0)::numeric(14, 3) AS out_wt,
    (
        COALESCE(ls.closing_qty, 0)
        + COALESCE(SUM(CASE WHEN txn.movement_direction = '+' THEN txn.quantity ELSE 0 END), 0)
        - COALESCE(SUM(CASE WHEN txn.movement_direction = '-' THEN txn.quantity ELSE 0 END), 0)
    )::integer AS balance_qty,
    (
        COALESCE(ls.closing_wt, 0.0)
        + COALESCE(SUM(CASE WHEN txn.movement_direction = '+' THEN txn.weight ELSE 0 END), 0.0)
        - COALESCE(SUM(CASE WHEN txn.movement_direction = '-' THEN txn.weight ELSE 0 END), 0.0)
    )::numeric(14, 3) AS balance_wt
FROM subjects subj
LEFT JOIN latest_statements ls
    ON ls.subject_type = subj.subject_type
    AND ls.subject_id = subj.subject_id
LEFT JOIN inventory_txn_projection txn
    ON txn.subject_type = subj.subject_type
    AND txn.subject_id = subj.subject_id
    AND (ls.statement_created IS NULL OR txn.created >= ls.statement_created)
GROUP BY
    subj.subject_type,
    subj.subject_id,
    subj.stock_id,
    subj.stock_item_id,
    ls.statement_method,
    ls.statement_created,
    ls.closing_wt,
    ls.closing_qty,
    ls.total_wt_in,
    ls.total_wt_out,
    ls.total_qty_in,
    ls.total_qty_out;
"""


STOCK_BALANCE_SQL = """
CREATE OR REPLACE VIEW stock_balance AS
SELECT
    stock_id,
    closing_wt,
    closing_qty,
    in_wt,
    in_qty,
    out_wt,
    out_qty
FROM inventory_balance
WHERE subject_type = 'LOT' AND stock_id IS NOT NULL;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("product", "0010_pr2_add_union_fk_constraints"),
    ]

    operations = [
        migrations.RunSQL(
            sql=INVENTORY_TXN_PROJECTION_SQL,
            reverse_sql="DROP VIEW IF EXISTS inventory_txn_projection;",
        ),
        migrations.RunSQL(
            sql=INVENTORY_BALANCE_SQL,
            reverse_sql="DROP VIEW IF EXISTS inventory_balance;",
        ),
        migrations.RunSQL(
            sql=STOCK_BALANCE_SQL,
            reverse_sql="DROP VIEW IF EXISTS stock_balance;",
        ),
    ]