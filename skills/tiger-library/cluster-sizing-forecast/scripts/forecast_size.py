#!/usr/bin/env python3
"""
forecast_size.py — offline Databricks cluster sizing forecaster.

This script performs NO Databricks access. The agent gathers source metadata,
design signals, analogs and pricing through the Databricks SQL MCP server, then
passes one JSON payload to this deterministic scorer. The sizing logic lives in
forecast(), a PURE function with no I/O so evals can import it directly.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CATALOG = REPO_ROOT / "references" / "node_catalog.csv"
DEFAULT_BILLING_RATES = REPO_ROOT / "references" / "billing_rates.csv"
DEFAULT_THROUGHPUT = REPO_ROOT / "references" / "throughput_baselines.csv"

BROADCAST_AUTO_BYTES = 10 * 1024 ** 2
BROADCAST_HINT_BYTES = 2 * 1024 ** 3
BYTES_PER_GB = 1024 ** 3
PARTITION_MB = 128
TASKS_PER_CORE = 2.5
DEFAULT_SPARK_VERSION = "<DBR LTS>"
DEFAULT_SECURITY_MODE = "SINGLE_USER"
GENERATED_BY = "cluster-forecaster"

# Every emitted citation carries an [O] official-source marker so consumers and
# evals can verify thresholds/multipliers are backed by first-party guidance.
CITATIONS = [
    "[O] Spark SQL performance tuning (AQE, join selection, shuffle partitions) — https://spark.apache.org/docs/latest/sql-performance-tuning.html",
    "[O] Spark tuning guide (memory, parallelism, data locality) — https://spark.apache.org/docs/latest/tuning.html",
    "[O] Databricks compute configuration best practices — https://docs.databricks.com/aws/en/compute/cluster-config-best-practices",
    "[O] Databricks compute configuration reference — https://docs.databricks.com/aws/en/compute/configure",
    "[O] Databricks Photon engine — https://docs.databricks.com/aws/en/compute/photon",
    "[O] Databricks Adaptive Query Execution (AQE) — https://docs.databricks.com/aws/en/optimizations/aqe",
    "[O] Delta Lake best practices (partitioning, OPTIMIZE, file sizing) — https://docs.databricks.com/aws/en/delta/best-practices",
    "[O] Databricks table details / DESCRIBE DETAIL metadata — https://docs.databricks.com/aws/en/tables/operations/table-details",
    "[O] Databricks system tables: pricing — https://docs.databricks.com/aws/en/admin/system-tables/pricing",
    "[O] Databricks system tables: billing usage — https://docs.databricks.com/aws/en/admin/system-tables/billing",
    "[O] Databricks best practices for cost management — https://www.databricks.com/blog/best-practices-cost-management-databricks",
]

THROUGHPUT = {
    "simple_etl": (100.0, 500.0),
    "join_heavy": (30.0, 100.0),
    "merge_pruned": (50.0, 200.0),
    "merge_unpruned": (10.0, 50.0),
    "agg_heavy": (40.0, 150.0),
    "window_heavy": (20.0, 80.0),
    "streaming": (80.0, 250.0),
}

CRIT_HIGH = {"high", "critical", "p0", "p1", "tier-1", "tier1", "t1", "gold"}
CRIT_MED = {"medium", "med", "p2", "tier-2", "tier2", "t2", "silver"}
CRIT_LOW = {"low", "p3", "p4", "tier-3", "tier3", "t3", "bronze", "dev", "test", "sandbox"}


def load_catalog(path=DEFAULT_CATALOG):
    """Load the node catalog CSV into a list of typed dicts."""
    rows = []
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rows.append({
                "node_type": r["node_type"].strip(),
                "family": r["family"].strip(),
                "vcpu": int(r["vcpu"]),
                "ram_gb": float(r["ram_gb"]),
                "rel_dbu": float(r["rel_dbu"]),
                "cloud": r.get("cloud", "").strip(),
            })
    return rows


def load_billing_rates(path=DEFAULT_BILLING_RATES):
    """Load billing rates from references/billing_rates.csv.

    Source of truth: COST_ESTIMATION_REFERENCE.md (system.billing.list_prices,
    your organization's Azure account). Replace billing_rates.csv with your own
    exported rates.
    Returns a dict keyed by sku_name with rate_usd, unit, and environment.
    """
    rates = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rates[r["sku_name"].strip()] = {
                "rate_usd": float(r["rate_usd"]),
                "unit": r["unit"].strip(),
                "region": r["region"].strip(),
                "environment": r.get("environment", "").strip(),
            }
    return rates


def storage_rates_by_env(billing_rates: dict) -> dict:
    """Return storage rates keyed by environment tier (rename to match your org).

    DEV/QA  → US East           ($0.026/GB-month)
    PREPROD/PROD → US South Central  ($0.023/GB-month)
    """
    dev_qa = billing_rates.get("PREMIUM_DATABRICKS_STORAGE_US_EAST", {})
    preprod_prod = billing_rates.get("PREMIUM_DATABRICKS_STORAGE_US_SOUTH_CENTRAL", {})
    return {
        "dev_qa": {
            "environments": ["DEV", "QA"],
            "region": dev_qa.get("region", "US East"),
            "storage_rate_usd_gb_month": dev_qa.get("rate_usd", 0.026),
        },
        "preprod_prod": {
            "environments": ["PREPROD", "PROD"],
            "region": preprod_prod.get("region", "US South Central"),
            "storage_rate_usd_gb_month": preprod_prod.get("rate_usd", 0.023),
        },
    }


def load_throughput_baselines(path=DEFAULT_THROUGHPUT):
    """Load DBU/GB throughput baselines from references/throughput_baselines.csv.

    Source of truth: COST_ESTIMATION_REFERENCE.md (observed historical runs —
    replace with your organization's own historical run data).
    Returns a dict keyed by workload_type.
    """
    baselines = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            baselines[r["workload_type"].strip()] = {
                "dbu_per_gb": float(r["dbu_per_gb"]),
                "overhead_pct": float(r["overhead_pct"]),
                "description": r["description"].strip(),
            }
    return baselines


def _billing_defaults(billing_rates: dict) -> dict:
    """Extract the three pricing scalars forecast() expects from the billing rates dict."""
    jobs = billing_rates.get("PREMIUM_JOBS_COMPUTE", {}).get("rate_usd", 0.30)
    all_purpose = billing_rates.get("PREMIUM_ALL_PURPOSE_COMPUTE", {}).get("rate_usd", 0.55)
    # Photon DBU rate is the same as classic ($0.30) but runs 2-5x faster;
    # the multiplier here is the RUNTIME speedup factor (not the DBU price ratio).
    photon_mult = 2.0
    return {"jobs_dbu_usd": jobs, "all_purpose_dbu_usd": all_purpose, "photon_dbu_mult": photon_mult}


def node_by_type(catalog, node_type):
    for n in catalog:
        if n["node_type"] == node_type:
            return n
    return None


def forecast(inputs: dict, catalog: list[dict]) -> dict:
    """Forecast a first-run job cluster from static source/design signals.

    Pure and deterministic: no file, network, clock, Databricks, or CLI access.
    """
    inputs = inputs or {}
    assumptions = []
    sources = inputs.get("sources") or []
    positive_sources = [s for s in sources if _to_float(s.get("size_bytes")) > 0]
    if not positive_sources:
        reasons = []
        if not sources:
            reasons.append("no source provided")
        else:
            reasons.append("no source has a positive size_bytes")
        return _abstain_result(reasons, assumptions)

    total_source_gb = sum(_to_float(s.get("size_bytes")) for s in positive_sources) / BYTES_PER_GB
    read_partitions = _ceil_partition_gb(total_source_gb)
    schedule = inputs.get("schedule") or {}
    criticality = _criticality(schedule.get("criticality") or inputs.get("criticality"))
    runs_per_month = int(_to_float(schedule.get("runs_per_month"), 30) or 30)
    retention_days = _to_float(schedule.get("retention_days"), None)
    if retention_days is None:
        # Caller must have prompted the user; if still missing, flag it clearly.
        assumptions.append(
            "WARNING: schedule.retention_days not provided. "
            "Storage cost CANNOT be calculated. "
            "Prompt the user for retention_days before presenting a complete cost estimate."
        )
    retention_days = int(retention_days) if retention_days is not None else None

    # Load pricing from billing_rates.csv (COST_ESTIMATION_REFERENCE.md source of truth).
    # The payload may override individual keys; missing keys fall back to the reference file.
    _ref_pricing = _billing_defaults(load_billing_rates())
    pricing = dict(inputs.get("pricing") or {})
    if pricing.get("jobs_dbu_usd") is None:
        pricing["jobs_dbu_usd"] = _ref_pricing["jobs_dbu_usd"]
        assumptions.append(
            f"pricing.jobs_dbu_usd sourced from billing_rates.csv "
            f"(PREMIUM_JOBS_COMPUTE {_ref_pricing['jobs_dbu_usd']} USD/DBU)"
        )
    if pricing.get("all_purpose_dbu_usd") is None:
        pricing["all_purpose_dbu_usd"] = _ref_pricing["all_purpose_dbu_usd"]
        assumptions.append(
            f"pricing.all_purpose_dbu_usd sourced from billing_rates.csv "
            f"(PREMIUM_ALL_PURPOSE_COMPUTE {_ref_pricing['all_purpose_dbu_usd']} USD/DBU)"
        )
    if pricing.get("photon_dbu_mult") is None:
        pricing["photon_dbu_mult"] = _ref_pricing["photon_dbu_mult"]
        assumptions.append(
            f"pricing.photon_dbu_mult sourced from billing_rates.csv "
            f"(Photon same DBU rate as classic; runtime speedup multiplier {_ref_pricing['photon_dbu_mult']}x)"
        )

    join_shuffle_gb, join_notes = _join_shuffle(inputs, total_source_gb)
    merge_shuffle_gb, merge_pruned, merge_notes = _merge_shuffle(inputs, total_source_gb)
    agg_shuffle_gb, window_hedge, agg_notes, has_window, has_agg = _aggregation_shuffle(inputs, total_source_gb)
    assumptions.extend(join_notes)
    assumptions.extend(merge_notes)
    assumptions.extend(agg_notes)

    shuffle_gb = join_shuffle_gb + merge_shuffle_gb + agg_shuffle_gb
    shuffle_partitions = _ceil_partition_gb(shuffle_gb)
    min_cores = int(math.ceil(max(read_partitions, shuffle_partitions, 1) / TASKS_PER_CORE))

    skew_hedge, skew_pct = _skew_hedge(inputs.get("skew") or {}, shuffle_partitions)
    if skew_hedge:
        assumptions.append("skew hedge applied because key cardinality/hot-key signal indicates uneven partitions")

    workload_class = _workload_class(inputs, merge_shuffle_gb, join_shuffle_gb,
                                     agg_shuffle_gb, has_window, has_agg)
    mem_per_core = _mem_per_core(workload_class, shuffle_gb)
    mem_gb = min_cores * mem_per_core * (1.0 + skew_pct + window_hedge)

    single_node = total_source_gb < 1.0 and shuffle_gb <= 0 and workload_class == "simple_etl"
    node_family, node_family_reason = _node_family(workload_class, mem_per_core, single_node)
    photon, photon_reason = _photon(inputs, workload_class, total_source_gb, shuffle_gb)

    rec_runtime_probe = _runtime_hours(total_source_gb, workload_class, merge_pruned,
                                       max(1, _target_cores(min_cores, workload_class)), photon,
                                       _to_float(pricing.get("photon_dbu_mult")))["expected"]
    autoscale, autoscale_reason = _autoscale(schedule, rec_runtime_probe, single_node,
                                             workload_class, shuffle_partitions)

    tiers = _build_tiers(catalog, node_family, single_node, min_cores, mem_per_core,
                         workload_class, criticality, photon, autoscale)

    for tier in tiers:
        worker = node_by_type(catalog, tier["node_type_id"])
        driver = worker
        cores = _tier_cores(worker, tier["workers"], single_node)
        runtime = _runtime_hours(total_source_gb, workload_class, merge_pruned, cores,
                                 tier["photon"], _to_float(pricing.get("photon_dbu_mult")))
        cost = _cost_band(runtime, worker, driver, tier["workers"], pricing, inputs.get("analog"),
                          total_source_gb, inputs.get("load_strategy"), assumptions)
        tier["est_runtime_hours"] = {"low": runtime["low"], "high": runtime["high"]}
        tier["_runtime_full"] = runtime
        tier["cost"] = {"per_run_usd": cost["per_run_usd"]}
        tier["_cost_projection"] = cost

    recommended = next(t for t in tiers if t["tier"] == "recommended")
    rec_workers = recommended["workers"]
    rec_autoscale = recommended["autoscale"]
    recommended_cluster = {
        "node_type_id": recommended["node_type_id"],
        "driver_node_type_id": recommended["node_type_id"],
        "num_workers": None if rec_autoscale else rec_workers,
        "autoscale": rec_autoscale,
        "photon": recommended["photon"],
        "spot_workers": recommended["spot_workers"],
        "spark_version": DEFAULT_SPARK_VERSION,
        "data_security_mode": DEFAULT_SECURITY_MODE,
    }

    cost_projection = recommended["_cost_projection"]
    billing_rates = load_billing_rates()
    env_storage = storage_rates_by_env(billing_rates)

    # Storage cost — requires retention_days (must be prompted from user if absent).
    # Formula (COST_ESTIMATION_REFERENCE.md): raw source volume, no compression.
    #   retention_snapshots = retention_days × runs_per_month / 30
    #   storage_steady_state_gb = total_source_gb × retention_snapshots
    #   annual_storage_cost = storage_ss_gb × rate_per_gb_month × 12
    if retention_days is not None and retention_days > 0:
        retention_snapshots = retention_days * runs_per_month / 30
        storage_ss_gb = round(total_source_gb * retention_snapshots, 2)
        for env_info in env_storage.values():
            rate = env_info["storage_rate_usd_gb_month"]
            env_info["retention_days"] = retention_days
            env_info["retention_snapshots"] = round(retention_snapshots, 1)
            env_info["storage_steady_state_gb"] = storage_ss_gb
            env_info["annual_storage_usd"] = round(storage_ss_gb * rate * 12, 2)
            env_info["formula"] = (
                f"{total_source_gb:.2f} GB × {retention_snapshots:.1f} snapshots "
                f"× ${rate}/GB-month × 12 months"
            )
    else:
        for env_info in env_storage.values():
            env_info["retention_days"] = None
            env_info["storage_steady_state_gb"] = None
            env_info["annual_storage_usd"] = None
            env_info["formula"] = "retention_days not provided — storage cost unknown"
    cost_projection = {
        "per_run_usd": cost_projection["per_run_usd"],
        "monthly_usd": {
            "low": _money(cost_projection["per_run_usd"]["low"] * runs_per_month),
            "expected": _money(cost_projection["per_run_usd"]["expected"] * runs_per_month),
            "high": _money(cost_projection["per_run_usd"]["high"] * runs_per_month),
        },
        "runs_per_month": runs_per_month,
        "analog_job_id": cost_projection["analog_job_id"],
        "confidence": cost_projection["confidence"],
        "storage_by_env": env_storage,
        "note": (
            "Compute (DBU) rate is identical across all environments ($0.30/DBU PREMIUM_JOBS_COMPUTE). "
            "Storage rate differs by region: DEV/QA uses US East ($0.026/GB-month); "
            "PREPROD/PROD uses US South Central ($0.023/GB-month)."
        ),
    }

    options = []
    for tier in tiers:
        workers_desc = _workers_desc(tier["workers"], tier["autoscale"], single_node)
        options.append({
            "tier": tier["tier"],
            "node_type_id": tier["node_type_id"],
            "num_workers_or_autoscale": workers_desc,
            "spot_workers": tier["spot_workers"],
            "photon": tier["photon"],
            "est_runtime_hours": tier["est_runtime_hours"],
            "cost": tier["cost"],
        })

    if not inputs.get("analog"):
        assumptions.append("no analog supplied; cost projection is bottom-up only with low confidence")

    return {
        "abstained": False,
        "abstain_reasons": [],
        "workload_class": workload_class,
        "recommended_cluster": recommended_cluster,
        "recommended_tier": "recommended",
        "options": options,
        "rationale": {
            "est_source_gb": _num(total_source_gb),
            "est_shuffle_gb": _num(shuffle_gb),
            "read_partitions": read_partitions,
            "shuffle_partitions": shuffle_partitions,
            "min_cores": min_cores,
            "mem_gb": int(math.ceil(mem_gb)),
            "skew_hedge": bool(skew_hedge),
            "photon_reason": photon_reason,
            "autoscale_reason": autoscale_reason,
            "node_family_reason": node_family_reason,
        },
        "cost_projection": cost_projection,
        "assumptions": _dedupe(assumptions),
        "citations": CITATIONS[:],
        "generated_by": GENERATED_BY,
    }


def _join_shuffle(inputs, total_source_gb):
    shuffle = 0.0
    assumptions = []
    for j in inputs.get("joins") or []:
        right_bytes = _to_float(j.get("right_size_bytes") or j.get("dim_size_bytes") or j.get("size_bytes"))
        left_bytes = j.get("left_size_bytes") or j.get("left_bytes") or j.get("probe_size_bytes")
        if left_bytes is None:
            left_gb = total_source_gb
            assumptions.append("join left_size_bytes missing; used total source size as probe side")
        else:
            left_gb = _to_float(left_bytes) / BYTES_PER_GB
        right_gb = right_bytes / BYTES_PER_GB
        if right_bytes <= 0:
            continue
        if right_bytes < BROADCAST_AUTO_BYTES:
            continue
        if right_bytes <= BROADCAST_HINT_BYTES:
            shuffle += right_gb
        else:
            shuffle += (left_gb + right_gb) * 3.0
    return shuffle, assumptions


def _merge_shuffle(inputs, total_source_gb):
    strategy = str(inputs.get("load_strategy") or "").strip().lower().replace("-", "_")
    merge = inputs.get("merge") or {}
    is_merge = strategy in {"upsert", "scd2", "delete_insert"} or bool(merge)
    if not is_merge:
        return 0.0, False, []
    assumptions = []
    pruned = bool(merge.get("partition_pruned"))
    matched = merge.get("matched_target_bytes")
    if matched is None:
        if pruned:
            matched_gb = max(total_source_gb * 0.25, 0.01)
            assumptions.append("merge matched_target_bytes missing with partition pruning; assumed 25% of source size")
        else:
            matched_gb = total_source_gb
            assumptions.append("merge partition pruning absent/false; assumed full-target scan with matched target equal to source size")
    else:
        matched_gb = _to_float(matched) / BYTES_PER_GB
    return total_source_gb * 3.0 + matched_gb * 3.0, pruned, assumptions


def _aggregation_shuffle(inputs, total_source_gb):
    shuffle = 0.0
    window_hedge = 0.0
    assumptions = []
    has_window = False
    has_agg = False
    for a in inputs.get("aggregations") or []:
        kind = str(a.get("kind") or a.get("type") or "").strip().lower()
        input_gb = _to_float(a.get("input_size_bytes"), total_source_gb * BYTES_PER_GB) / BYTES_PER_GB
        if kind == "count_distinct" or a.get("count_distinct"):
            has_agg = True
            shuffle += input_gb * 2.0
        elif kind in {"group_by", "aggregate", "aggregation"}:
            has_agg = True
            if a.get("low_cardinality"):
                window_hedge = max(window_hedge, 0.50)
            shuffle += input_gb
        elif kind == "window" or a.get("unbounded_frame"):
            has_window = True
            if a.get("low_cardinality") or a.get("unbounded_frame"):
                window_hedge = max(window_hedge, 0.50)
            shuffle += input_gb
    if window_hedge:
        assumptions.append("low-cardinality aggregation/window or unbounded frame; applied +50% memory hedge")
    return shuffle, window_hedge, assumptions, has_window, has_agg


def _skew_hedge(skew, shuffle_partitions):
    if not skew:
        return False, 0.0
    hot = bool(skew.get("hot_keys") or skew.get("null_heavy"))
    card = skew.get("max_key_cardinality")
    low_card = card is not None and _to_float(card) < 10.0 * max(1, shuffle_partitions)
    if hot or low_card:
        return True, 0.25
    return False, 0.0


def _workload_class(inputs, merge_shuffle, join_shuffle, agg_shuffle, has_window, has_agg):
    strategy = str(inputs.get("load_strategy") or "").strip().lower()
    if strategy == "streaming" or inputs.get("streaming"):
        return "streaming"
    if merge_shuffle > 0:
        return "merge_heavy"
    if has_window:
        return "window_heavy"
    if join_shuffle > 0:
        return "join_heavy"
    if has_agg or agg_shuffle > 0:
        return "agg_heavy"
    return "simple_etl"


def _mem_per_core(workload_class, shuffle_gb):
    if workload_class == "merge_heavy":
        return 8.0
    if workload_class in {"join_heavy", "window_heavy"}:
        return 7.0
    if workload_class == "agg_heavy" or shuffle_gb > 0:
        return 6.0
    return 4.0


def _node_family(workload_class, mem_per_core, single_node):
    if single_node:
        return "general", "source <1 GB and no distributed operators; single-node general-purpose fit"
    if workload_class == "streaming":
        return "compute", "streaming/CPU-oriented workload; compute-optimized family preferred"
    if workload_class in {"merge_heavy", "join_heavy", "window_heavy"} or mem_per_core >= 6:
        return "memory", "shuffle/MERGE/join-heavy workload or >=6 GB/core; memory-optimized family preferred"
    return "general", "balanced simple ETL; general-purpose family preferred"


def _photon(inputs, workload_class, total_source_gb, shuffle_gb):
    if workload_class == "streaming" or inputs.get("udf_heavy") or inputs.get("rdd_heavy"):
        return False, "Photon disabled for streaming/UDF/RDD-heavy workload"
    if workload_class in {"merge_heavy", "join_heavy", "agg_heavy", "window_heavy"}:
        return True, "Photon enabled for SQL/DataFrame joins, aggregations, windows or MERGE"
    if total_source_gb >= 10 or shuffle_gb > 0:
        return True, "Photon enabled for large scan"
    return False, "Photon disabled for tiny/simple ETL"


def _autoscale(schedule, expected_runtime_h, single_node, workload_class, shuffle_partitions):
    if single_node:
        return False, "single-node workload; autoscale not applicable"
    sla_h = schedule.get("sla_hours") or schedule.get("sla_h")
    if sla_h is not None and _to_float(sla_h) < 2:
        return False, "SLA under 2 hours; fixed on-demand workers preferred"
    variable = workload_class in {"merge_heavy", "join_heavy", "agg_heavy", "window_heavy"} or shuffle_partitions > 0
    if expected_runtime_h > 0.5 and variable:
        return True, "projected runtime exceeds ~30 minutes with variable distributed stages"
    return False, "projected runtime is short or stage parallelism is stable; fixed workers preferred"


def _build_tiers(catalog, family, single_node, min_cores, mem_per_core, workload_class,
                 criticality, photon, autoscale):
    if single_node:
        node = _pick_node(catalog, family, 1, 1, 0)
        return [
            _tier("lean", node, 0, False, False, photon=False),
            _tier("recommended", node, 0, False, False, photon=photon),
            _tier("conservative", _next_larger(catalog, node, family), 0, False, False, photon=photon),
        ]

    target = _target_cores(min_cores, workload_class)
    desired_worker_vcpu = _desired_worker_vcpu(target, workload_class)
    base = _pick_node(catalog, family, desired_worker_vcpu, mem_per_core, 0)
    lean_node = _prev_smaller(catalog, base, family) or base
    cons_node = _next_larger(catalog, base, family)

    rec_workers = _clamp_workers(int(math.ceil(target / max(1, base["vcpu"]))))
    lean_workers = max(1, _clamp_workers(int(math.ceil(rec_workers * 0.7))))
    cons_workers = _clamp_workers(int(math.ceil(rec_workers * 1.35)))
    if workload_class in {"merge_heavy", "join_heavy", "window_heavy"}:
        rec_workers = max(2, rec_workers)
        lean_workers = max(2, lean_workers)
        cons_workers = max(3, cons_workers)

    lean_spot = criticality in {"low", "medium", "unknown"}
    rec_spot = criticality in {"low", "medium"}
    cons_spot = False

    return [
        _tier("lean", lean_node, lean_workers, autoscale, lean_spot, photon=photon),
        _tier("recommended", base, rec_workers, autoscale, rec_spot, photon=photon),
        _tier("conservative", cons_node, cons_workers, autoscale, cons_spot, photon=photon),
    ]


def _tier(name, node, workers, autoscale_enabled, spot, photon):
    autoscale = None
    if autoscale_enabled and workers > 0:
        autoscale = {"min_workers": max(1, int(math.floor(workers * 0.5))),
                     "max_workers": max(1, workers)}
    return {
        "tier": name,
        "node_type_id": node["node_type"],
        "workers": workers,
        "autoscale": autoscale,
        "spot_workers": bool(spot),
        "photon": bool(photon),
    }


def _target_cores(min_cores, workload_class):
    if min_cores <= 64:
        return max(4, min_cores)
    mult = 5.0 if workload_class in {"merge_heavy", "join_heavy", "window_heavy"} else 4.0
    return int(math.ceil(math.sqrt(min_cores) * mult))


def _desired_worker_vcpu(target_cores, workload_class):
    if workload_class in {"merge_heavy", "join_heavy", "window_heavy"}:
        if target_cores >= 640:
            return 64
        if target_cores >= 256:
            return 32
        return 16
    if target_cores >= 512:
        return 32
    if target_cores >= 128:
        return 16
    return 8


def _pick_node(catalog, family, min_vcpu, mem_per_core, extra_ram):
    pool = [n for n in catalog if n["family"] == family] or list(catalog)
    cands = [n for n in pool if n["vcpu"] >= min_vcpu and
             (n["ram_gb"] / max(1, n["vcpu"])) >= mem_per_core * 0.9 and
             n["ram_gb"] >= extra_ram]
    if not cands:
        cands = [n for n in pool if n["vcpu"] >= min_vcpu]
    if not cands:
        cands = pool
    return min(cands, key=lambda n: (n["rel_dbu"] / max(1, n["vcpu"]), n["rel_dbu"], n["ram_gb"]))


def _next_larger(catalog, node, family):
    pool = sorted([n for n in catalog if n["family"] == family], key=lambda n: (n["vcpu"], n["ram_gb"], n["rel_dbu"]))
    for n in pool:
        if n["vcpu"] > node["vcpu"] or n["ram_gb"] > node["ram_gb"]:
            return n
    return node


def _prev_smaller(catalog, node, family):
    pool = sorted([n for n in catalog if n["family"] == family], key=lambda n: (n["vcpu"], n["ram_gb"], n["rel_dbu"]))
    prev = None
    for n in pool:
        if n["node_type"] == node["node_type"]:
            return prev
        prev = n
    return prev


def _runtime_hours(source_gb, workload_class, merge_pruned, cores, photon, photon_mult):
    key = workload_class
    if workload_class == "merge_heavy":
        key = "merge_pruned" if merge_pruned else "merge_unpruned"
    lo_tp, hi_tp = THROUGHPUT.get(key, THROUGHPUT["simple_etl"])
    expected_tp = (lo_tp + hi_tp) / 2.0
    speed = photon_mult if photon else 1.0
    cores = max(1.0, float(cores))

    def rt(tp):
        return max(0.01, source_gb / tp * (100.0 / cores) / speed)

    low = rt(hi_tp)
    expected = rt(expected_tp)
    high = rt(lo_tp)
    return {"low": _hours(low), "expected": _hours(expected), "high": _hours(high)}


def _cost_band(runtime, worker, driver, workers, pricing, analog, source_gb, load_strategy, assumptions):
    jobs_price = _to_float(pricing.get("jobs_dbu_usd"), 0.30)
    hourly_dbu = (max(0, workers) * worker["rel_dbu"] + driver["rel_dbu"])
    per_run = {
        "low": _money(hourly_dbu * runtime["low"] * jobs_price),
        "expected": _money(hourly_dbu * runtime["expected"] * jobs_price),
        "high": _money(hourly_dbu * runtime["high"] * jobs_price),
    }
    confidence = "low"
    analog_job_id = None
    if analog:
        analog_job_id = analog.get("job_id") or analog.get("analog_job_id")
        adbuh = _to_float(analog.get("dbus_per_hour"))
        art = _to_float(analog.get("runtime_hours"))
        asize_gb = _to_float(analog.get("size_bytes")) / BYTES_PER_GB
        if adbuh > 0 and art > 0 and asize_gb > 0:
            ratio = max(0.1, source_gb / asize_gb)
            analog_expected = adbuh * art * ratio * jobs_price
            envelope = (_money(analog_expected * 0.6), _money(analog_expected * 1.6))
            per_run["expected"] = _money(min(max(per_run["expected"], envelope[0]), envelope[1]))
            per_run["low"] = _money(min(per_run["low"], envelope[0], per_run["expected"]))
            per_run["high"] = _money(max(per_run["high"], envelope[1], per_run["expected"]))
            same_load = str(analog.get("load_strategy") or load_strategy or "").lower() == str(load_strategy or "").lower()
            confidence = "high" if 0.5 <= ratio <= 2.0 and same_load else "medium"
        else:
            assumptions.append("analog supplied without dbus_per_hour/runtime_hours/size_bytes; ignored for cost clamp")
    return {"per_run_usd": per_run, "analog_job_id": analog_job_id, "confidence": confidence}


def _tier_cores(worker, workers, single_node):
    if single_node:
        return max(1, worker["vcpu"])
    return max(1, worker["vcpu"] * max(1, workers))


def _workers_desc(workers, autoscale, single_node):
    if single_node:
        return "single-node (num_workers=0)"
    if autoscale:
        return f"autoscale {autoscale['min_workers']}-{autoscale['max_workers']} workers"
    return f"{workers} workers"


def _abstain_result(reasons, assumptions):
    return {
        "abstained": True,
        "abstain_reasons": reasons,
        "workload_class": None,
        "recommended_cluster": None,
        "recommended_tier": None,
        "options": [],
        "rationale": {
            "est_source_gb": 0,
            "est_shuffle_gb": 0,
            "read_partitions": 0,
            "shuffle_partitions": 0,
            "min_cores": 0,
            "mem_gb": 0,
            "skew_hedge": False,
            "photon_reason": "abstained; no positive source size",
            "autoscale_reason": "abstained; no cluster guessed",
            "node_family_reason": "abstained; no cluster guessed",
        },
        "cost_projection": {
            "per_run_usd": {"low": 0, "expected": 0, "high": 0},
            "monthly_usd": {"low": 0, "expected": 0, "high": 0},
            "runs_per_month": 0,
            "analog_job_id": None,
            "confidence": "low",
        },
        "assumptions": _dedupe(assumptions),
        "citations": CITATIONS[:],
        "generated_by": GENERATED_BY,
    }


def _apply_block(rec):
    """Build the human-gated job-cluster proposal from a recommended cluster.

    Emits only legal job-cluster fields (node types, autoscale/num_workers,
    runtime_engine, data_security_mode, spot policy). Never emits
    spark.executor.* / spark.dynamicAllocation.* — those are deliberately
    omitted so the platform/AQE manages them.
    """
    new_cluster = {
        "spark_version": rec["spark_version"],
        "node_type_id": rec["node_type_id"],
        "driver_node_type_id": rec["driver_node_type_id"],
    }
    if rec.get("num_workers") is not None:
        new_cluster["num_workers"] = rec["num_workers"]
    if rec.get("autoscale"):
        new_cluster["autoscale"] = rec["autoscale"]
    new_cluster["runtime_engine"] = "PHOTON" if rec.get("photon") else "STANDARD"
    new_cluster["data_security_mode"] = rec["data_security_mode"]
    # Driver is always on-demand; only workers may use spot.
    new_cluster["azure_attributes"] = {
        "availability": "SPOT_WITH_FALLBACK_AZURE" if rec.get("spot_workers") else "ON_DEMAND_AZURE"
    }
    return {"job_cluster": {"job_cluster_key": "<use_case>-forecast", "new_cluster": new_cluster}}


def render_markdown(result):
    lines = ["# Cluster sizing forecast", ""]
    if result["abstained"]:
        lines += ["**Verdict:** ABSTAIN", "", "## Reasons"]
        lines += [f"- {r}" for r in result["abstain_reasons"]]
        return "\n".join(lines)

    rec = result["recommended_cluster"]
    lines += [
        f"**Workload class:** `{result['workload_class']}`  |  **Recommended tier:** `{result['recommended_tier']}`",
        "",
        "## Recommended cluster",
        "```json",
        json.dumps(rec, indent=2),
        "```",
        "",
        "## Options",
        "| Tier | Node | Workers | Spot | Photon | Runtime h (low-high) | Cost/run (low/expected/high) |",
        "|---|---|---|---|---|---|---|",
    ]
    for o in result["options"]:
        c = o["cost"]["per_run_usd"]
        rt = o["est_runtime_hours"]
        star = " ★" if o["tier"] == result["recommended_tier"] else ""
        lines.append(f"| {o['tier']}{star} | `{o['node_type_id']}` | {o['num_workers_or_autoscale']} | "
                     f"{o['spot_workers']} | {o['photon']} | {rt['low']}–{rt['high']} | "
                     f"${c['low']} / ${c['expected']} / ${c['high']} |")
    cp = result["cost_projection"]
    lines += [
        "",
        "## Rationale",
        f"- Source/shuffle: {result['rationale']['est_source_gb']} GB / {result['rationale']['est_shuffle_gb']} GB",
        f"- Partitions: read {result['rationale']['read_partitions']}, shuffle {result['rationale']['shuffle_partitions']}",
        f"- Minimum cores / memory: {result['rationale']['min_cores']} cores / {result['rationale']['mem_gb']} GB",
        f"- {result['rationale']['node_family_reason']}",
        f"- {result['rationale']['photon_reason']}",
        f"- {result['rationale']['autoscale_reason']}",
        "",
        "## Cost projection",
        f"- Per run: ${cp['per_run_usd']['low']} / ${cp['per_run_usd']['expected']} / ${cp['per_run_usd']['high']}",
        f"- Monthly ({cp['runs_per_month']} runs): ${cp['monthly_usd']['low']} / ${cp['monthly_usd']['expected']} / ${cp['monthly_usd']['high']}",
        f"- Confidence: {cp['confidence']} | Analog: {cp['analog_job_id']}",
    ]
    if result["assumptions"]:
        lines += ["", "## Assumptions"] + [f"- {a}" for a in result["assumptions"]]
    lines += ["", "## Citations"] + [f"- {c}" for c in result["citations"]]
    lines += [
        "",
        "## Apply Block (PROPOSAL — human-gated; UI / Jobs REST API only — MCP is read-only)",
        "",
        "This proposal is **not auto-applied**. Review and apply via the Databricks UI "
        "or Jobs REST API only; the Databricks SQL MCP server is read-only and cannot "
        "mutate compute.",
        "",
        "```json",
        json.dumps(_apply_block(rec), indent=2),
        "```",
    ]
    return "\n".join(lines)


def _read_payload(src):
    if src == "-":
        text = sys.stdin.read()
    else:
        with open(src, encoding="utf-8") as fh:
            text = fh.read()
    if not text.strip():
        raise ValueError("empty payload (expected JSON with an 'inputs' object)")
    return json.loads(text)


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Forecast a Databricks job cluster from a JSON design-time payload. "
                    "This script performs no Databricks access.")
    p.add_argument("--from-json", required=True, metavar="PATH",
                   help="Path to payload JSON, or '-' for stdin.")
    p.add_argument("--catalog", default=str(DEFAULT_CATALOG), help="Path to node_catalog.csv")
    p.add_argument("--json", action="store_true", help="Emit raw JSON instead of Markdown")
    args = p.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    try:
        payload = _read_payload(args.from_json)
    except (OSError, ValueError) as e:
        print(f"Error: could not read --from-json payload: {e}", file=sys.stderr)
        return 2

    inputs = payload.get("inputs") if isinstance(payload, dict) else None
    if inputs is None and isinstance(payload, dict) and ("sources" in payload or "load_strategy" in payload):
        inputs = payload
    if not isinstance(inputs, dict):
        print("Error: payload must be a JSON object with an 'inputs' object.", file=sys.stderr)
        return 2

    catalog = load_catalog(args.catalog)
    result = forecast(inputs, catalog)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(render_markdown(result))
    return 0


def _ceil_partition_gb(gb):
    if gb <= 0:
        return 0
    return int(math.ceil(gb * 1024.0 / PARTITION_MB))


def _to_float(value, default=0.0):
    try:
        if value is None:
            return None if default is None else float(default)
        return float(value)
    except (TypeError, ValueError):
        return None if default is None else float(default)


def _criticality(value):
    if value is None:
        return "unknown"
    v = str(value).strip().lower()
    if v in CRIT_HIGH:
        return "high"
    if v in CRIT_MED:
        return "medium"
    if v in CRIT_LOW:
        return "low"
    return "unknown"


def _clamp_workers(n):
    return max(1, min(64, n))


def _hours(v):
    return round(float(v), 2)


def _money(v):
    return round(float(v), 2)


def _num(v):
    v = float(v)
    if abs(v - round(v)) < 0.005:
        return int(round(v))
    return round(v, 2)


def _dedupe(items):
    out = []
    for item in items:
        if item and item not in out:
            out.append(item)
    return out


if __name__ == "__main__":
    raise SystemExit(main())
