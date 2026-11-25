-- tests/silver_rule_tests.sql : synthetic-row tests for the Silver rules (run via execute_sql_read_only in Stage 6; NOT run in a dry run).
-- Each statement returns one column `mismatches`; expected value is 0. Expected outputs are hand-computed in the `-> ` comments.

-- T1 email normalization + flag (dim_customer.email, is_email_missing; rule-email-nullable-flagged)
WITH src AS (SELECT * FROM VALUES
    ('C1', '  A@X.com '),            -- -> email 'a@x.com', is_email_missing false
    ('C2', CAST(NULL AS STRING)),    -- -> email NULL,      is_email_missing true
    ('C3', '   ')                    -- -> email NULL,      is_email_missing true
  AS t(customer_id, email)),
out AS (SELECT customer_id, NULLIF(LOWER(TRIM(email)), '') AS email, (email IS NULL OR TRIM(email) = '') AS is_email_missing FROM src),
exp AS (SELECT * FROM VALUES ('C1', 'a@x.com', FALSE), ('C2', CAST(NULL AS STRING), TRUE), ('C3', CAST(NULL AS STRING), TRUE) AS e(customer_id, email, is_email_missing))
SELECT COUNT(*) AS mismatches FROM out o FULL OUTER JOIN exp e ON o.customer_id = e.customer_id
WHERE o.customer_id IS NULL OR e.customer_id IS NULL OR NOT (o.email <=> e.email) OR o.is_email_missing <> e.is_email_missing;

-- T2 cast failure detection (quantity INT, unit_sold_price DECIMAL(18,2)): NULL is not a failure, bad text is
WITH src AS (SELECT * FROM VALUES
    ('I1', '2',  '10.50'),           -- -> qty 2,    price 10.50, no failure
    ('I2', 'x',  'abc'),             -- -> qty NULL, price NULL,  failure on quantity (first CASE branch)
    ('I3', CAST(NULL AS STRING), CAST(NULL AS STRING))  -- -> NULL, NULL, no failure
  AS t(item_id, quantity, unit_sold_price)),
out AS (SELECT item_id, TRY_CAST(quantity AS INT) AS q, TRY_CAST(unit_sold_price AS DECIMAL(18,2)) AS p,
               CASE WHEN quantity IS NOT NULL AND TRY_CAST(quantity AS INT) IS NULL THEN 'cast_failure:quantity'
                    WHEN unit_sold_price IS NOT NULL AND TRY_CAST(unit_sold_price AS DECIMAL(18,2)) IS NULL THEN 'cast_failure:unit_sold_price' END AS reason FROM src),
exp AS (SELECT * FROM VALUES ('I1', 2, CAST(10.50 AS DECIMAL(18,2)), CAST(NULL AS STRING)), ('I2', CAST(NULL AS INT), CAST(NULL AS DECIMAL(18,2)), 'cast_failure:quantity'), ('I3', CAST(NULL AS INT), CAST(NULL AS DECIMAL(18,2)), CAST(NULL AS STRING)) AS e(item_id, q, p, reason))
SELECT COUNT(*) AS mismatches FROM out o JOIN exp e ON o.item_id = e.item_id WHERE NOT (o.q <=> e.q) OR NOT (o.p <=> e.p) OR NOT (o.reason <=> e.reason);

-- T3 domain check (rule-loyalty-tier-domain): value in domain after TRIM passes; NULL or other fails
WITH src AS (SELECT * FROM VALUES ('A', 'Gold'), ('B', ' Silver '), ('C', 'Diamond'), ('D', CAST(NULL AS STRING)) AS t(k, loyalty_tier)),
out AS (SELECT k, NOT COALESCE(TRIM(loyalty_tier) IN ('Bronze', 'Silver', 'Gold', 'Platinum'), FALSE) AS violation FROM src),
exp AS (SELECT * FROM VALUES ('A', FALSE), ('B', FALSE), ('C', TRUE), ('D', TRUE) AS e(k, violation))   -- Gold ok, Silver ok, Diamond bad, NULL bad
SELECT COUNT(*) AS mismatches FROM out o JOIN exp e ON o.k = e.k WHERE o.violation <> e.violation;

-- T4 reconciliation flag, OQ1 option (a): gross - discount = items_total, as the rule is written
WITH src AS (SELECT * FROM VALUES
    ('O1', CAST(200.00 AS DECIMAL(18,2)), CAST(20.00 AS DECIMAL(18,2)), CAST(200.00 AS DECIMAL(18,2))),  -- 180 <> 200 -> false
    ('O2', CAST(120.00 AS DECIMAL(18,2)), CAST(0.00 AS DECIMAL(18,2)),  CAST(120.00 AS DECIMAL(18,2))),  -- 120 = 120 -> true
    ('O3', CAST(75.00 AS DECIMAL(18,2)),  CAST(0.00 AS DECIMAL(18,2)),  CAST(65.00 AS DECIMAL(18,2))),   -- 75 <> 65  -> false
    ('O4', CAST(NULL AS DECIMAL(18,2)),   CAST(0.00 AS DECIMAL(18,2)),  CAST(10.00 AS DECIMAL(18,2))),   -- gross NULL -> NULL
    ('O5', CAST(100.00 AS DECIMAL(18,2)), CAST(10.00 AS DECIMAL(18,2)), CAST(90.00 AS DECIMAL(18,2)))    -- 90 = 90 -> true
  AS t(order_id, gross_amount, discount_amount, items_total)),
out AS (SELECT order_id, CASE WHEN items_total IS NULL OR gross_amount IS NULL OR discount_amount IS NULL THEN NULL ELSE (gross_amount - discount_amount = items_total) END AS r FROM src),
exp AS (SELECT * FROM VALUES ('O1', FALSE), ('O2', TRUE), ('O3', FALSE), ('O4', CAST(NULL AS BOOLEAN)), ('O5', TRUE) AS e(order_id, r))
SELECT COUNT(*) AS mismatches FROM out o JOIN exp e ON o.order_id = e.order_id WHERE NOT (o.r <=> e.r);

-- T5 latest-row-per-key dedup (Bronze -> Silver): the row with the greatest _landed_at wins
WITH src AS (SELECT * FROM VALUES
    ('K1', 'old', TIMESTAMP '2026-01-01 00:00:00'),
    ('K1', 'new', TIMESTAMP '2026-02-01 00:00:00'),   -- -> K1 keeps 'new'
    ('K2', 'only', TIMESTAMP '2026-01-15 00:00:00')   -- -> K2 keeps 'only'
  AS t(k, v, _landed_at)),
out AS (SELECT k, v FROM (SELECT k, v, ROW_NUMBER() OVER (PARTITION BY k ORDER BY _landed_at DESC) AS rn FROM src) WHERE rn = 1),
exp AS (SELECT * FROM VALUES ('K1', 'new'), ('K2', 'only') AS e(k, v))
SELECT COUNT(*) AS mismatches FROM out o FULL OUTER JOIN exp e ON o.k = e.k WHERE o.k IS NULL OR e.k IS NULL OR o.v <> e.v;
