---

name: databricks-cluster-sizer
description: >-
  Analyze accessible node-based Databricks job clusters and all-purpose/interactive
  clusters to recommend a safer, cheaper, or faster size from measured Spark/cluster
  utilization read from Unity Catalog system tables through the Databricks SQL MCP
  server. For scheduled JOBS it is cadence- and criticality-aware: it reads how often
  a job runs and how critical it is, analyzes trends across recent runs, and returns
  three ranked trade-off options (Cost-optimized / Balanced / Performance-optimized)
  with projected cost (Δ$ and Δ%) AND projected runtime (Δ%) for each, biasing
  infrequent/non-critical jobs toward cheaper downsizing and daily/critical jobs
  toward cost-and-performance. It abstains rather than guessing when the system
  tables are unavailable or the signal is weak. Use this whenever the user provides
  or mentions a Databricks workspace, job run id, cluster id, slow or expensive Spark
  workload, OOM/spill, idle or over-provisioned cluster, autoscale ceiling, DBU waste,
  node-type choice, worker count, cost-vs-performance trade-off, weekly/daily/hourly
  job cadence, criticality/SLA, cluster cost optimization, or asks "what node type /
  how many workers should I use", "make this cheaper without breaking the SLA", or
  "why is this job so expensive" — even when they do not say the word "skill".
compatibility: Requires a Databricks SQL MCP server (.../api/2.0/mcp/sql) for all data access, plus Python 3.9+ for the offline scorer. No Databricks CLI is used.

---

# Databricks Cluster Sizer

Capture real per-node CPU/memory utilization for a Databricks cluster (a job run
or an all-purpose/interactive cluster) and propose a better size — node type,
worker count, or autoscale ceiling. For scheduled **jobs**, it goes further: it
reads the job's **cadence** (weekly/daily/hourly) and **criticality**, studies
**trends across recent runs**, and returns **three ranked trade-off options**
(Cost-optimized / Balanced / Performance-optimized), each with a **projected cost
(Δ$ and Δ%) and projected runtime (Δ%)**. Every recommendation is grounded in
measured utilization and billing, not the cluster's name or guesswork, and the
tool **abstains rather than downsizes** when the signal is weak, so it is safe to
run across a whole fleet.

## When to use

Reach for this skill when someone wants to right-size Databricks compute and, in
particular, to **trade cost against performance deliberately**: cutting cost on an
idle/over-provisioned weekly job, optimizing a daily job for both speed and spend,
protecting an hourly/SLA-bound job's runtime while trimming waste, fixing OOM/spill
by adding memory, clearing a CPU bottleneck, or raising an autoscale cap. It works
on **any** cluster the caller can see, and is **cadence-aware for scheduled jobs**.

## Prerequisites

| Requirement | Needed for | Notes |
| --- | --- | --- |
| **Databricks SQL MCP server** (`https://<host>/api/2.0/mcp/sql`) | always | All Databricks data is read by running SQL through whichever Databricks SQL MCP tool is configured in this workspace (commonly named like `*_execute_sql` / `*-execute_sql`). If more than one is configured (e.g. one per environment), pick the one whose workspace owns the target cluster. **No Databricks CLI is used.** |
| **Python 3.9+** | always | Runs `scripts/size_cluster.py` (the offline scorer) and the eval suite. Standard library only; performs no Databricks access. |
| **UC `system.compute`** + `SELECT` on `system.compute.node_timeline`, `system.compute.clusters` | utilization + config | Where the real CPU/mem "Spark logs" and the SCD2 cluster config live. |
| **UC `system.lakeflow`** + `SELECT` on `job_task_run_timeline`, `job_run_timeline`, `jobs` | run resolution, cadence, criticality | Maps a run id to its cluster/window; supplies schedule, tags and `health_rules` for cadence + criticality. Empirical cadence is derived from `job_run_timeline` when the schedule columns are sparse. |
| **UC `system.billing`** + `SELECT` on `usage`, `list_prices` | absolute $ cost + trends | Anchors cost projections in **actual billed dollars** per run. Optional: without it, cost is shown as **relative DBU %** with a caveat. |
| **A SQL warehouse** the MCP server can use, caller has **CAN USE** | always | The MCP server runs the queries on an authorized warehouse on your behalf. |

This skill **requires** the Databricks SQL MCP server — it is the only way it
reaches Databricks. There is no CLI fallback; if the `system.compute` tables are
not available, the skill **abstains** instead of guessing. The `lakeflow` and
`billing` tables are *enrichment*: missing them degrades to a single (non-cadence)
verdict or relative-only cost, each clearly caveated — never a silent wrong answer.

## Workflow

All Databricks access is done by **you, the agent**, by running SQL through the
Databricks SQL MCP server. `scripts/size_cluster.py` never touches Databricks — it
only scores the telemetry you collect. The queries below live in
`references/queries.sql`; run each with the MCP server's SQL tool (commonly
`execute_sql`).

1. **Pick the MCP server & target.** If this workspace has more than one
   Databricks SQL MCP tool configured (e.g. one per environment), pick the one
   whose workspace owns the target cluster; otherwise use the single tool available.
   - A **scheduled job** → start from its `run_id` (or `job_id`). This unlocks the
     full cadence/criticality/trend analysis and the three-tier output.
   - An **always-on/interactive cluster** → start from its `cluster_id` and a
     lookback window. You still get a sized verdict; cadence defaults to Balanced.
2. **Resolve the run** (when starting from a `run_id`) — query **[0]**
   (`job_task_run_timeline`) → `cluster_id`, `start_ts`, `end_ts`, `job_id`.
3. **Read the config** — query **[2]** (`system.compute.clusters`) for node types,
   worker count, autoscale bounds, and `cluster_source` (JOB / UI / API / PIPELINE).
4. **Capture utilization** — query **[1]** (`node_timeline`) for driver/worker CPU
   & memory percentiles + swap + sample minutes, and query **[3]** for observed
   peak workers. Substitute `:cluster_id`, `:start_ts`, `:end_ts`.
5. **Enrich the job (scheduled jobs only):**
   - Query **[4]** (`system.lakeflow.jobs`) → `schedule`, `trigger_type`, `tags`,
     `health_rules` (criticality + cadence signal).
   - Query **[5]** (`job_run_timeline`, 90 days) → empirical `runs_per_week` and
     inter-run gaps (robust cadence fallback).
   - Query **[6]**/**[8]** (last N runs) → per-run duration trend, variance, and
     success rate.
   - Query **[7]** (`system.billing.usage` × `list_prices`) → **billed $ per run**
     (the cost anchor). Query **[9]** confirms the cost is attributable (not
     all-purpose / serverless).
6. **Score it.** Assemble one JSON payload and run the scorer:

   ```bash
   # payload.json = {
   #   "config":  {...from [2]...},
   #   "profile": {
   #     "source": "system_tables",
   #     "observed_peak_workers": <from [3]>,
   #     "worker":  {...from [1] driver=false...},
   #     "driver":  {...from [1] driver=true...},
   #     "job": {                              # optional — enables cadence/tiers
   #       "tags": {...from [4]...},
   #       "health_rules": [...from [4]...],
   #       "cadence": { "trigger_type": "...", "runs_per_week": <from [5]> }
   #     },
   #     "workload": { "workload_type": "simple_etl|sql_heavy|ml|streaming",
   #                   "shuffle_partitions": 200, "is_serverless": false,
   #                   "uses_pool": false },
   #     "pricing": { "baseline_cost_usd": <from [7]> },   # optional $ anchor
   #     "trend":   { "n_runs": 20, "runtime_seconds_p50": ..., ... }  # from [6]/[8]
   #   } }
   python scripts/size_cluster.py --from-json payload.json        # Markdown report
   python scripts/size_cluster.py --from-json payload.json --json # machine output
   ```

   Every nested block under `profile` is **optional**. With none of them you get the
   classic single verdict (defaulted to Balanced); add `job`/`workload`/`pricing`/
   `trend` to unlock cadence-awareness, the three tiers, and the projections. The
   payload shape matches the fixtures in `evals/fixtures/`.
7. **Read the options & apply.** The report shows the classification, evidence, a
   **trend summary**, and an **Options table** with all three tiers (node, ΔDBU,
   projected Δruntime, projected Δcost, spot/Photon), the **Recommended** tier
   starred, an **annualized** savings figure when billing is known, **caveats**,
   and an **apply block** — JSON to apply via the Databricks **UI** or the
   **Clusters/Jobs REST API** (never the CLI), after a human sanity-check.

## How the recommendation is made

See `README.md` for the full reasoning model. In brief:

**1. Classify (deterministic, worker-node signal).** From `node_timeline`
percentiles (`cpu_busy = cpu_user + cpu_system`, `mem_used_percent`,
`mem_swap_percent`):

| Observation (worker nodes) | Class | Base action |
| --- | --- | --- |
| `< 10` sample-minutes | insufficient data | **Abstain** — never size on thin signal |
| `mem_p95 ≥ 85%` or any swap | memory-bound | Higher-RAM node; ≥1.5× RAM if swapping |
| driver `mem_p95 ≥ 85%` (workers fine) | driver-bound | Upsize **driver only** |
| `cpu_p95 ≥ 80%` and `mem_p95 < 70%` | CPU-bound | Bigger/more workers; raise cap if pinned |
| `cpu_p95 < 40%` and `mem_p95 < 50%`, no swap | over-provisioned | Downsize to smallest node with headroom |
| otherwise | balanced | Keep current size |

Node selection picks the **smallest node by relative DBU** that still meets
post-change headroom targets (mem ≤ 70%, cpu ≤ 65%) from
`references/node_catalog.csv` — a capacity/price search, never index math.

**2. Derive cadence & criticality (scheduled jobs).** Cadence buckets to
`hourly_or_more` (≥35 runs/wk, ~5+/day) / `daily` (≥5/wk) / `weekly_or_less` /
`irregular` from the schedule or empirical `runs_per_week`. Criticality
(`high`/`medium`/`low`) is resolved in priority order: **explicit input** →
**tags / SLA / `health_rules`** → **derived from cadence**. Every criticality value
(explicit or tag) is normalized through one shared vocabulary (e.g. `critical`,
`p1`, `gold` → `high`) so a synonym is never mistaken for non-critical. The source
is always shown for transparency.

**3. Build three tiers & project.** From the base verdict the scorer emits
**Cost-optimized**, **Balanced**, and **Performance-optimized** options that differ
on node, spot, autoscale and Photon. For each it projects **runtime** (Amdahl's-Law
parallel-speedup capped at the shuffle-partition ceiling, plus spill-removal and
Photon factors) and **cost** (relative-DBU weight × runtime, with Photon DBU uplift
and blended spot savings; absolute $ and annualized when billing is supplied) — both
as **ranges**, never false precision.

**4. Pick the Recommended tier.** Explicit criticality wins over cadence: **high**
crit → **Performance** (even for a weekly job), **low** crit → **Cost** (even for an
hourly job); when criticality is medium/unknown, cadence breaks the tie —
weekly → **Cost**, hourly → **Performance**, daily → **Balanced**. Mandatory fixes
(memory/driver/CPU/autoscale) keep the corrective node across all tiers and only
trade spot/Photon, so a critical job is never made unstable to save money.

**5. Guardrails & caveats.** Hard rules (e.g. never downsize RAM while spilling,
never spot-driver, no autoscale on sub-5-minute jobs without a pool, no Photon for
ML/streaming/UDF) constrain every tier. All-purpose (non-attributable billing),
serverless (no node timeline), and missing-billing cases emit explicit caveats and
fall back to relative DBU instead of guessing.

## Bundled resources

- `scripts/size_cluster.py` — the offline scorer: the pure `recommend()` brain
  (importable, no Databricks I/O) that emits the three tiers + projections, plus the
  Markdown renderer, fed via `--from-json`.
- `references/node_catalog.csv` — node specs (`node_type, family, vcpu, ram_gb,
  rel_dbu, cloud`), incl. F-series compute nodes. Edit to match your cloud/contract.
- `references/queries.sql` — the parameterized MCP queries: `[0]` run resolution,
  `[1]`/`[3]` utilization + peak workers, `[2]` config, and `[4]`–`[9]` for cadence,
  criticality, last-N-run trends, per-run billed cost, and attribution checks.
- `README.md` — the full reasoning model: cadence/criticality, the three-tier
  framework, projection formulas + cited sources, and guardrails.
- `evals/` — offline golden-fixture suite. Run `python evals/run_evals.py` to verify
  the logic, the cadence/tier output, and the `--from-json` ingest (and after any
  threshold/catalog change). All cases must pass, including the safety case that
  forbids downsizing under memory pressure and the abstain case when system tables
  are unavailable.

## Notes & scope

- Covers node-based compute: **job clusters + all-purpose/interactive**. SQL
  warehouses and DLT-specific autoscaling are out of scope (a DLT *cluster* can
  still be analyzed from its cluster id).
- **All Databricks access is via the SQL MCP server**; the skill never shells out to
  the Databricks CLI. Applying a recommendation is done by a human via the
  Databricks UI or the Clusters/Jobs REST API — the SQL MCP server cannot edit compute.
- Configuring the MCP servers themselves (the user's `mcp.json`) is out of scope.
- Cost projections are **billed $** when `system.billing` is attributable, otherwise
  **relative DBU %** — both are estimates and presented as ranges. Runtime
  projections are model-based ranges, not guarantees.
- Treat medium/low-confidence results as directional; validate on a representative
  run before rolling out fleet-wide.
