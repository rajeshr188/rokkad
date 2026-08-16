import django.db.models.deletion
from django.db import migrations, models


VIEW_BODY = r"""
WITH latest_statements AS (
    SELECT DISTINCT ON ("AccountNo_id", "ClosingBalance_currency")
        "AccountNo_id", created, "ClosingBalance", "ClosingBalance_currency"
    FROM dea_accountstatement
    ORDER BY "AccountNo_id", "ClosingBalance_currency", created DESC
),
credit_sums AS (
    SELECT at."Account_id", at.amount_currency,
        COALESCE(sum(CASE
            WHEN (ls.created IS NULL OR at.created > ls.created)
             AND at."XactTypeCode_id" = 'Cr' THEN at.amount
            ELSE 0::numeric END), 0::numeric) AS credit_sum
    FROM dea_accounttransaction at
    LEFT JOIN latest_statements ls
      ON at."Account_id" = ls."AccountNo_id"
     AND at.amount_currency::text = ls."ClosingBalance_currency"::text
    GROUP BY at."Account_id", at.amount_currency
),
debit_sums AS (
    SELECT at."Account_id", at.amount_currency,
        COALESCE(sum(CASE
            WHEN (ls.created IS NULL OR at.created > ls.created)
             AND at."XactTypeCode_id" = 'Dr' THEN at.amount
            ELSE 0::numeric END), 0::numeric) AS debit_sum
    FROM dea_accounttransaction at
    LEFT JOIN latest_statements ls
      ON at."Account_id" = ls."AccountNo_id"
     AND at.amount_currency::text = ls."ClosingBalance_currency"::text
    GROUP BY at."Account_id", at.amount_currency
),
currencies AS (
    SELECT DISTINCT "Account_id", amount_currency
    FROM dea_accounttransaction
)
SELECT
    a.id AS account_id,
    a.{counterparty_column},
    a."AccountType_Ext_id",
    COALESCE(ls."ClosingBalance_currency", c.amount_currency, 'INR'::text) AS currency,
    COALESCE(ls.created, NULL::timestamp with time zone) AS last_statement_date,
    COALESCE(ls."ClosingBalance", 0::numeric) AS last_statement_balance,
    COALESCE(cs.credit_sum, 0::numeric) AS credit_sum,
    COALESCE(ds.debit_sum, 0::numeric) AS debit_sum,
    CASE
        WHEN a."AccountType_Ext_id" IN
            (SELECT id FROM dea_accounttype_ext WHERE "XactTypeCode_id" = 'Dr')
        THEN COALESCE(ls."ClosingBalance", 0::numeric)
           + COALESCE(ds.debit_sum, 0::numeric)
           - COALESCE(cs.credit_sum, 0::numeric)
        ELSE COALESCE(ls."ClosingBalance", 0::numeric)
           + COALESCE(cs.credit_sum, 0::numeric)
           - COALESCE(ds.debit_sum, 0::numeric)
    END AS current_balance
FROM dea_account a
LEFT JOIN currencies c ON a.id = c."Account_id"
LEFT JOIN latest_statements ls
  ON a.id = ls."AccountNo_id"
 AND c.amount_currency = ls."ClosingBalance_currency"
LEFT JOIN credit_sums cs
  ON a.id = cs."Account_id" AND c.amount_currency = cs.amount_currency
LEFT JOIN debit_sums ds
  ON a.id = ds."Account_id" AND c.amount_currency = ds.amount_currency
"""


CREATE_PARTY_VIEW = (
    "DROP VIEW IF EXISTS account_balances;\n"
    "CREATE VIEW account_balances AS\n"
    + VIEW_BODY.format(counterparty_column="party_id")
    + ";"
)

class Migration(migrations.Migration):
    dependencies = [("dea", "0044_account_party")]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=CREATE_PARTY_VIEW,
                    reverse_sql=migrations.RunSQL.noop,
                )
            ],
            state_operations=[],
        )
    ]
