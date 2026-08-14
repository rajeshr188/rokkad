---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

-- Type: money_value

-- DROP TYPE IF EXISTS public.money_value;

CREATE TYPE public.money_value AS
(
	amount numeric(14,3),
	currency character varying(3)
);

ALTER TYPE public.money_value
    OWNER TO postgres;

CREATE OR REPLACE FUNCTION array_math( 
    opening_balance money_value[],
    total_debit money_value[],
    total_credit money_value[]
) RETURNS money_value[] AS $$
DECLARE
    combined_balance money_value[] := '{}';
BEGIN
    -- Step 1: Start with the opening balance
    combined_balance := opening_balance;

    -- Step 2: Add total debit to the combined balance
    combined_balance := ARRAY(
        SELECT
            ROW(coalesce(o.amount, 0) + coalesce(d.amount, 0), COALESCE(o.currency, d.currency))::money_value
        FROM
            unnest(combined_balance) AS o(amount, currency)
        FULL OUTER JOIN unnest(total_debit) AS d(amount, currency)
            ON o.currency = d.currency
    );

    -- Step 3: Subtract total credit from the combined balance
    combined_balance := ARRAY(
        SELECT
            ROW(coalesce(o.amount, 0) - coalesce(c.amount, 0), COALESCE(o.currency, c.currency))::money_value
        FROM
            unnest(combined_balance) AS o(amount, currency)
        FULL OUTER JOIN unnest(total_credit) AS c(amount, currency)
            ON o.currency = c.currency
    );

    -- Step 4: Return the final combined balance
    RETURN combined_balance;
END;
$$ LANGUAGE plpgsql;


Example Walkthrough
Let's say we have the following inputs:

Opening Balance:

sql
Copy
Edit
ARRAY[ROW(100, 'USD')::moneyvalue, ROW(200, 'EUR')::moneyvalue]
Total Debit:

sql
Copy
Edit
ARRAY[ROW(50, 'USD')::moneyvalue, ROW(100, 'EUR')::moneyvalue]
Total Credit:

sql
Copy
Edit
ARRAY[ROW(30, 'USD')::moneyvalue, ROW(50, 'EUR')::moneyvalue]
The function will perform the following steps:

Step 1: Start with the opening_balance:

sql
Copy
Edit
combined_balance = ARRAY[ROW(100, 'USD'), ROW(200, 'EUR')]
Step 2: Add the total_debit to combined_balance:

sql
Copy
Edit
combined_balance = 
  ARRAY[ROW(100, 'USD') + ROW(50, 'USD'), ROW(200, 'EUR') + ROW(100, 'EUR')]
  = ARRAY[ROW(150, 'USD'), ROW(300, 'EUR')]
Step 3: Subtract the total_credit from combined_balance:

sql
Copy
Edit
combined_balance = 
  ARRAY[ROW(150, 'USD') - ROW(30, 'USD'), ROW(300, 'EUR') - ROW(50, 'EUR')]
  = ARRAY[ROW(120, 'USD'), ROW(250, 'EUR')]
Step 4: Return the final combined_balance:

sql
Copy
Edit
RETURN ARRAY[ROW(120, 'USD'), ROW(250, 'EUR')]
Key Points
Handling Currencies: The function ensures that calculations are performed per currency, and if a currency exists in one array but not the other, it is handled correctly using coalesce().
Set-based Operations: Using unnest() and SQL joins, the function operates on the entire array as a set, avoiding manual iteration and ensuring better performance.
Flexibility: The FULL OUTER JOIN ensures that we can safely add or subtract balances even if the currencies don't match across opening_balance, total_debit, and total_credit.

You can use this function to calculate the combined balance of multiple accounts, wallets, or any other financial entities with different currencies.

Sure! Let's break down each step of the array_math() function to understand how it works:

Function Definition
sql
Copy
Edit
CREATE OR REPLACE FUNCTION array_math(
    opening_balance moneyvalue[],  -- Array of moneyvalue for opening balance
    total_debit moneyvalue[],      -- Array of moneyvalue for total debits
    total_credit moneyvalue[]      -- Array of moneyvalue for total credits
) RETURNS moneyvalue[] AS $$  -- Returns an array of moneyvalue (final balance)
The function array_math takes three parameters, each an array of moneyvalue[], which represents a collection of amounts and their corresponding currencies.

Step 1: Initialize combined_balance
sql
Copy
Edit
DECLARE
    combined_balance moneyvalue[] := '{}';  -- Declare a variable to hold the combined balance
BEGIN
    -- Step 1: Start with the opening balance
    combined_balance := opening_balance;
We declare a variable combined_balance that will hold the running total of the balances (starting with the opening_balance).
The opening_balance parameter is passed to this variable as the starting point of the calculation.
Step 2: Add Total Debit to the Combined Balance
sql
Copy
Edit
    -- Step 2: Add total debit to the combined balance
    PERFORM
    SELECT INTO combined_balance
        ARRAY(
            SELECT
                ROW(coalesce(o.amount, 0) + coalesce(d.amount, 0), COALESCE(o.currency, d.currency))::moneyvalue
            FROM
                unnest(combined_balance) AS o(amount, currency)
                FULL OUTER JOIN unnest(total_debit) AS d(amount, currency)
                ON o.currency = d.currency
        )
    ;
Purpose: This step adds the amounts in the total_debit array to the combined_balance array.
Explanation:
The unnest() function is used to turn the combined_balance and total_debit arrays into table-like structures. It essentially "unwraps" the arrays so that each element (amount and currency) can be processed.
The FULL OUTER JOIN ensures that even if there are currencies in combined_balance that aren't in total_debit (or vice versa), they are included in the result. This way, we don't lose data when there is no matching currency between the two arrays.
coalesce(o.amount, 0): This handles the case where combined_balance might have a NULL value for the amount, treating it as 0 (default behavior).
coalesce(d.amount, 0): Similarly, it ensures that if the total_debit does not have a specific value for an amount, it defaults to 0.
The result of the join is a combination of amounts for the same currency, where the amounts are summed (debit amounts are added) for matching currencies.
The resulting rows are aggregated into a new array and assigned back to combined_balance.
Step 3: Subtract Total Credit from the Combined Balance
sql
Copy
Edit
    -- Step 3: Subtract total credit from the combined balance
    PERFORM
    SELECT INTO combined_balance
        ARRAY(
            SELECT
                ROW(coalesce(o.amount, 0) - coalesce(c.amount, 0), COALESCE(o.currency, c.currency))::moneyvalue
            FROM
                unnest(combined_balance) AS o(amount, currency)
                FULL OUTER JOIN unnest(total_credit) AS c(amount, currency)
                ON o.currency = c.currency
        )
    ;
Purpose: This step subtracts the amounts in the total_credit array from the combined_balance array.
Explanation:
Similar to Step 2, the combined_balance and total_credit arrays are turned into table-like structures using unnest().
A FULL OUTER JOIN ensures that even if there are currencies in combined_balance that don't exist in total_credit, they are retained in the result.
coalesce(o.amount, 0) and coalesce(c.amount, 0) ensure that NULL values are treated as 0 when performing the subtraction.
The amounts from combined_balance are subtracted by the corresponding amounts in total_credit, resulting in an updated balance for each currency.
This subtraction is performed for all matching currencies.
The result of the operation is assigned back to combined_balance, which now holds the updated balance after the credit amounts have been subtracted.
Step 4: Return the Final Combined Balance
sql
Copy
Edit
    -- Step 4: Return the final combined balance
    RETURN combined_balance;
END;
$$ LANGUAGE plpgsql;
Purpose: The final balance, which is stored in the combined_balance array, is returned as the result of the function.
Explanation: After performing the debit and credit adjustments, combined_balance will hold the calculated balance for each currency, and this is returned as the output of the function.
Example Walkthrough
Let's say we have the following inputs:

Opening Balance:

sql
Copy
Edit
ARRAY[ROW(100, 'USD')::moneyvalue, ROW(200, 'EUR')::moneyvalue]
Total Debit:

sql
Copy
Edit
ARRAY[ROW(50, 'USD')::moneyvalue, ROW(100, 'EUR')::moneyvalue]
Total Credit:

sql
Copy
Edit
ARRAY[ROW(30, 'USD')::moneyvalue, ROW(50, 'EUR')::moneyvalue]
The function will perform the following steps:

Step 1: Start with the opening_balance:

sql
Copy
Edit
combined_balance = ARRAY[ROW(100, 'USD'), ROW(200, 'EUR')]
Step 2: Add the total_debit to combined_balance:

sql
Copy
Edit
combined_balance = 
  ARRAY[ROW(100, 'USD') + ROW(50, 'USD'), ROW(200, 'EUR') + ROW(100, 'EUR')]
  = ARRAY[ROW(150, 'USD'), ROW(300, 'EUR')]
Step 3: Subtract the total_credit from combined_balance:

sql
Copy
Edit
combined_balance = 
  ARRAY[ROW(150, 'USD') - ROW(30, 'USD'), ROW(300, 'EUR') - ROW(50, 'EUR')]
  = ARRAY[ROW(120, 'USD'), ROW(250, 'EUR')]
Step 4: Return the final combined_balance:

sql
Copy
Edit
RETURN ARRAY[ROW(120, 'USD'), ROW(250, 'EUR')]
Key Points
Handling Currencies: The function ensures that calculations are performed per currency, and if a currency exists in one array but not the other, it is handled correctly using coalesce().
Set-based Operations: Using unnest() and SQL joins, the function operates on the entire array as a set, avoiding manual iteration and ensuring better performance.
Flexibility: The FULL OUTER JOIN ensures that we can safely add or subtract balances even if the currencies don't match across opening_balance, total_debit, and total_credit.
Let me know if you need further clarification!

WITH latest_statements AS (
    SELECT 
        ls.ledgerno_id,
        ls."ClosingBalance" AS opening_balance,
        ls.created AS latest_statement_date
    FROM jcl.dea_ledgerstatement ls
    WHERE ls.created = (
        SELECT max(ls_sub.created) AS max
        FROM jcl.dea_ledgerstatement ls_sub
        WHERE ls_sub.ledgerno_id = ls.ledgerno_id
    )
), credits AS (
    SELECT 
        lt.ledgerno_id AS ledger_id,
        array_agg(ROW(lt.amount::numeric(14,3), lt.amount_currency)::money_value) AS total_credit
    FROM jcl.dea_ledgertransaction lt
    GROUP BY lt.ledgerno_id
), debits AS (
    SELECT 
        lt.ledgerno_dr_id AS ledger_id,
        array_agg(ROW(lt.amount::numeric(14,3), lt.amount_currency)::money_value) AS total_debit
    FROM jcl.dea_ledgertransaction lt
    GROUP BY lt.ledgerno_dr_id
), account_credits AS (
    SELECT 
        at.ledgerno_id AS ledger_id,
        array_agg(ROW(at.amount::numeric(14,3), at.amount_currency)::money_value) AS total_credit
    FROM jcl.dea_accounttransaction at
    WHERE at.XactTypeCode = 'cr'
    GROUP BY at.ledgerno_id
), account_debits AS (
    SELECT 
        at.ledgerno_id AS ledger_id,
        array_agg(ROW(at.amount::numeric(14,3), at.amount_currency)::money_value) AS total_debit
    FROM jcl.dea_accounttransaction at
    WHERE at.XactTypeCode = 'dr'
    GROUP BY at.ledgerno_id
), aggregates AS (
    SELECT 
        l.id AS ledger_id,
        COALESCE(ls.opening_balance, '{}'::money_value[]) AS opening_balance,
        COALESCE(c.total_credit, '{}'::money_value[]) AS total_credit,
        COALESCE(d.total_debit, '{}'::money_value[]) AS total_debit,
        COALESCE(ac.total_credit, '{}'::money_value[]) AS account_credit,
        COALESCE(ad.total_debit, '{}'::money_value[]) AS account_debit,
        array_math(
            COALESCE(ls.opening_balance, '{}'::money_value[]),
            COALESCE(d.total_debit, '{}'::money_value[]) + COALESCE(ad.total_debit, '{}'::money_value[]),
            COALESCE(c.total_credit, '{}'::money_value[]) + COALESCE(ac.total_credit, '{}'::money_value[])
        ) AS closing_balance
    FROM jcl.dea_ledger l
    LEFT JOIN latest_statements ls ON ls.ledgerno_id = l.id
    LEFT JOIN credits c ON c.ledger_id = l.id
    LEFT JOIN debits d ON d.ledger_id = l.id
    LEFT JOIN account_credits ac ON ac.ledger_id = l.id
    LEFT JOIN account_debits ad ON ad.ledger_id = l.id
)
SELECT 
    ledger_id,
    opening_balance,
    total_credit,
    total_debit,
    closing_balance
FROM aggregates
ORDER BY ledger_id;

This query calculates the closing balance for each ledger by combining the opening balance, total credits, total debits, account credits, and account debits. It uses the array_math() function to perform the balance calculations based on the provided inputs.
