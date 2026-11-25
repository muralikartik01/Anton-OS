-- queries.sql — parameterized lookups for databricks-cluster-sizer (MCP-only).
--
-- Run EVERY query through whichever Databricks SQL MCP server is configured in
-- this workspace (`.../api/2.0/mcp/sql`), using its SQL execution tool (commonly
-- named like `execute_sql`). Do NOT use the Databricks CLI for anything. The MCP
-- server runs the statement on an authorized SQL warehouse on your behalf.
--
-- Substitute the named parameters (:run_id, :cluster_id, :start_ts, :end_ts)
-- into the statement text before sending, or pass them via the tool's parameter
-- map if your build supports bound parameters, e.g.:
--   execute_sql(sql_query="<one statement below, with values substituted>")
--
-- Requires Unity Catalog `system.compute` (always) and `system.lakeflow` (only
-- for [0], run resolution) enabled, with SELECT on the tables referenced below.
-- The cadence/cost/trend queries [4]-[9] additionally require SELECT on
-- `system.lakeflow.jobs`, `system.lakeflow.job_run_timeline`,
-- `system.billing.usage` and `system.billing.list_prices`.

-- ============================================================================
-- [0] RESOLVE A JOB RUN -> cluster_id + time window
-- Source: system.lakeflow.job_task_run_timeline. Replaces the old
-- `databricks jobs get-run` CLI call. A run can touch several compute ids, so
-- explode compute_ids and take the full span of the run as the window. Feed the
-- resulting cluster_id + start_ts/end_ts into [1], [2] and [3] below.
-- ============================================================================
WITH exploded AS (
  SELECT
    explode(compute_ids) AS cluster_id,
    period_start_time,
    period_end_time
  FROM system.lakeflow.job_task_run_timeline
  WHERE job_run_id = :run_id
)
SELECT
  cluster_id,
  min(period_start_time) AS start_ts,
  max(period_end_time)   AS end_ts
FROM exploded
GROUP BY cluster_id;

-- ============================================================================
-- [1] UTILIZATION PROFILE  (per role: driver vs worker)
-- Source: system.compute.node_timeline (minute granularity).
-- cpu_busy excludes idle + iowait so it reflects real compute pressure.
-- ============================================================================
WITH nt AS (
  SELECT
    driver,
    cpu_user_percent + cpu_system_percent AS cpu_busy,
    mem_used_percent,
    mem_swap_percent
  FROM system.compute.node_timeline
  WHERE cluster_id = :cluster_id
    AND start_time BETWEEN :start_ts AND :end_ts
)
SELECT
  driver,
  count(*)                                       AS sample_minutes,
  round(percentile(cpu_busy, 0.50), 1)           AS cpu_p50,
  round(percentile(cpu_busy, 0.95), 1)           AS cpu_p95,
  round(max(cpu_busy), 1)                        AS cpu_max,
  round(percentile(mem_used_percent, 0.95), 1)   AS mem_p95,
  round(max(mem_used_percent), 1)                AS mem_max,
  round(max(mem_swap_percent), 1)                AS swap_max
FROM nt
GROUP BY driver;

-- ============================================================================
-- [2] CURRENT CLUSTER CONFIG  (latest row; clusters is SCD2 history)
-- Source: system.compute.clusters.
-- ============================================================================
SELECT
  cluster_id,
  cluster_name,
  driver_node_type,
  worker_node_type,
  worker_count,
  min_autoscale_workers,
  max_autoscale_workers,
  auto_termination_minutes,
  cluster_source
FROM system.compute.clusters
WHERE cluster_id = :cluster_id
QUALIFY row_number() OVER (PARTITION BY cluster_id ORDER BY change_time DESC) = 1;

-- ============================================================================
-- [3] OBSERVED PEAK CONCURRENCY  (to detect autoscale-capped clusters)
-- Distinct non-driver instances seen in any single minute = peak worker count.
-- ============================================================================
SELECT
  max(active_workers) AS observed_peak_workers
FROM (
  SELECT start_time, count(DISTINCT instance_id) AS active_workers
  FROM system.compute.node_timeline
  WHERE cluster_id = :cluster_id
    AND start_time BETWEEN :start_ts AND :end_ts
    AND driver = false
  GROUP BY start_time
);

-- ============================================================================
-- CADENCE / CRITICALITY / TREND / COST QUERIES
-- ----------------------------------------------------------------------------
-- The queries below upgrade the skill from single-run sizing to cadence- and
-- criticality-aware, trend-based, multi-tier recommendations. They require
-- additional Unity Catalog system schemas with SELECT granted:
--   * system.lakeflow.jobs              (job identity, schedule, tags)
--   * system.lakeflow.job_run_timeline  (run-level cadence + outcomes)
--   * system.billing.usage              (actual DBU consumption per job/run)
--   * system.billing.list_prices        (DBU -> USD list price, SCD2)
-- All are point-in-time / SCD2 where noted; respect change_time when joining.
-- ============================================================================

-- ============================================================================
-- [4] JOB IDENTITY + SCHEDULE + TAGS  (criticality + declared cadence)
-- Source: system.lakeflow.jobs (SCD2 — take the latest row per job_id).
-- `trigger_type`/`schedule`/`tags` may be NULL on older rows or for jobs that
-- were never edited after these columns shipped; in that case rely on the
-- empirical cadence in [5]. `tags` is a MAP<string,string>; read keys like
-- criticality / tier / sla / env to derive criticality (else fall back to
-- cadence). Parameter: :job_id.
-- ============================================================================
SELECT
  job_id,
  name                          AS job_name,
  run_as,
  schedule.quartz_cron_expression AS cron_expression,
  schedule.pause_status         AS schedule_pause_status,
  trigger_type,                              -- e.g. PERIODIC / CONTINUOUS / FILE_ARRIVAL
  tags,                                      -- MAP<string,string> (criticality/tier/sla/env)
  tags['criticality']           AS tag_criticality,
  tags['tier']                  AS tag_tier,
  tags['sla']                   AS tag_sla,
  tags['env']                   AS tag_env
FROM system.lakeflow.jobs
WHERE job_id = :job_id
QUALIFY row_number() OVER (PARTITION BY job_id ORDER BY change_time DESC) = 1;

-- ============================================================================
-- [5] EMPIRICAL CADENCE  (robust fallback when [4] schedule is NULL)
-- Source: system.lakeflow.job_run_timeline over a 90-day window. Counts only
-- terminal runs (result_state IS NOT NULL) and measures the typical gap between
-- consecutive run starts. runs_per_week + median_gap_hours feed the cadence
-- bucket: hourly_or_more (>=35/week, ~5+/day) / daily (>=5/week) /
-- weekly_or_less / irregular.
-- Parameter: :job_id.
-- ============================================================================
WITH terminal AS (
  SELECT period_start_time AS run_start
  FROM system.lakeflow.job_run_timeline
  WHERE job_id = :job_id
    AND period_start_time >= current_timestamp() - INTERVAL 90 DAYS
    AND result_state IS NOT NULL
),
gaps AS (
  SELECT
    run_start,
    (unix_timestamp(run_start)
       - unix_timestamp(lag(run_start) OVER (ORDER BY run_start))) / 3600.0 AS gap_hours
  FROM terminal
)
SELECT
  count(*)                                              AS runs_90d,
  round(count(*) / 12.857, 2)                           AS runs_per_week,   -- 90d ≈ 12.857 weeks
  round(percentile(gap_hours, 0.50), 2)                 AS median_gap_hours,
  round(stddev(gap_hours), 2)                           AS gap_stddev_hours,
  min(run_start)                                        AS first_run,
  max(run_start)                                        AS last_run
FROM gaps;

-- ============================================================================
-- [6] LAST-N RUNS ENUMERATION  (trend window; default N=20)
-- Source: system.lakeflow.job_run_timeline. One terminal row per job run with
-- duration + outcome + the compute id(s) used. Feed each cluster_id/window into
-- [1]-[3] for per-run utilization, and the run_id set into [7]/[8] for cost.
-- Parameters: :job_id, :n_runs.
-- ============================================================================
SELECT
  run_id,
  job_run_id,
  period_start_time                                              AS run_start,
  period_end_time                                               AS run_end,
  (unix_timestamp(period_end_time)
     - unix_timestamp(period_start_time))                        AS duration_seconds,
  result_state,
  termination_code,
  compute_ids
FROM system.lakeflow.job_run_timeline
WHERE job_id = :job_id
  AND result_state IS NOT NULL
QUALIFY row_number() OVER (PARTITION BY job_id ORDER BY period_start_time DESC) <= :n_runs
ORDER BY run_start DESC;

-- ============================================================================
-- [7] PER-RUN ACTUAL COST  (DBU -> USD, the cost anchor for projections)
-- Source: system.billing.usage JOIN system.billing.list_prices. This is the
-- ground-truth $ for a job run; alternatives are projected by scaling this
-- baseline. Notes:
--   * usage_metadata.job_id is NULL for ALL-PURPOSE compute (cluster_source
--     UI/API) — such jobs are NOT attributable here; fall back to relative DBU
--     and surface a caveat.
--   * record_type may be RETRACTION / RESTATEMENT — net them out (sum signed).
--   * list_prices is SCD2; match the price effective at usage_start_time.
--   * billing data can lag several hours; very recent runs may be incomplete.
-- Parameters: :job_id, :start_ts, :end_ts.
-- ============================================================================
WITH u AS (
  SELECT
    usage_metadata.job_id        AS job_id,
    usage_metadata.job_run_id    AS job_run_id,
    sku_name,
    cloud,
    usage_start_time,
    usage_unit,
    -- net out corrections: RETRACTION rows carry negative offsets
    CASE WHEN record_type = 'RETRACTION' THEN -usage_quantity ELSE usage_quantity END AS dbus
  FROM system.billing.usage
  WHERE usage_metadata.job_id = :job_id
    AND usage_start_time BETWEEN :start_ts AND :end_ts
),
priced AS (
  SELECT
    u.job_run_id,
    u.dbus,
    u.dbus * lp.pricing.default AS usd
  FROM u
  JOIN system.billing.list_prices lp
    ON lp.sku_name = u.sku_name
   AND lp.currency_code = 'USD'
   AND u.usage_start_time >= lp.price_start_time
   AND u.usage_start_time <  coalesce(lp.price_end_time, current_timestamp())
)
SELECT
  job_run_id,
  round(sum(dbus), 4) AS dbus,
  round(sum(usd), 4)  AS cost_usd
FROM priced
GROUP BY job_run_id;

-- ============================================================================
-- [8] COST + RUNTIME TREND  (last-N runs aggregated -> drift, variance, SLA)
-- Combines run durations ([6]) with per-run cost ([7]) so projections rest on
-- representative percentiles rather than a single run. success_rate and the
-- runtime/cost percentiles feed the trend summary and tier defaults.
-- Parameters: :job_id, :n_runs.
-- ============================================================================
WITH runs AS (
  SELECT
    job_run_id,
    period_start_time AS run_start,
    (unix_timestamp(period_end_time) - unix_timestamp(period_start_time)) AS duration_seconds,
    result_state
  FROM system.lakeflow.job_run_timeline
  WHERE job_id = :job_id
    AND result_state IS NOT NULL
  QUALIFY row_number() OVER (PARTITION BY job_id ORDER BY period_start_time DESC) <= :n_runs
),
cost AS (
  SELECT
    usage_metadata.job_run_id AS job_run_id,
    sum(CASE WHEN record_type = 'RETRACTION' THEN -usage_quantity ELSE usage_quantity END
        * lp.pricing.default) AS cost_usd
  FROM system.billing.usage bu
  JOIN system.billing.list_prices lp
    ON lp.sku_name = bu.sku_name
   AND lp.currency_code = 'USD'
   AND bu.usage_start_time >= lp.price_start_time
   AND bu.usage_start_time <  coalesce(lp.price_end_time, current_timestamp())
  WHERE usage_metadata.job_id = :job_id
  GROUP BY usage_metadata.job_run_id
)
SELECT
  count(*)                                                          AS n_runs,
  round(avg(CASE WHEN r.result_state = 'SUCCEEDED' THEN 1 ELSE 0 END), 3) AS success_rate,
  round(percentile(r.duration_seconds, 0.50), 1)                   AS runtime_seconds_p50,
  round(percentile(r.duration_seconds, 0.90), 1)                   AS runtime_seconds_p90,
  round(stddev(r.duration_seconds), 1)                             AS runtime_seconds_stddev,
  round(percentile(c.cost_usd, 0.50), 4)                           AS cost_usd_p50,
  round(percentile(c.cost_usd, 0.90), 4)                           AS cost_usd_p90,
  -- simple drift signal: correlation of duration vs recency rank (+ = slowing)
  round(corr(r.duration_seconds,
             unix_timestamp(r.run_start)), 3)                      AS runtime_recency_corr
FROM runs r
LEFT JOIN cost c USING (job_run_id);

-- ============================================================================
-- [9] COMPUTE ATTRIBUTION CHECK  (all-purpose vs jobs vs serverless)
-- Decides whether cost can be attributed and whether node_timeline exists.
--   * cluster_source JOB           -> jobs compute, fully attributable.
--   * cluster_source UI / API      -> all-purpose; billing.job_id is NULL,
--                                     project on relative DBU only (caveat).
--   * billing_origin_product like
--     'JOBS%' with NULL cluster    -> serverless; no node_timeline, so utilization
--                                     profile is unavailable (degrade gracefully).
-- Parameter: :cluster_id.
-- ============================================================================
SELECT
  cluster_id,
  cluster_source,
  CASE
    WHEN cluster_source = 'JOB'            THEN 'jobs_attributable'
    WHEN cluster_source IN ('UI','API')    THEN 'all_purpose_not_attributable'
    ELSE 'unknown'
  END AS attribution
FROM system.compute.clusters
WHERE cluster_id = :cluster_id
QUALIFY row_number() OVER (PARTITION BY cluster_id ORDER BY change_time DESC) = 1;
