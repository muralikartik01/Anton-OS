-- Replace placeholders:
--   ${CATALOG}, ${SCHEMA}, ${TABLE}
-- Fully qualified table:
--   ${CATALOG}.${SCHEMA}.${TABLE}

-- 1) Table schema
DESCRIBE TABLE ${CATALOG}.${SCHEMA}.${TABLE};

-- 2) Row count
SELECT COUNT(*) AS row_count
FROM ${CATALOG}.${SCHEMA}.${TABLE};

-- 3) Duplicate rows across all columns
SELECT
  COUNT(*) - COUNT(DISTINCT struct(*)) AS duplicate_row_count
FROM ${CATALOG}.${SCHEMA}.${TABLE};

-- 4) Null percentage per column (generate one SELECT per column and UNION ALL)
-- Template line per column:
-- SELECT 'column_name' AS column_name,
--        SUM(CASE WHEN column_name IS NULL THEN 1 ELSE 0 END) AS null_count,
--        ROUND(100.0 * SUM(CASE WHEN column_name IS NULL THEN 1 ELSE 0 END) / COUNT(*), 4) AS null_pct
-- FROM ${CATALOG}.${SCHEMA}.${TABLE}

-- 5) Distinct count per column (generate one SELECT per column and UNION ALL)
-- Template line per column:
-- SELECT 'column_name' AS column_name,
--        COUNT(DISTINCT column_name) AS distinct_count
-- FROM ${CATALOG}.${SCHEMA}.${TABLE}

-- 6) Numeric profile template (per numeric column)
-- SELECT
--   'column_name' AS column_name,
--   MIN(column_name) AS min_value,
--   MAX(column_name) AS max_value,
--   ROUND(AVG(column_name), 4) AS avg_value,
--   ROUND(STDDEV(column_name), 4) AS stddev_value,
--   PERCENTILE_APPROX(column_name, 0.50) AS p50,
--   PERCENTILE_APPROX(column_name, 0.90) AS p90,
--   PERCENTILE_APPROX(column_name, 0.95) AS p95,
--   PERCENTILE_APPROX(column_name, 0.99) AS p99
-- FROM ${CATALOG}.${SCHEMA}.${TABLE}
-- WHERE column_name IS NOT NULL

-- 7) String profile template (per string column)
-- SELECT
--   'column_name' AS column_name,
--   MIN(LENGTH(column_name)) AS min_length,
--   MAX(LENGTH(column_name)) AS max_length,
--   ROUND(AVG(LENGTH(column_name)), 4) AS avg_length
-- FROM ${CATALOG}.${SCHEMA}.${TABLE}
-- WHERE column_name IS NOT NULL

-- 8) Top values for string column (deterministic ordering)
-- SELECT
--   column_name AS value,
--   COUNT(*) AS value_count
-- FROM ${CATALOG}.${SCHEMA}.${TABLE}
-- WHERE column_name IS NOT NULL
-- GROUP BY column_name
-- ORDER BY value_count DESC, value ASC
-- LIMIT 10

-- 9) Temporal min/max for date or timestamp column
-- SELECT
--   MIN(CAST(column_name AS DATE)) AS min_date,
--   MAX(CAST(column_name AS DATE)) AS max_date,
--   DATEDIFF(MAX(CAST(column_name AS DATE)), MIN(CAST(column_name AS DATE))) AS coverage_days
-- FROM ${CATALOG}.${SCHEMA}.${TABLE}
-- WHERE column_name IS NOT NULL

-- 10) Last-30-day daily row counts
-- SELECT
--   CAST(column_name AS DATE) AS dt,
--   COUNT(*) AS row_count
-- FROM ${CATALOG}.${SCHEMA}.${TABLE}
-- WHERE CAST(column_name AS DATE) >= DATE_SUB(CURRENT_DATE(), 30)
-- GROUP BY CAST(column_name AS DATE)
-- ORDER BY dt ASC
