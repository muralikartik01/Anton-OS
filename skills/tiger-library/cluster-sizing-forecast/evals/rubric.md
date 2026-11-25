# Eval rubric — cluster-sizing-forecast

This is the offline regression guard for the a-priori forecaster: Phase 1 of the Forecast → Measure → Refine loop. `python evals/run_evals.py` imports `scripts/forecast_size.py`, runs the pure `forecast()` brain over local fixtures, validates the contract in `expected.json`, and exercises `--from-json` ingest without Databricks access.

## Global assertions
- Every result has the 11 authoritative top-level keys and `generated_by="cluster-forecaster"`.
- Every non-abstain result has exactly three tiers: `lean`, `recommended`, `conservative`.
- `cost_projection.per_run_usd` is ordered `low <= expected <= high`.
- No output contains forbidden Spark config strings: `spark.executor.memory` or `spark.dynamicAllocation`.
- Identical input is deterministic, and CLI ingest matches the pure function.

## Fixture coverage
- `deliveryline_sa` — golden 1.85 TB daily high-criticality Upsert/MERGE, six keys, eight joins, no merge partition pruning, analog + pricing. Asserts `merge_heavy`, non-abstain, memory-optimized E-series, multi-worker autoscale, Photon, non-trivial cost, and three tiers.
- `simple_etl_small` — sub-1 GB append with no distributed operators. Asserts `simple_etl`, smallest single-node general-purpose node, low cost, and no Photon.
- `join_heavy_smj` — two large facts over the broadcast threshold, no merge. Asserts `join_heavy`, large shuffle partition estimate, Photon, and a memory/general multi-worker node.
- `merge_pruned` — same heavy MERGE shape with `merge.partition_pruned=true`. Asserts lower shuffle/cost bounds than the unpruned golden case and the partition-pruning assumption.
- `abstain_unreadable` — zero-byte source metadata. Asserts safe abstain, non-empty reasons, and no guessed cluster.
- `no_analog_lowconf` — valid source metadata and schedule but no analog or pricing. Asserts bottom-up cost still exists, confidence is low, and missing analog/pricing assumptions are explicit.
- `window_heavy` — window plus count-distinct aggregation. Asserts window workload inference, memory hedge, skew hedge, Photon, and memory-optimized node selection.
