---
name: cluster-sizing-forecast
description: >-
  Forecast an ideal Databricks job cluster for a Gold table that has NOT been built
  yet — before any run history exists — by inferring technical complexity (broadcast
  vs shuffle joins, MERGE/Upsert/SCD2 strategy, aggregations, window functions, key
  skew) from the DRD/DAT and reading live source-table metadata (size, file count,
  partition columns, key cardinality) through the Databricks SQL MCP server. It applies
  cited Apache Spark + Databricks sizing heuristics to recommend a node type, worker
  count / autoscale bounds, Photon and spot settings, AND projects a per-run + monthly
  cost using fleet Jobs-Compute DBU rates bounded by the nearest analog job's measured
  actuals. It is the a-priori FORECAST twin of the post-deployment, telemetry-measured
  databricks-cluster-sizer: this one runs at design time so the generated notebook/job
  ships on a sensible cluster instead of a blind guess. It deliberately produces a
  conservative over-estimate and ABSTAINS rather than guessing when source tables are
  unreadable or sizes are missing (a missing analog only widens the cost band and lowers
  confidence — it does not abstain). Use this whenever someone is
  about to onboard / design a new Gold table or pipeline and needs to pick a cluster and
  estimate cost before it runs, asks "what cluster should this new job use", "how big a
  cluster do I need for this MERGE", "estimate the cost of this pipeline before we build
  it", or mentions cluster sizing during design / pre-deployment — even without saying
  the word "skill".
compatibility: Requires a Databricks SQL MCP server (.../api/2.0/mcp/sql) for all source-metadata, analog and pricing reads, plus Python 3.9+ for the offline forecaster/scorer. No Databricks CLI is used. Read-only; emits an Apply Block that a human applies via the Databricks UI or REST API.

---

# Databricks Cluster Sizing Forecaster (pre-deployment)

Recommend a Databricks **job cluster** and a **cost projection** for a Gold table
**before it is built** — at design time, when there is no `run_id`, no telemetry and
no billing history to measure. Instead of measured utilization, this skill reasons from
**static signals**: the load strategy and joins declared in the DRD/DAT, and the **live
metadata of the source tables** (byte size, file count, partition columns, candidate-key
cardinality) read read-only through the Databricks SQL MCP server. It applies transparent,
**cited** Apache Spark / Databricks sizing rules to size the cluster, then projects
per-run and monthly cost from fleet **Jobs-Compute DBU rates**, **bounded by the nearest
analog job's actuals**. The output feeds the design doc and the generated workflow JSON so
the **notebook runs on the recommended cluster** from its first execution.

This is **Phase 1 (Forecast)** of Databricks' documented **Forecast → Measure → Refine**
sizing loop. The companion `databricks-cluster-sizer` skill is **Phase 2 (Measure) +
Phase 3 (Right-size)**: it validates and tightens this forecast once real runs exist. The
two are deliberate twins — same node catalog, same cost model, same abstain discipline —
differing only in their signal (static estimate here vs. measured telemetry there).

## When to use

Reach for this skill at **design / onboarding time** for a new Gold market+table, whenever
someone must pick a cluster and estimate cost **before the pipeline has ever run**: sizing
a heavy Delta `MERGE`/Upsert, deciding memory- vs compute- vs general-purpose nodes for a
multi-join build, choosing autoscale bounds and Photon, or giving Finance a pre-build cost
range. It is **not** for right-sizing a deployed job from telemetry — that is
`databricks-cluster-sizer` (use it after the job has run). When in doubt: **no run history
yet → forecast (this skill); run history exists → measure (the sizer).**

## Prerequisites

| Requirement | Needed for | Notes |
| --- | --- | --- |
| **Databricks SQL MCP server** (`https://<host>/api/2.0/mcp/sql`) | source metadata, analog calibration, pricing | All Databricks data is read by running SQL through whichever Databricks SQL MCP tool is configured in this workspace. If more than one is configured (e.g. one per environment), pick the one whose workspace owns the **source** tables. **No Databricks CLI is used.** |
| **Python 3.9+** | always | Runs `scripts/forecast_size.py` (the offline forecaster) and the eval suite. Standard library only; performs **no** Databricks access. |
| **SELECT on the source tables** (+ `DESCRIBE DETAIL`) | volume + layout signal | Supplies `sizeInBytes`, `numFiles`, `partitionColumns`; `APPROX_COUNT_DISTINCT` on candidate keys gives the skew signal. |
| **UC `system.lakeflow`** + `system.billing` (`usage`, `list_prices`) | analog calibration + DBU pricing | Finds the nearest existing SRD/Gold job by volume + load-type and pulls its **real** DBU/hr + runtime to bound the bottom-up estimate, and the current Jobs/All-Purpose/Photon DBU price. Optional: without them the forecast degrades to a **bottom-up-only** range with a wider band + lower confidence (never a silent wrong number). |
| **UC `system.compute.clusters`** | fleet node norms | Confirms which node families the SRD job fleet actually uses (so the rec stays inside the supported catalog). |
| **A SQL warehouse** the MCP server can use, caller has **CAN USE** | always | The MCP server runs the queries on an authorized warehouse on your behalf. |

This skill **requires** the Databricks SQL MCP server for its source/analog/pricing reads
— there is no CLI fallback. If the **source tables are unreadable or report no size**, the
skill **abstains** instead of guessing. The `lakeflow`/`billing` reads are *calibration*:
missing them widens the cost band and lowers confidence, clearly caveated.

## Workflow

All Databricks access is done by **you, the agent**, by running SQL through the Databricks
SQL MCP server. `scripts/forecast_size.py` never touches Databricks — it only scores the
static signals you collect. The queries below live in `references/queries.sql`; run each
with the MCP server's SQL tool (commonly `execute_sql`).

1. **Read the design intent (manifest-backed).** From `specs/{use_case}/manifest.md`
   resolve the DRD/DAT CSVs, the **source table FQNs**, target market, and the **planned
   schedule + criticality**. From the DRD/DAT extract: load strategy (Upsert / Append /
   SCD2 / Delete-Insert / Overwrite), declared joins/lookups, business / merge keys,
   aggregations and window functions. **Do not scan the codebase** — use only manifest paths.
2. **Pick the MCP server & read source metadata.** If this workspace has more than
   one Databricks SQL MCP tool configured, pick the one matching the workspace
   owning the **sources**; otherwise use the single tool available. Run query **[0]**
   (`DESCRIBE DETAIL <src>`) for `sizeInBytes`, `numFiles`, `partitionColumns`; **[1]** for
   row counts. Run **[2]** (`APPROX_COUNT_DISTINCT` on candidate join/partition keys) for
   the **skew** signal. **Abstain** if no source size is obtainable.
3. **Calibrate against analogs (optional but preferred).** Run **[3]** to find the nearest
   existing SRD/Gold job by volume class + load type (`system.lakeflow.jobs`), **[4]** for
   its **actual DBU/hr + runtime** (`system.billing.usage` ⋈ `job_run_timeline`), **[5]**
   for the current Jobs-Compute / All-Purpose / Photon **DBU price** (`list_prices`, SCD2),
   and **[6]** for fleet node-type norms (`system.compute.clusters`).
3a. **Prompt for `retention_days` if not provided (MANDATORY before forecasting).**
   Storage cost is a function of how long snapshots are kept. If the user has not explicitly
   stated a retention period, **stop and ask before proceeding**:

   > *"How many days should Gold snapshots be retained for this pipeline?*
   > *Common values: 90 days (3 months), 365 days (1 year), 730 days (2 years).*
   > *This is required to calculate storage cost — I cannot estimate it without this."*

   **Do NOT default silently.** Do NOT assume 90 days or any other value. Only proceed
   once the user has confirmed a number. Add the confirmed value to `schedule.retention_days`
   in the payload. If the pipeline does NOT create historical snapshots (upsert/overwrite
   to a current-state table), set `retention_days` to `0` and skip storage cost.
4. **Forecast.** Assemble one JSON payload and run the offline forecaster:

   ```bash
   # payload.json = {
   #   "inputs": {
   #     "use_case": "deliveryline_SA",
   #     "load_strategy": "upsert",              # upsert|append|scd2|delete_insert|overwrite
   #     "sources": [ {"fqn":"...", "size_bytes":..., "num_files":..., "row_count":...,
   #                   "partition_columns":[...], "role":"fact|dim|ref"} ],
   #     "joins":  [ {"type":"inner|left|full|cross", "right_role":"dim|fact",
   #                  "right_size_bytes":..., "broadcastable":true} ],
   #     "merge":  {"keys":[...], "partition_pruned":true, "matched_target_bytes":...},
   #     "aggregations": [ {"kind":"group_by|window|count_distinct",
   #                        "low_cardinality":true, "unbounded_frame":false} ],
   #     "skew":   {"max_key_cardinality":..., "hot_keys":false},
   #     "schedule": {"cadence":"daily","runs_per_month":30,"criticality":"high",
   #                  "retention_days":90},   # REQUIRED — prompt user if not provided
   #     "analog":  {"job_id":"...","dbus_per_hour":...,"runtime_hours":...,"size_bytes":...},
   #     "pricing": {"jobs_dbu_usd":0.30,"all_purpose_dbu_usd":0.55,"photon_dbu_mult":2.0}
   #   } }
   python scripts/forecast_size.py --from-json payload.json          # Markdown report
   python scripts/forecast_size.py --from-json payload.json --json   # machine output
   ```

   Every nested block under `inputs` except `sources` is **optional**. With only `sources`
   + `load_strategy` you get a bottom-up forecast (defaulted to a conservative posture); add
   `joins`/`merge`/`aggregations`/`skew` to sharpen complexity, `schedule`/`analog`/`pricing`
   to unlock the calibrated cost projection. The payload shape matches `evals/fixtures/`.
5. **Read the options & emit artifacts.** The report shows the inferred **workload class**,
   the **volume + complexity evidence**, a three-tier **Options** table (Lean / Recommended /
   Conservative), the **cost projection** (low / expected / high per run + monthly, with the
   analog used and a confidence band), **assumptions**, **citations**, and an **Apply Block**
   (the `job_cluster` / `new_cluster` JSON). Write `specs/{use_case}/cluster-sizing-forecast.md`
   (human report) and `specs/{use_case}/cluster-sizing-forecast.json` (machine output for
   sttm-author + code-generator). Mutations remain **human-gated** — the Apply Block is a
   proposal, never auto-applied.

## How the forecast is made

See `README.md` for the full reasoning model with formulas + cited sources. In brief:

**1. Infer the workload class (deterministic, from declared SQL + source sizes).**

| Signal | Inference | Drives |
| --- | --- | --- |
| Dim side `< 10 MB` | Broadcast hash join (free, no shuffle) | no shuffle add |
| Dim side `10 MB – 2 GB` | Broadcast-hint candidate | small shuffle |
| Both sides `> 2 GB` | Sort-merge join → shuffle | `shuffle_GB += Σ inputs ×3` |
| `MERGE`/Upsert/SCD2/Delete-Insert | Most expensive: `source_GB×3 + matched_target_GB×3`; partition-pruned condition shrinks `matched_target`; full-target scan assumed if no partition key in the condition | large shuffle + memory |
| Join/partition key cardinality `< 10×` shuffle partitions, or known hot keys/NULLs | **Skew risk** | +20–30% memory hedge |
| Low-cardinality `GROUP BY`/`PARTITION BY` or unbounded window frame | | +50% executor memory; `COUNT DISTINCT` = 2 shuffles |

**2. Size from volume (a-priori heuristic).**
```
read_partitions    = ceil(total_source_GB * 1024 / 128)              # 128 MB / input partition
shuffle_GB         = Σ(join/merge/agg shuffle from step 1)           # ×3 Parquet decompression
shuffle_partitions = ceil(shuffle_GB * 1024 / 128)                  # 64–128 MB / shuffle partition
min_cores          = max(read_partitions, shuffle_partitions) / 2.5  # 2–3 tasks / core
total_memory_GB    = min_cores * mem_per_core (4 base; 6–8 shuffle-heavy) + skew/window hedges
# fit (min_cores, total_memory_GB) into the cheapest node family from references/node_catalog.csv
```

**3. Pick node family + knobs (grounded to the real Azure SRD fleet).** Shuffle/MERGE/join-
heavy or spill-prone → **memory-optimized (E-series)**, fewer larger nodes over many small;
CPU-bound/streaming/maintenance → **compute-optimized (F-series)**; `< 1 GB` & no distributed
ops → **single-node**. **Photon** on for SQL/DataFrame-heavy joins/aggregations/large scans
(2–5× faster); off for trivial ETL. **Autoscale** when runtime is variable and `> ~30 min`;
fixed (or pool) when SLA-critical/short — never set `spark.dynamicAllocation.*` alongside
Databricks autoscale. **Spot** workers by criticality (low → yes; medium → spot + on-demand
fallback; high / SLA < 2 h → on-demand); **driver always on-demand**.

**4. Project cost (hybrid: bottom-up bounded by analog).**
```
runtime_h  = est_input_GB / throughput_GB_per_hr_per_100cores × (100/cores) ÷ photon_mult
per_run_$  = (workers×worker_DBU + driver_DBU) × runtime_h × jobs_dbu_price          # Databricks DBU
           + (workers×worker_VM  + driver_VM ) × runtime_h                            # cloud VM (spot on workers)
monthly_$  = per_run_$ × runs_per_month(from planned schedule)
```
Throughput priors (GB/hr per 100 cores): simple ETL 100–500 · SMJ 30–100 · MERGE-no-prune
10–50 · MERGE-prune 50–200 · window 20–80; Photon 2–5×. Then **clamp the bottom-up estimate
to the nearest analog job's measured DBU/hr + runtime envelope** and report **low / expected /
high** with a **confidence band** and the analog id.

**5. Guardrails & abstain.** Forecast is a deliberate **conservative over-estimate** (AQE
self-corrects partition counts/joins at runtime but cannot shrink the cluster mid-run, so
over-provisioning is the insurance). Never emit `spark.executor.memory` /
`spark.dynamicAllocation.*` (Databricks warns these override built-in optimization). If the
source tables are unreadable / sizes missing → `"abstained": true` with reasons (mirrors the
sizer's "< 10 sample-minutes → abstain"). If no analog is found → bottom-up-only with a wider
band + lower confidence. The first 2–3 runs should use a **fixed** cluster; then
`cluster-optimizer` (Phase 2/3) refines it from real telemetry.

## Output contract (authoritative — workers MUST conform)

`scripts/forecast_size.py` exposes a **pure** brain plus a `--from-json` entrypoint, mirroring
`databricks-cluster-sizer/scripts/size_cluster.py`:

- `load_catalog(path) -> list[dict]` — read `references/node_catalog.csv`
  (`node_type,family,vcpu,ram_gb,rel_dbu,cloud`).
- `node_by_type(catalog, node_type) -> dict | None`.
- `forecast(inputs: dict, catalog: list[dict]) -> dict` — **pure**, deterministic, no I/O.
- `main(argv) -> int` — supports `--from-json <path|->` and `--json`; Markdown by default.

`forecast(...)` returns (and `cluster-sizing-forecast.json` serializes) **exactly** this shape:
```json
{
  "abstained": false,
  "abstain_reasons": [],
  "workload_class": "merge_heavy",
  "recommended_cluster": {
    "node_type_id": "Standard_E8ds_v4",
    "driver_node_type_id": "Standard_E8ds_v4",
    "num_workers": null,
    "autoscale": {"min_workers": 2, "max_workers": 8},
    "photon": true,
    "spot_workers": false,
    "spark_version": "<DBR LTS>",
    "data_security_mode": "SINGLE_USER"
  },
  "recommended_tier": "recommended",
  "options": [
    {"tier": "lean",        "node_type_id": "...", "num_workers_or_autoscale": "...",
     "spot_workers": true,  "photon": true, "est_runtime_hours": {"low":..,"high":..},
     "cost": {"per_run_usd": {"low":..,"expected":..,"high":..}}},
    {"tier": "recommended", "...": "..."},
    {"tier": "conservative","...": "..."}
  ],
  "rationale": {
    "est_source_gb": 1850, "est_shuffle_gb": 0, "read_partitions": 0,
    "shuffle_partitions": 0, "min_cores": 0, "mem_gb": 0,
    "skew_hedge": true, "photon_reason": "...", "autoscale_reason": "...",
    "node_family_reason": "..."
  },
  "cost_projection": {
    "per_run_usd": {"low": 0, "expected": 0, "high": 0},
    "monthly_usd": {"low": 0, "expected": 0, "high": 0},
    "runs_per_month": 30, "analog_job_id": "…|null", "confidence": "low|medium|high"
  },
  "assumptions": ["…"],
  "citations": ["…"],
  "generated_by": "cluster-forecaster"
}
```

## Bundled resources

- `scripts/forecast_size.py` — the offline forecaster: the pure `forecast()` brain
  (importable, no Databricks I/O) that infers the workload class, sizes the cluster, builds
  the three tiers and the cost projection, plus the Markdown renderer, fed via `--from-json`.
- `references/node_catalog.csv` — node specs (`node_type,family,vcpu,ram_gb,rel_dbu,cloud`),
  Azure D/E/DS/F families. Kept in sync with `databricks-cluster-sizer/references/node_catalog.csv`
  (same schema) so both twins recommend within one supported catalog.
- `references/billing_rates.csv` — **canonical DBU and storage rates for your organization**, sourced
  directly from `system.billing.list_prices`. Used by
  `forecast_size.py` as the primary pricing source (`load_billing_rates()`). Includes an
  `environment` column mapping each SKU to your organization's environment tier:

  | Environment | Region | Storage rate | Compute (DBU) rate |
  |---|---|---|---|
  | **DEV / QA** | US East (example) | $0.026/GB-month (example) | $0.30/DBU (example, all envs) |
  | **PREPROD / PROD** | US South Central (example) | $0.023/GB-month (example) | $0.30/DBU (example, all envs) |

  Compute DBU rates (`PREMIUM_JOBS_COMPUTE`) are identical across all environments in the
  bundled example — only storage rates differ by region. `storage_rates_by_env()` returns this split; the
  `cost_projection.storage_by_env` output block carries both rates so every forecast shows
  costs for DEV/QA and PREPROD/PROD side by side. **Replace the bundled values with your own** —
  update whenever `system.billing.list_prices` reports a price change (`price_end_time IS NULL` check).
- `references/throughput_baselines.csv` — **observed DBU/GB throughput ratios**, ideally derived from
  your organization's own historical run data (`COST_ESTIMATION_REFERENCE.md`). Maps workload type to DBU/GB
  (e.g. `simple_read_write = 3.0 DBU/GB`, `medium_transform = 6.0 DBU/GB`). Used as the
  cost-per-GB basis when no analog job is available. Loaded via `load_throughput_baselines()`.
  Ships with illustrative example values — replace with your own observed runs.
- `references/queries.sql` — the parameterized MCP queries: `[0]`/`[1]` source size + rows,
  `[2]` key-cardinality skew probe, `[3]`/`[4]` analog job + actual DBU/hr, `[5]` DBU pricing,
  `[6]` fleet node-type norms.
- `references/sizing-heuristics.md` — every threshold + multiplier with its `[O]` official
  source (the citation table the report draws from).
- `assets/cluster-sizing-forecast.template.{md,json}` — the report + machine-output templates.
- `README.md` — the full reasoning model: workload inference, the a-priori sizing formulas,
  the hybrid cost model + cited sources, guardrails, and the Forecast→Measure→Refine pairing.
- `evals/` — offline golden-fixture suite. Run `python evals/run_evals.py` to verify the
  heuristic, the cost projection, the three-tier output, the abstain path, and the
  `--from-json` ingest (and after any threshold/catalog change). All cases must pass,
  including `deliveryline_SA` (2.5 Bn-row Upsert/Delta-Merge → memory-optimized E-series), the
  conservative-overestimate safety case, and the abstain case when source tables are unreadable.

## Notes & scope

- Covers **pre-deployment job clusters** for batch Gold builds. Right-sizing a *deployed*
  cluster from telemetry is out of scope — that is `databricks-cluster-sizer` (Phase 2/3).
- **All Databricks access is via the SQL MCP server**; the skill never shells out to the
  Databricks CLI. Applying the recommendation is a human action via the Databricks UI or the
  Clusters/Jobs REST API — the SQL MCP server cannot edit compute.
- Cost projections are **estimates presented as ranges**: bottom-up bounded by analog actuals
  when billing is attributable, bottom-up-only (wider band, lower confidence) otherwise.
- The forecast is **conservative by design**; treat medium/low-confidence results as
  directional and let `cluster-optimizer` refine them from the first real runs.
