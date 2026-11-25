# databricks-cluster-sizer

Cadence- and criticality-aware right-sizing for Databricks compute. Given measured
Spark/cluster utilization read from Unity Catalog **system tables** (via the
Databricks SQL MCP server), it recommends a safer, cheaper, or faster cluster — and
for scheduled **jobs** it returns **three ranked trade-off options** with **projected
cost (Δ$ and Δ%) and projected runtime (Δ%)** for each, so a human can decide where
to sit on the cost/performance curve.

This README explains **how the recommendation is made**. For the operational workflow
(which MCP queries to run, in what order) see [`SKILL.md`](SKILL.md). The deterministic
correctness gate is [`evals/run_evals.py`](evals/run_evals.py).

---

## TL;DR — the decision in one picture

```
 evidence (system tables)                derive                       emit
 ────────────────────────      ─────────────────────────     ───────────────────────
 cpu/mem percentiles + swap ─▶ classification (bottleneck) ─┐
 trigger / run_timeline     ─▶ cadence  (hourly/daily/wk)  ─┼─▶ 3 tiers ─▶ Recommended
 tags / health_rules        ─▶ criticality (high/med/low)  ─┤   Cost                 ┐
 last-N runs + billing $    ─▶ trend (drift/variance/SR)   ─┘   Balanced   each with ├─ apply
                                                                Performance  Δ$ + Δrt ┘
```

Two facts drive everything:

1. **What is the bottleneck?** (memory, CPU, driver, autoscale ceiling, or nothing —
   i.e. over-provisioned). This is the *safety* axis and decides the **direction**
   (up / down / keep / abstain).
2. **How often does it run and how much does it matter?** (cadence × criticality).
   This is the *economics* axis and decides **which of the three tiers is Recommended**.

Cheap, infrequent, non-critical jobs are pushed toward aggressive downsizing.
Frequent, critical, SLA-bound jobs are protected and optimized for cost **and**
performance. Nothing that endangers correctness or an SLA is ever the cheapest option.

---

## 1. Evidence: what we read

All inputs come from Unity Catalog system tables — never the Spark UI, never guesses.
The exact SQL lives in [`references/queries.sql`](references/queries.sql); the schema
notes are in [`research/databricks-system-tables-reference.md`](../research/databricks-system-tables-reference.md).

| Signal | Source | Used for |
|---|---|---|
| CPU / memory percentiles (p50/p95/peak), swap | `system.compute.node_timeline` | classification, sizing |
| Node type, worker count, autoscale min/max, `cluster_source` | `system.compute.clusters` | sizing, all-purpose caveat |
| Trigger type + cron | `system.lakeflow.jobs` (`trigger`/`trigger_type`) | cadence (primary) |
| Terminal run history (90 d) | `system.lakeflow.job_run_timeline` | cadence (fallback), trend |
| Per-run DBUs → USD | `system.billing.usage` × `system.billing.list_prices` | absolute cost baseline |
| `tags`, `health_rules` (SLA) | `system.lakeflow.jobs` | criticality |

If the signal is too thin (`< MIN_SAMPLES` runs) or the cluster is serverless /
all-purpose (billing not cleanly attributable), the tool **abstains or caveats**
rather than fabricating a number.

---

## 2. Classification — the safety axis (direction)

Thresholds (percent of node capacity, all tunable in
[`scripts/size_cluster.py`](scripts/size_cluster.py) and documented in `SKILL.md`):

| Verdict | Trigger | Direction |
|---|---|---|
| **memory-bound** | `mem_p95 ≥ 85%` or any swap | **up** (more RAM) |
| **CPU-bound** | `cpu_p95 ≥ 80%` *and* `mem_p95 < 70%` | **up** (more vCPU) |
| **driver-bound** | `driver_mem ≥ 85%` | **up** (bigger driver) |
| **autoscale-capped** | sustained at `max_workers` | raise ceiling ×1.5 |
| **over-provisioned** | `cpu_p95 < 40%` *and* `mem_p95 < 50%` | **down** |
| **balanced** | none of the above | **keep** node, tune knobs |
| **insufficient-data** | `< MIN_SAMPLES` runs | **abstain** |

Memory is always evaluated **before** cost: an idle-CPU but spilling cluster is
memory-bound, never "over-provisioned". This is what prevents the classic unsafe
downsize.

---

## 3. Cadence & criticality — the economics axis (recommended tier)

### Cadence (how often)
- **Primary:** `trigger_type` + cron from `system.lakeflow.jobs` when populated.
- **Fallback:** empirical `runs_per_week` over a 90-day window from
  `job_run_timeline` (terminal rows only).
- **Buckets** (`runs_per_week`): `hourly_or_more` (≥ 35) · `daily` (≥ 5) ·
  `weekly_or_less` (> 0) · `irregular` · `unknown`.

### Criticality (how much it matters)
Resolved in priority order, and the **source is always reported** for transparency:
1. **Tags** — keys `criticality | tier | priority | sla_tier` matched against
   high/medium/low vocab.
2. **SLA signal** — a `sla*` tag or any `health_rules` ⇒ **high**.
3. **Environment** — `dev`/`test` tag ⇒ **low**.
4. **Cadence fallback** — `hourly_or_more → high`, `daily → medium`,
   `weekly_or_less → low`.

### Default-tier selection
Evaluated **top-to-bottom; first match wins** — so explicit criticality is honored
before cadence (a critical job is protected even if it runs weekly; a non-critical
job stays cheap even if it runs hourly), and cadence only breaks ties when
criticality is medium/unknown:

| Priority | Situation | Recommended tier |
|---|---|---|
| 1 | Fix needed (memory/CPU/driver/autoscale) + **high** crit | **Performance** |
| 2 | Fix needed + **low** crit | **Cost** |
| 3 | Fix needed + medium/unknown crit | **Balanced** |
| 4 | Cost opportunity + **high** crit | **Performance** |
| 5 | Cost opportunity + **low** crit | **Cost** |
| 6 | Cost opportunity + `weekly_or_less` cadence | **Cost** |
| 7 | Cost opportunity + `hourly_or_more` cadence | **Performance** |
| 8 | Everything else / unknown signal | **Balanced** |

This is the rule that implements the user's directive: *weekly/non-critical → cheaper
downsizing; daily/critical → optimize cost **and** performance* — while never letting
an infrequent cadence override an explicit "this job is critical" signal.

> Criticality values (explicit input **and** tags) are normalized through one shared
> vocabulary (`high`: high/critical/p0/p1/tier-1/gold; `medium`: medium/p2/silver;
> `low`: low/p3/p4/bronze/dev/test) before any tier or spot decision, so a synonym
> like `P1` or `gold` is never mistaken for non-critical.

> Directional support for biasing by cadence/criticality is summarized in
> [`research/databricks-rightsizing-bestpractices.md`](../research/databricks-rightsizing-bestpractices.md)
> §2.2 (official guidance here is sparse, so the framework is explicit and tunable).

---

## 4. Trend analysis — why we use many runs, not one

A single run is noise. Over the last N runs (default 20 / 90 d) we summarize:
**runtime drift** (slope), **variance/stddev**, **success rate**, **cost average**,
and **spill presence**. Projections are anchored on **representative percentiles**
(p50/p90) and the **billed dollars** of the window, so a one-off spike neither triggers
an upsize nor inflates a saving. The trend (and its reliability) is surfaced in the
report so a reviewer sees *why* a number is what it is.

---

## 5. The three tiers

Every job recommendation emits **exactly three** options so the user owns the
trade-off. Construction depends on the classification:

| Tier | Intent | Spot workers | Autoscale | Photon | Sizing |
|---|---|---|---|---|---|
| **Cost-optimized** | cheapest viable | yes *(if criticality allows)* | yes *(if runtime permits + pool)* | only if SQL-heavy & net-cheaper | smallest node meeting RAM/vCPU + headroom; workers → partition floor |
| **Balanced** | headroom at low cost | spot + on-demand fallback | yes w/ pool | yes if SQL/DataFrame-heavy | right-size to p90 (≈70% mem / 65% cpu) |
| **Performance** | protect runtime/SLA | **on-demand only** | fixed or autoscale + pool | yes | keep proven node / scale up for shuffle-heavy |

- For a **fix** (memory/driver/CPU/autoscale) **all three tiers share the corrective
  node** — safety is non-negotiable; the tiers differ only on spot/Photon/autoscale.
- For **over-provisioned**, Cost downsizes + spot + autoscale, Balanced downsizes
  on-demand, Performance keeps the current node.
- For **balanced**, no tier changes the node; savings come only from knobs.

---

## 6. Projection formulas (with sources)

Every projection is a **range**, never a point — honesty about uncertainty is a
feature. Multipliers live as named constants in `scripts/size_cluster.py` and are
cited in `research/databricks-rightsizing-bestpractices.md` (§3–§4).

### Runtime
```
projected_runtime = baseline × parallelism_factor × memory_factor × photon_factor
```
- **parallelism_factor** — Amdahl's Law: `factor = (1 − p) + p / k`, where `p` is the
  workload's parallel fraction (`PARALLEL_FRACTION`, 0.40–0.95 by workload) and `k` is
  the core ratio, **capped at the shuffle-partition / task ceiling** so we never claim
  speedup past the point where adding workers stops helping (§3.1, §3.5).
- **memory_factor** — `SPILL_SPEEDUP` 0.60–0.85 when a memory upsize *eliminates*
  spill; otherwise 1.0 (§3.2).
- **photon_factor** — `PHOTON_RUNTIME` 0.30–0.60 (SQL-heavy) / 0.40–0.75 (simple ETL);
  never applied to ML/streaming/UDF/RDD jobs (§3.3, guardrail G7).

When the node is unchanged and no Photon/spill-fix applies, runtime Δ is reported as
**0** (we don't invent movement).

### Cost
```
est_cost_per_run = baseline_$ × (rate_new / rate_baseline) × (projected_runtime / baseline_runtime)
                 × spot_adjustment × photon_dbu_uplift
annual_$         = est_cost_delta_per_run × runs_per_week × 52
```
- **baseline_$** comes from actual billing (`usage_quantity × list_prices`). If billing
  is **not attributable** (all-purpose / serverless), we fall back to **relative DBU
  (`rel_dbu`)** and flag it loudly — no fake dollars (§4.2, §4.5).
- **rate_new / rate_baseline** = the catalog `rel_dbu` ratio of the two nodes.
- **spot_adjustment** — `SPOT_BLENDED_SAVING` 0.15–0.40 blended (VM-only discount,
  driver always on-demand) (§4.3).
- **photon_dbu_uplift** — `PHOTON_DBU_UPLIFT` 1.20–2.00× DBU rate, traded against the
  runtime cut (§4.4).
- **Annualized** savings are only shown when `runs_per_week` is known — cadence is what
  turns a per-run delta into a finance-relevant number.

---

## 7. Guardrails (G1–G9) — hard rules that override cost

Drawn from documented Databricks anti-patterns
([research §5.1](../research/databricks-rightsizing-bestpractices.md)). These can never
be violated by *any* tier, including Cost:

| | Rule |
|---|---|
| **G1** | Never spot for the **driver**. |
| **G2** | Never `spark.dynamicAllocation` together with cluster autoscaling. |
| **G3** | If `disk_spill > 0`, **do not downsize memory** until spill is resolved. |
| **G4** | If runtime `< 5 min`, no autoscaling without instance pools. |
| **G5** | Don't reduce workers below the shuffle-partition floor. |
| **G6** | Streaming → DLT/structured-streaming autoscaling, not classic autoscale. |
| **G7** | No Photon for sub-2s / UDF-heavy / RDD jobs. |
| **G8** | Disk-cache + new autoscaling = instability → flag, don't recommend. |
| **G9** | ML Runtime only for GPU/ML workloads. |

---

## 8. Caveats / abstain conditions

The tool degrades gracefully instead of being confidently wrong:

- **Insufficient data** (`< MIN_SAMPLES` runs) → abstain; ask for a longer window.
- **All-purpose / interactive** (`cluster_source IN ('UI','API')`) → cost not
  attributable → relative DBU + caveat, no absolute $.
- **Serverless** → no `node_timeline` → utilization-based sizing not possible.
- **Billing lag** → recent runs may lack finalized cost; trend is annotated.

---

## 9. How it's tested

| Layer | Command | Role |
|---|---|---|
| **Offline deterministic** | `python evals/run_evals.py` | authoritative gate — 15 golden fixtures over the pure `recommend()`; covers direction, cadence/criticality, 3-tier output, projection determinism, guardrails, caveats. Must be 100% green. |
| **Agent evals** | `evals/evals.json` | 5 end-to-end scenarios pinned to **Sonnet 4.6** (executor + analyzer); exercises the full agent behavior. |

Scoring criteria for both layers are in [`evals/rubric.md`](evals/rubric.md).

---

## 10. Layout

```
databricks-cluster-sizer/
├── SKILL.md                         # operational workflow (MCP query order)
├── README.md                        # ← you are here: the reasoning model
├── scripts/size_cluster.py          # pure recommend() + renderer (deterministic)
├── references/
│   ├── queries.sql                  # all system-table SQL ([1]–[9])
│   └── node_catalog.csv             # node specs + relative DBU weights
└── evals/
    ├── run_evals.py                 # offline gate
    ├── evals.json                   # 5 Sonnet-4.6 agent scenarios
    ├── expected.json                # golden expectations
    ├── rubric.md                    # scoring criteria
    └── fixtures/                    # golden input payloads
```

## Sources

- `research/databricks-rightsizing-bestpractices.md` — best practices, projection
  models (Amdahl/Photon/spill), cost formula, and guardrails G1–G9, with citations.
- `research/databricks-system-tables-reference.md` — verified system-table schema and
  the SQL behind cadence, per-run cost, and trends.
