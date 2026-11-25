# Reasoning Model — Cluster Sizing Forecaster (pre-deployment)

This is the full reasoning model for the `cluster-sizing-forecast` skill: how a cluster and a
cost projection are forecast for a Gold table **before it has ever run**, from static design
signals instead of measured telemetry. `SKILL.md` is the operating guide; this file is the
*why*, with formulas and cited sources. Every threshold and multiplier here also appears in
`references/sizing-heuristics.md` with its citation, and the forecaster (`scripts/forecast_size.py`)
encodes exactly these rules.

> **Where this sits.** Databricks documents a **Forecast → Measure → Refine** loop for cluster
> sizing ([Compute config best practices](https://docs.databricks.com/aws/en/compute/cluster-config-best-practices)).
> This skill is **Phase 1 (Forecast)**. The `databricks-cluster-sizer` skill / `cluster-optimizer`
> agent is **Phase 2 (Measure) + Phase 3 (Refine)**. The forecast is intentionally a *conservative
> over-estimate*; the measured twin tightens it once real runs exist.

---

## 0. Why a heuristic estimator (not an ML model)

A brand-new Gold table has **no run history** — there is nothing to train or measure on. The
available signal is entirely **structural**: source byte-size, file count, partition columns,
key cardinality, the declared load strategy, and the joins/aggregations in the DRD/DAT. A
transparent, **cited rule-of-thumb model** is therefore both *sufficient* and *auditable*:

1. **No training data exists** for the table being forecast, so a learned model would have to
   borrow from loosely-related jobs — less defensible than first-principles Spark math.
2. **Adaptive Query Execution (AQE)** self-corrects shuffle-partition counts and some join
   strategies *at runtime* ([AQE](https://docs.databricks.com/aws/en/optimizations/aqe)), so
   pinpoint a-priori precision is neither achievable nor necessary — the cluster only needs to
   be *big enough*, and AQE handles the rest within that envelope.
3. **Explainability is the product.** Every number must trace to an official source so a human
   can sanity-check the rec before applying it. Intent: **defensible and explainable over
   precise**, and deliberately **conservative** (over-provision is the insurance; AQE can't
   grow the cluster mid-run).

---

## 1. Inputs and where they come from

| Input | Source | Used for |
| --- | --- | --- |
| Load strategy (Upsert / Append / SCD2 / Delete-Insert / Overwrite) | DRD/DAT (via manifest) | the dominant cost driver (MERGE is the most expensive) |
| Declared joins / lookups + which side is the dimension | DRD/DAT design | broadcast vs shuffle classification |
| Business / merge keys; partition columns | DRD/DAT + `DESCRIBE DETAIL` | MERGE scope, skew, partition pruning |
| Aggregations / window functions | DRD/DAT | extra shuffle + memory hedges |
| `sizeInBytes`, `numFiles`, `partitionColumns` | `DESCRIBE DETAIL <src>` (MCP **[0]**) | the **volume** that drives parallelism. Use bytes, **never** raw row counts — Parquet compresses 2–10× ([table details](https://docs.databricks.com/aws/en/tables/operations/table-details)) |
| Row counts | `information_schema` / `COUNT(*)` (MCP **[1]**) | secondary volume cross-check |
| Candidate-key cardinality | `APPROX_COUNT_DISTINCT` (MCP **[2]**) | **skew** signal |
| Nearest analog job + its DBU/hr + runtime | `system.lakeflow.jobs` ⋈ `system.billing.usage` (MCP **[3]/[4]**) | **empirical bound** on the cost estimate |
| Current Jobs / All-Purpose / Photon DBU price | `system.billing.list_prices` (MCP **[5]**, SCD2) | $ conversion |
| Fleet node-type norms | `system.compute.clusters` (MCP **[6]**) | keep the rec inside the supported catalog |
| Planned schedule + criticality | manifest | runs/month + spot/autoscale posture |

---

## 2. Workload-complexity inference (the cost drivers)

The forecaster classifies each declared operation and accumulates a `shuffle_GB` estimate. All
thresholds are cited.

### 2.1 Joins — broadcast vs shuffle
Spark chooses a **broadcast hash join (BHJ)** when one side fits under
`spark.sql.autoBroadcastJoinThreshold` (default **10 MB**), avoiding a shuffle entirely;
otherwise it does a **sort-merge join (SMJ)** which shuffles **both** sides
([Spark SQL perf tuning](https://spark.apache.org/docs/latest/sql-performance-tuning.html)).

| Dim side size | Classification | Shuffle contribution |
| --- | --- | --- |
| `< 10 MB` | BHJ (automatic) | 0 |
| `10 MB – 2 GB` | broadcast-hint candidate (still cheap; replicated to workers) | small (≈ dim size) |
| both sides `> 2 GB` | SMJ | `+(left_GB + right_GB) × 3` decompression |

AQE can **convert** a planned SMJ to a broadcast join at runtime if post-filter sizes turn out
small ([AQE](https://docs.databricks.com/aws/en/optimizations/aqe)) — another reason the
forecast errs large rather than small.

### 2.2 MERGE / Upsert / SCD2 / Delete-Insert — the dominant driver
Delta `MERGE` is the most expensive operation: it joins source to target, then rewrites matched
files. A-priori shuffle estimate:
```
merge_shuffle_GB = source_GB × 3 + matched_target_GB × 3
```
- `matched_target_GB` is the **scanned** portion of the target. If the MERGE condition includes
  the target's **partition column(s)**, partition pruning shrinks it dramatically; if it does
  **not**, assume a **full-target scan** (worst case)
  ([Delta best practices](https://docs.databricks.com/aws/en/delta/best-practices)).
- **Low Shuffle Merge** ([docs](https://docs.databricks.com/aws/en/optimizations/low-shuffle-merge))
  and **deletion vectors**
  ([docs](https://docs.databricks.com/aws/en/tables/features/deletion-vectors)) reduce the
  rewrite; note them as mitigations but still size for the un-mitigated case (conservative).

### 2.3 Skew
If a join/partition key's cardinality (`APPROX_COUNT_DISTINCT`) is `< 10×` the shuffle-partition
count, or there are known hot keys / heavy NULLs, partitions are unevenly sized and the largest
task dictates memory. Hedge: **+20–30 % executor memory**. AQE skew-join handling splits some
skewed partitions automatically
([Spark SQL perf tuning — skewJoin](https://spark.apache.org/docs/latest/sql-performance-tuning.html)),
but the memory hedge protects the case it cannot.

### 2.4 Aggregations and windows
- Low-cardinality `GROUP BY` / `PARTITION BY`, or an **unbounded** window frame, forces large
  per-key state → **+50 % executor memory**.
- `COUNT(DISTINCT …)` is **two** shuffles (distinct then count) — add its input to `shuffle_GB`
  twice ([Spark SQL perf tuning](https://spark.apache.org/docs/latest/sql-performance-tuning.html)).

### 2.5 Workload class
The dominant driver names the class, used for node-family + throughput selection:
`simple_etl` · `join_heavy` · `merge_heavy` · `agg_heavy` · `window_heavy` · `streaming`.

---

## 3. A-priori sizing heuristic

```
total_source_GB    = Σ source sizeInBytes / 1024³
read_partitions    = ceil(total_source_GB × 1024 / 128)              # 128 MB / input partition  [Spark SQL tuning]
shuffle_GB         = Σ contributions from §2 (joins, merge, agg)     # already ×3 for decompression
shuffle_partitions = ceil(shuffle_GB × 1024 / 128)                  # 64–128 MB / shuffle partition (AQE target)
min_cores          = ceil( max(read_partitions, shuffle_partitions) / 2.5 )   # 2–3 tasks / core  [Spark tuning]
mem_per_core_GB    = 4 baseline; 6–8 for shuffle/merge-heavy
total_memory_GB    = min_cores × mem_per_core_GB × (1 + skew_hedge + window_hedge)
```
Sources: [Spark Tuning Guide](https://spark.apache.org/docs/latest/tuning.html) (2–3 tasks/core,
2–3 GB/core baseline), [Spark SQL Perf Tuning](https://spark.apache.org/docs/latest/sql-performance-tuning.html)
(128 MB partition target).

**Worked example (regression-tested in `evals/`).** SMJ of a 500 GB fact with a 200 GB fact:
`shuffle_GB = (500+200)×3 = 2100 GB ≈ 2.1 TB`; `shuffle_partitions = ceil(2100×1024/128) ≈ 16 800`;
`min_cores = ceil(16 800 / 2.5) ≈ 6 720` instantaneous task slots — i.e. a large multi-worker
memory-optimized cluster, not a single node. (Real clusters run far fewer cores and let tasks
queue; the number sizes the *ceiling*, then node-fitting + autoscale pick a sane worker count.)

### 3.1 Fit to a node (from `references/node_catalog.csv`)
Pick the **cheapest node family** (lowest `rel_dbu` per unit capacity) that satisfies
`mem_per_core_GB` and the family rule below, then choose worker count so
`workers × node.vcpu ≈ a sane fraction of min_cores` (let autoscale cover the rest). Prefer
**fewer larger** nodes for shuffle-heavy work (less network), **more smaller** for embarrassingly
parallel scans.

| Condition | Node family | Rule |
| --- | --- | --- |
| shuffle/MERGE/join-heavy, spill-prone, `mem_per_core ≥ 6` | **memory (E-series)** | vertical scale; fewer larger nodes |
| CPU-bound / streaming / maintenance | **compute (F-series)** | more cores per $ |
| balanced general ETL | **general (D/DS-series)** | default |
| `total_source_GB < 1` and no distributed ops | **single-node** | driver-only |

Sources: [Compute config best practices](https://docs.databricks.com/aws/en/compute/cluster-config-best-practices),
[Configure compute](https://docs.databricks.com/aws/en/compute/configure).

### 3.2 Knobs
- **Photon** ([docs](https://docs.databricks.com/aws/en/compute/photon)): ON for SQL/DataFrame-
  heavy joins/aggregations/large scans (2–5× faster, but a DBU uplift — net usually cheaper per
  job); OFF for trivial/sub-second ETL and for UDF/ML/streaming-dominated code.
- **Autoscale**: ON when projected runtime `> ~30 min` and variable; **fixed** (or a **pool**)
  when the job is SLA-critical or very short. **Never** combine with `spark.dynamicAllocation.*`
  ([best practices](https://docs.databricks.com/aws/en/compute/cluster-config-best-practices)).
- **Spot/on-demand** by criticality: low → spot workers; medium → spot with on-demand fallback;
  high / SLA `< 2 h` → on-demand workers. **Driver is always on-demand**
  ([configure](https://docs.databricks.com/aws/en/compute/configure)).

---

## 4. Three tiers

| Tier | Posture | Differs on |
| --- | --- | --- |
| **Lean** | cheapest defensible; accepts longer/again-able runtime | smaller node or spot workers, lower autoscale max |
| **Recommended** ⭐ | the conservative default that ships to the notebook | the sized node, on-demand for critical jobs, Photon as inferred |
| **Conservative** | extra headroom for the first runs / unknown skew | one size up and/or higher autoscale max |

Tier selection mirrors the sizer's logic but driven by **planned** criticality/cadence:
high-criticality → Recommended leans to the on-demand, more-headroom side; low-criticality /
infrequent → Lean is acceptable as the default. The first **2–3 runs** should use a **fixed**
cluster so `cluster-optimizer` has clean telemetry to measure.

---

## 5. Cost projection (hybrid — bottom-up bounded by analog)

### 5.1 Bottom-up runtime
```
runtime_h = est_input_GB / throughput_GB_per_hr_per_100cores × (100 / cores) ÷ photon_mult
```
Throughput priors (GB/hr **per 100 cores**), from the cited cost/tuning sources, used as a band:

| Workload class | Throughput (GB/hr/100c) |
| --- | --- |
| simple_etl | 100–500 |
| join_heavy (SMJ) | 30–100 |
| merge_heavy (no prune) | 10–50 |
| merge_heavy (partition-pruned) | 50–200 |
| window_heavy | 20–80 |

`photon_mult` = 2–5× when Photon is on. Compute a **low/expected/high** runtime from the band.

### 5.2 Bottom-up dollars
```
per_run_DBU = (workers × worker_rel_dbu + driver_rel_dbu) × runtime_h        # rel_dbu from node_catalog
per_run_$   = per_run_DBU × jobs_dbu_price                                    # + cloud VM $ if VM rates supplied
monthly_$   = per_run_$ × runs_per_month
```
Use the **Jobs-Compute** DBU price (cheaper than All-Purpose — the *cluster type* is often a
bigger lever than node size). Pricing rows are SCD2: pick the current price via
`price_start_time`/`price_end_time`
([list_prices](https://docs.databricks.com/aws/en/admin/system-tables/pricing)).

### 5.3 Analog bound (empirical sanity check)
Find the nearest existing SRD/Gold job by **volume class + load type** (`system.lakeflow.jobs`),
pull its **actual DBU/hr + runtime** (`system.billing.usage` ⋈ `job_run_timeline`), scale by the
size ratio, and **clamp** the bottom-up `expected` into that envelope. If the bottom-up estimate
falls outside the analog band, **widen the band and lower confidence** — never silently pick one.
Report `low / expected / high`, the **confidence** (high if analog within 2× size and same load
type; medium if looser; low if no analog), and the **analog job id**.
Sources: [Cost management best practices](https://www.databricks.com/blog/best-practices-cost-management-databricks),
[billing.usage](https://docs.databricks.com/aws/en/admin/system-tables/billing).

### 5.4 Session-validated anchors (Azure SRD fleet)
- All-Purpose ≈ **$0.55/DBU**; Serverless ≈ **$0.95–1.05/DBU**; Jobs-Compute `<` All-Purpose
  (pull the exact current Jobs SKU rate at runtime via **[5]**).
- Observed fleet nodes: `Standard_DS12/DS13/DS14_v2`, `D8a_v4`, memory `E*ds_v4/v5`, compute
  `F*s_v2`; Jobs Compute; small autoscale (1–2 → 1–16).

---

## 6. Guardrails, abstain, and the refine loop

### 6.1 Hard guardrails (every tier)
- **No hardcoded Spark configs.** Never emit `spark.executor.memory`, `spark.executor.cores`,
  or `spark.dynamicAllocation.*` — Databricks sizes executors automatically and these override
  built-in optimization
  ([best practices](https://docs.databricks.com/aws/en/compute/cluster-config-best-practices)).
- **Driver never on spot.** Workers may be spot per criticality; the driver is always on-demand.
- **Conservative bias.** When two node sizes are plausible, the Recommended tier takes the larger;
  AQE can shrink work within a cluster but cannot grow the cluster mid-run.

### 6.2 Abstain rules
- **Source unreadable / no `sizeInBytes`** → `abstained=true`, reasons listed, no cluster guessed.
- **No analog found** → still forecast (bottom-up only) but widen the cost band and set
  `confidence="low"`.
- **MERGE with no partition key in the condition** → do not abstain, but assume full-target scan
  and flag it as the largest cost-uncertainty driver.

### 6.3 Forecast → Measure → Refine
The artifact explicitly names `cluster-optimizer` (agent A7) as the Phase-2/3 step that will
validate cost-per-run against this projection once the job has run, and recommends a **fixed**
cluster for the first 2–3 runs so that telemetry is clean. This closes the documented loop
([Compute config best practices](https://docs.databricks.com/aws/en/compute/cluster-config-best-practices)).

---

## 7. Risks & caveats

| Risk | Mitigation | Source |
| --- | --- | --- |
| Parquet compression varies 2–10× | size from `sizeInBytes`, apply a 3× in-memory/decompression factor | [table details](https://docs.databricks.com/aws/en/tables/operations/table-details) |
| Key skew invisible in size stats | `APPROX_COUNT_DISTINCT` probe + 20–30 % memory hedge | [Spark SQL perf tuning](https://spark.apache.org/docs/latest/sql-performance-tuning.html) |
| MERGE scope under-estimated | require a partition column in the MERGE condition; else assume full-target scan | [Delta best practices](https://docs.databricks.com/aws/en/delta/best-practices) |
| `numFiles` ≠ parallelism | use `sizeInBytes / 128 MB`, not file count | [tune file size](https://docs.databricks.com/aws/en/tables/tune-file-size) |
| Forecast error in general | conservative over-estimate + fixed cluster for first 2–3 runs, then A7 refines | [compute best practices](https://docs.databricks.com/aws/en/compute/cluster-config-best-practices) |

---

## 8. References

- Apache Spark — [Tuning Guide](https://spark.apache.org/docs/latest/tuning.html) ·
  [SQL Performance Tuning](https://spark.apache.org/docs/latest/sql-performance-tuning.html)
- Databricks compute — [Cluster config best practices](https://docs.databricks.com/aws/en/compute/cluster-config-best-practices) ·
  [Configure compute](https://docs.databricks.com/aws/en/compute/configure) ·
  [Photon](https://docs.databricks.com/aws/en/compute/photon) ·
  [AQE](https://docs.databricks.com/aws/en/optimizations/aqe)
- Delta — [Best practices](https://docs.databricks.com/aws/en/delta/best-practices) ·
  [MERGE](https://docs.databricks.com/aws/en/delta/merge) ·
  [Low Shuffle Merge](https://docs.databricks.com/aws/en/optimizations/low-shuffle-merge) ·
  [Deletion vectors](https://docs.databricks.com/aws/en/tables/features/deletion-vectors)
- Tables / metadata — [DESCRIBE DETAIL / table details](https://docs.databricks.com/aws/en/tables/operations/table-details) ·
  [Data skipping](https://docs.databricks.com/aws/en/tables/data-skipping) ·
  [Tune file size](https://docs.databricks.com/aws/en/tables/tune-file-size)
- Cost / system tables — [Cost management best practices](https://www.databricks.com/blog/best-practices-cost-management-databricks) ·
  [billing.usage](https://docs.databricks.com/aws/en/admin/system-tables/billing) ·
  [billing.list_prices](https://docs.databricks.com/aws/en/admin/system-tables/pricing) ·
  [system.compute](https://docs.databricks.com/aws/en/admin/system-tables/compute)
- Full internal research: `de-plugin/research/cluster-forecast-apriori-research.md`,
  `de-plugin/research/databricks-rightsizing-bestpractices.md`.
