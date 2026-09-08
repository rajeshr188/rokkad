from django.db import connection
sql = """
SELECT table_schema,
       MAX(CASE WHEN column_name='amount_base_currency' THEN 1 ELSE 0 END) AS has_amount_base_currency,
       MAX(CASE WHEN column_name='amount_base' THEN 1 ELSE 0 END) AS has_amount_base
FROM information_schema.columns
WHERE table_name='dea_ledgertransaction'
GROUP BY table_schema
ORDER BY table_schema;
"""
with connection.cursor() as c:
    c.execute(sql)
    rows = c.fetchall()
for r in rows:
    print(r)
