-- queries.sql — parameterized lookups for cluster-sizing-forecast (MCP-only / read-only).
--
-- Run EVERY query through whichever Databricks SQL MCP server is configured in
-- this workspace (`.../api/2.0/mcp/sql`). If more than one is configured (e.g.
-- one per environment), pick the one whose workspace owns the source tables.
-- Do NOT use the Databricks CLI. These statements are read-only and are
-- intended for an authorized SQL warehouse.
--
-- Substitute named parameters (:source_fqn, :key1, :catalog, :schema, :table,
-- :volume_class, :load_type, :market, :analog_job_id, :start_ts, :end_ts,
-- :cloud, :currency_code, :days_back) before sending, or pass them via the MCP
-- tool's parameter map if bound parameters are supported. Non-instant MCP
-- executions may return statement_id + PENDING; poll that statement_id until it
-- reaches a terminal state before using the result.
--
-- Required system schemas for calibration queries: system.lakeflow,
-- system.billing and system.compute. If [3]-[6] are unavailable, keep the
-- forecast bottom-up only and lower confidence; never guess silently.

-- ============================================================================
-- [0] SOURCE METADATA — size, files, partition columns
-- Purpose: run once per source FQN. Feeds
-- inputs.sources[].size_bytes, inputs.sources[].num_files,
-- inputs.sources[].partition_columns, and the abstain check for missing size.
-- Parameters: :source_fqn (for example 'catalog.schema.table').
-- ============================================================================
DESCRIBE DETAIL IDENTIFIER(:source_fqn);

-- ============================================================================
-- [1] SOURCE ROW COUNT — secondary volume cross-check
-- Purpose: run once per source FQN. Feeds inputs.sources[].row_count. Prefer
-- metadata if already available in your workspace; otherwise this exact COUNT is
-- the portable read-only fallback and may be expensive on very large sources.
-- Parameters: :source_fqn.
-- ============================================================================
SELECT
  :source_fqn AS source_fqn,
  count(*)    AS row_count
FROM IDENTIFIER(:source_fqn);

-- ============================================================================
-- [2] SKEW / KEY-CARDINALITY PROBE — multiple candidate keys in one scan
-- Purpose: probe business, join, partition and merge keys with
-- APPROX_COUNT_DISTINCT. Feeds inputs.skew.max_key_cardinality and flags skew
-- when cardinality is < 10x the forecast shuffle partition count or hot keys /
-- NULLs are known. Supply up to three key column names; repeat a key when fewer
-- are needed, or clone this pattern for more keys.
-- Parameters: :source_fqn, :key1, :key2, :key3.
-- ============================================================================
SELECT
  :source_fqn AS source_fqn,
  stack(
    3,
    :key1, approx_count_distinct(IDENTIFIER(:key1)), sum(CASE WHEN IDENTIFIER(:key1) IS NULL THEN 1 ELSE 0 END),
    :key2, approx_count_distinct(IDENTIFIER(:key2)), sum(CASE WHEN IDENTIFIER(:key2) IS NULL THEN 1 ELSE 0 END),
    :key3, approx_count_distinct(IDENTIFIER(:key3)), sum(CASE WHEN IDENTIFIER(:key3) IS NULL THEN 1 ELSE 0 END)
  ) AS (candidate_key, approx_distinct_values, null_rows)
FROM IDENTIFIER(:source_fqn);

-- ============================================================================
-- [3] ANALOG JOBS — nearest existing SRD/Gold job by volume + load type
-- Purpose: identify candidate analogs for the empirical bound. Feeds
-- inputs.analog.job_id candidates, plus analog metadata (volume_class,
-- load_type, cron, tags). Keep the nearest same load type / volume class first.
-- Parameters: :volume_class (small|medium|large|xl or local convention),
-- :load_type (append|upsert|scd2|delete_insert|overwrite), :market (optional
-- SRD market token; use '%' to match any), :days_back.
-- ============================================================================
WITH latest_jobs AS (
  SELECT
    job_id,
    name AS job_name,
    schedule.quartz_cron_expression AS quartz_cron_expression,
    tags,
    lower(coalesce(tags['domain'], tags['data_domain'], '')) AS domain_tag,
    lower(coalesce(tags['layer'], tags['medallion'], tags['tier'], '')) AS layer_tag,
    lower(coalesce(tags['volume_class'], tags['size_class'], '')) AS volume_class_tag,
    lower(coalesce(tags['load_type'], tags['load_strategy'], '')) AS load_type_tag,
    lower(coalesce(tags['market'], tags['country'], '')) AS market_tag,
    change_time
  FROM system.lakeflow.jobs
  WHERE coalesce(delete_time, timestamp'9999-12-31 00:00:00') > current_timestamp()
  QUALIFY row_number() OVER (PARTITION BY job_id ORDER BY change_time DESC) = 1
), recent_runs AS (
  SELECT
    job_id,
    count(DISTINCT job_run_id) AS runs_in_window,
    max(period_start_time)     AS last_run_start
  FROM system.lakeflow.job_run_timeline
  WHERE period_start_time >= current_timestamp() - make_interval(0, 0, 0, :days_back)
    AND result_state IS NOT NULL
  GROUP BY job_id
)
SELECT
  j.job_id,
  j.job_name,
  j.quartz_cron_expression,
  j.tags,
  j.volume_class_tag,
  j.load_type_tag,
  j.market_tag,
  r.runs_in_window,
  r.last_run_start,
  CASE WHEN j.load_type_tag = lower(:load_type) THEN 0 ELSE 10 END
    + CASE WHEN j.volume_class_tag = lower(:volume_class) THEN 0 ELSE 5 END
    + CASE WHEN j.market_tag LIKE lower(:market) THEN 0 ELSE 1 END AS analog_distance
FROM latest_jobs j
LEFT JOIN recent_runs r USING (job_id)
WHERE (j.domain_tag LIKE '%srd%' OR lower(j.job_name) LIKE '%srd%')
  AND (j.layer_tag LIKE '%gold%' OR lower(j.job_name) LIKE '%gold%')
  AND coalesce(r.runs_in_window, 0) > 0
ORDER BY analog_distance, r.last_run_start DESC
LIMIT 20;

-- ============================================================================
-- [4] ANALOG ACTUALS — actual DBU/hr and runtime for the selected analog
-- Purpose: join billing usage to Lakeflow run timeline and compute real runtime
-- + net DBU/hr. Feeds inputs.analog.dbus_per_hour, runtime_hours and analog
-- envelope. RETRACTION rows are signed negative so corrections net out.
-- Parameters: :analog_job_id, :start_ts, :end_ts.
-- ============================================================================
WITH runs AS (
  SELECT
    cast(job_id AS string)       AS job_id,
    cast(job_run_id AS string)   AS job_run_id,
    min(period_start_time)       AS run_start,
    max(period_end_time)         AS run_end,
    (unix_timestamp(max(period_end_time)) - unix_timestamp(min(period_start_time))) / 3600.0 AS runtime_hours,
    max(result_state)            AS result_state
  FROM system.lakeflow.job_run_timeline
  WHERE cast(job_id AS string) = cast(:analog_job_id AS string)
    AND period_start_time >= :start_ts
    AND period_start_time <  :end_ts
    AND result_state IS NOT NULL
  GROUP BY cast(job_id AS string), cast(job_run_id AS string)
), usage_net AS (
  SELECT
    cast(usage_metadata.job_id AS string)     AS job_id,
    cast(usage_metadata.job_run_id AS string) AS job_run_id,
    sum(CASE WHEN record_type = 'RETRACTION' THEN -usage_quantity ELSE usage_quantity END) AS net_dbus
  FROM system.billing.usage
  WHERE cast(usage_metadata.job_id AS string) = cast(:analog_job_id AS string)
    AND usage_start_time >= :start_ts
    AND usage_start_time <  :end_ts
    AND usage_unit = 'DBU'
  GROUP BY cast(usage_metadata.job_id AS string), cast(usage_metadata.job_run_id AS string)
), per_run AS (
  SELECT
    r.job_id,
    r.job_run_id,
    r.run_start,
    r.run_end,
    r.runtime_hours,
    coalesce(u.net_dbus, 0.0) AS net_dbus,
    coalesce(u.net_dbus, 0.0) / nullif(r.runtime_hours, 0.0) AS dbus_per_hour,
    r.result_state
  FROM runs r
  LEFT JOIN usage_net u
    ON r.job_id = u.job_id AND r.job_run_id = u.job_run_id
)
SELECT
  job_id,
  count(*) AS runs,
  round(percentile(runtime_hours, 0.50), 4) AS runtime_hours_p50,
  round(percentile(runtime_hours, 0.90), 4) AS runtime_hours_p90,
  round(percentile(dbus_per_hour, 0.50), 4) AS dbus_per_hour_p50,
  round(percentile(dbus_per_hour, 0.90), 4) AS dbus_per_hour_p90,
  round(sum(net_dbus), 4) AS total_net_dbus,
  round(avg(CASE WHEN result_state = 'SUCCEEDED' THEN 1 ELSE 0 END), 3) AS success_rate
FROM per_run
GROUP BY job_id;

-- ============================================================================
-- [5] CURRENT DBU PRICING — Jobs, All-Purpose and Photon rates
-- Purpose: read current SCD2 price rows. Feeds inputs.pricing.jobs_dbu_usd,
-- inputs.pricing.all_purpose_dbu_usd and Photon price/uplift assumptions. Current
-- row = price_start_time <= now and (price_end_time IS NULL or > now).
-- Parameters: :cloud (AZURE|AWS|GCP as stored), :currency_code (usually 'USD').
-- ============================================================================
WITH current_prices AS (
  SELECT
    cloud,
    sku_name,
    usage_unit,
    currency_code,
    price_start_time,
    price_end_time,
    pricing.default AS dbu_price
  FROM system.billing.list_prices
  WHERE upper(cloud) = upper(:cloud)
    AND currency_code = :currency_code
    AND usage_unit = 'DBU'
    AND price_start_time <= current_timestamp()
    AND (price_end_time IS NULL OR price_end_time > current_timestamp())
)
SELECT
  cloud,
  sku_name,
  CASE
    WHEN upper(sku_name) LIKE '%JOBS%PHOTON%' OR upper(sku_name) LIKE '%PHOTON%JOBS%' THEN 'jobs_photon'
    WHEN upper(sku_name) LIKE '%JOBS%' THEN 'jobs_compute'
    WHEN upper(sku_name) LIKE '%ALL_PURPOSE%PHOTON%' OR upper(sku_name) LIKE '%PHOTON%ALL_PURPOSE%' THEN 'all_purpose_photon'
    WHEN upper(sku_name) LIKE '%ALL_PURPOSE%' THEN 'all_purpose_compute'
    ELSE 'other_dbu'
  END AS price_bucket,
  dbu_price,
  price_start_time,
  price_end_time
FROM current_prices
WHERE upper(sku_name) LIKE '%JOBS%'
   OR upper(sku_name) LIKE '%ALL_PURPOSE%'
   OR upper(sku_name) LIKE '%PHOTON%'
ORDER BY price_bucket, sku_name;

-- ============================================================================
-- [6] FLEET NORMS — SRD job-cluster node types and autoscale patterns
-- Purpose: keep recommendations inside the supported SRD Azure fleet. Feeds fleet
-- node family norms, common driver/worker node types, fixed vs autoscale defaults,
-- and min/max worker ranges.
-- Parameters: :days_back, :market (optional pattern such as '%' or '%mx%').
-- ============================================================================
WITH current_clusters AS (
  SELECT
    cluster_id,
    cluster_name,
    cluster_source,
    driver_node_type,
    worker_node_type,
    worker_count,
    min_autoscale_workers,
    max_autoscale_workers,
    tags,
    change_time
  FROM system.compute.clusters
  WHERE cluster_source = 'JOB'
    AND coalesce(delete_time, timestamp'9999-12-31 00:00:00') > current_timestamp()
  QUALIFY row_number() OVER (PARTITION BY cluster_id ORDER BY change_time DESC) = 1
), recent_job_compute AS (
  SELECT DISTINCT explode(compute_ids) AS cluster_id
  FROM system.lakeflow.job_run_timeline
  WHERE period_start_time >= current_timestamp() - make_interval(0, 0, 0, :days_back)
)
SELECT
  c.worker_node_type,
  c.driver_node_type,
  CASE
    WHEN c.min_autoscale_workers IS NOT NULL OR c.max_autoscale_workers IS NOT NULL THEN 'autoscale'
    ELSE 'fixed'
  END AS sizing_mode,
  c.worker_count,
  c.min_autoscale_workers,
  c.max_autoscale_workers,
  count(*) AS cluster_count,
  round(percentile(coalesce(c.worker_count, c.min_autoscale_workers), 0.50), 1) AS workers_or_min_p50,
  round(percentile(coalesce(c.worker_count, c.max_autoscale_workers), 0.90), 1) AS workers_or_max_p90
FROM current_clusters c
JOIN recent_job_compute r USING (cluster_id)
WHERE (lower(coalesce(c.tags['domain'], c.tags['data_domain'], c.cluster_name, '')) LIKE '%srd%'
       OR lower(c.cluster_name) LIKE '%srd%')
  AND lower(coalesce(c.tags['market'], c.tags['country'], '')) LIKE lower(:market)
GROUP BY
  c.worker_node_type,
  c.driver_node_type,
  CASE WHEN c.min_autoscale_workers IS NOT NULL OR c.max_autoscale_workers IS NOT NULL THEN 'autoscale' ELSE 'fixed' END,
  c.worker_count,
  c.min_autoscale_workers,
  c.max_autoscale_workers
ORDER BY cluster_count DESC, worker_node_type, sizing_mode;
