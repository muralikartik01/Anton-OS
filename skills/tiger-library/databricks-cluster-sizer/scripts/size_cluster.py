#!/usr/bin/env python3
"""
size_cluster.py — offline Databricks cluster right-sizer (the scoring brain).

This script performs NO Databricks access. All telemetry is gathered by the
agent through the Databricks SQL MCP server (`.../api/2.0/mcp/sql`) by running
the queries in ../references/queries.sql, then handed to this script as a single
JSON payload. The script turns that payload into a deterministic sizing verdict
plus a Markdown/JSON report. No Databricks CLI is used anywhere.

The sizing logic lives in `recommend()`, a PURE function with no I/O so it can
be unit-tested offline (see ../evals/).

Input payload (a file path, or '-' for stdin):
  {
    "config":  { cluster_id, cluster_name, driver_node_type, worker_node_type,
                 worker_count, min_autoscale_workers, max_autoscale_workers,
                 auto_termination_minutes, cluster_source },
    "profile": { source, observed_peak_workers,
                 worker: { sample_minutes, cpu_p50, cpu_p95, cpu_max,
                           mem_p95, mem_max, swap_max },
                 driver: { ...same keys... } | null,

                 # --- optional cadence/criticality/trend context (JOB runs) ---
                 job: { job_id, job_name,
                        cadence: { trigger_type, cron, runs_per_week,
                                   median_gap_hours, gap_stddev_hours } | null,
                        criticality: { tier, source } | null,
                        tags: { criticality|tier|sla|env: ... } | null,
                        health_rules: [...] | null },
                 trend: { n_runs, success_rate, runtime_seconds_p50,
                          runtime_seconds_p90, runtime_seconds_stddev,
                          cost_usd_p50, cost_usd_p90,
                          runtime_recency_corr } | null,
                 workload: { workload_type, cores_per_worker, shuffle_partitions,
                             photon_enabled, is_serverless } | null,
                 pricing: { baseline_cost_usd, baseline_runtime_seconds,
                            dbu_price_usd } | null }
  }
The base payload shape matches the fixtures in ../evals/fixtures/. The job/trend/
workload/pricing blocks are OPTIONAL: when absent the tool still produces three
tiers (defaulting to Balanced) but cost is relative-only and runtime projection
is omitted. When present it becomes cadence-aware, picks a recommended tier, and
projects absolute cost + runtime ranges across the trend window.

Usage:
  # From a file the agent assembled out of the MCP query results:
  python size_cluster.py --from-json payload.json

  # Or piped on stdin:
  cat payload.json | python size_cluster.py --from-json -

Prerequisites: see ../SKILL.md.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys

# ---------------------------------------------------------------------------
# Tunable thresholds (percent of node capacity). Documented in SKILL.md so the
# behaviour is transparent and easy to adjust per fleet.
# ---------------------------------------------------------------------------
MIN_SAMPLES = 10        # below this we abstain: too little signal to trust
MEM_HIGH = 85.0         # mem_p95 at/above this => memory pressure
CPU_HIGH = 80.0         # cpu_p95 at/above this => CPU bound
MEM_OK_FOR_CPU = 70.0   # CPU-bound only counts if memory has headroom
CPU_LOW = 40.0          # below this (with low mem) => over-provisioned
MEM_LOW = 50.0
DRIVER_MEM_HIGH = 85.0  # driver collecting too much to itself

TARGET_MEM = 70.0       # post-change headroom we size toward
TARGET_CPU = 65.0
SWAP_RAM_MULTIPLIER = 1.5   # any swap => give at least 1.5x current RAM
AUTOSCALE_BUMP = 1.5        # autoscale-capped => raise max by this factor

# ---------------------------------------------------------------------------
# Cadence / criticality / projection tunables. These power the three trade-off
# tiers and the cost+runtime projections. Every multiplier below is a
# documented RANGE so projections are honest about uncertainty rather than
# implying false precision. Sources are cited in ../README.md and
# ../research/databricks-rightsizing-bestpractices.md.
# ---------------------------------------------------------------------------
# Empirical-cadence buckets, keyed off runs-per-week (90-day window).
CADENCE_HOURLY_RPW = 35.0   # >= ~5 runs/day -> hourly_or_more (pipeline/SLA-like)
CADENCE_DAILY_RPW = 5.0     # ~daily .. several/day
CADENCE_WEEKLY_RPW = 0.0    # anything positive below daily -> weekly_or_less

# Amdahl's-Law parallel fraction by workload (low, high) -> runtime range.
PARALLEL_FRACTION = {
    "sql_heavy": (0.78, 0.95),
    "simple_etl": (0.70, 0.90),
    "streaming": (0.50, 0.80),
    "ml": (0.40, 0.70),
    None: (0.65, 0.90),
}
SPILL_SPEEDUP = (0.60, 0.85)        # runtime factor when a memory upsize ends spill
PHOTON_RUNTIME = {                  # runtime factor when Photon is enabled
    "sql_heavy": (0.30, 0.60),
    "simple_etl": (0.40, 0.75),
}
PHOTON_DBU_UPLIFT = (1.20, 2.00)    # Photon raises the DBU rate while cutting runtime
SPOT_BLENDED_SAVING = (0.15, 0.40)  # blended total-cost saving from spot workers
WEEKS_PER_YEAR = 52.0
TIER_ORDER = ["cost", "balanced", "performance"]

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CATALOG = os.path.join(REPO_ROOT, "references", "node_catalog.csv")


# ---------------------------------------------------------------------------
# Node catalog
# ---------------------------------------------------------------------------
def load_catalog(path=DEFAULT_CATALOG):
    """Load the node catalog CSV into a list of dicts (typed)."""
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


def node_by_type(catalog, node_type):
    for n in catalog:
        if n["node_type"] == node_type:
            return n
    return None


def pick_node(catalog, required_ram, required_vcpu, prefer_family=None):
    """Smallest node (by rel_dbu) meeting both RAM and vCPU requirements.

    Selection is capacity- and price-based, never index/level math, so the
    catalog only needs to be self-consistent (more spec => higher rel_dbu),
    not perfectly ordered.
    """
    def candidates(pool):
        return [n for n in pool if n["ram_gb"] >= required_ram and n["vcpu"] >= required_vcpu]

    pool = catalog
    if prefer_family:
        fam = candidates([n for n in catalog if n["family"] == prefer_family])
        if fam:
            pool = [n for n in catalog if n["family"] == prefer_family]
    cands = candidates(pool)
    if not cands:
        # Requirement exceeds the catalog: return the biggest node we have.
        return max(catalog, key=lambda n: (n["rel_dbu"], n["ram_gb"]))
    return min(cands, key=lambda n: (n["rel_dbu"], n["ram_gb"], n["vcpu"]))


# ---------------------------------------------------------------------------
# The brain: PURE sizing decision (no I/O)
# ---------------------------------------------------------------------------
def _effective_workers(config, profile):
    if config.get("worker_count"):
        return int(config["worker_count"])
    if config.get("max_autoscale_workers"):
        return int(config["max_autoscale_workers"])
    if profile.get("observed_peak_workers"):
        return int(profile["observed_peak_workers"])
    return 1


def recommend(profile, config, catalog):
    """Map a utilization profile + current config to a sizing recommendation.

    profile: {
      "worker": {sample_minutes, cpu_p50, cpu_p95, cpu_max, mem_p95, mem_max, swap_max},
      "driver": {... same keys ...} | None,
      "observed_peak_workers": int | None,
      "source": "system_tables" | "events",
    }
    config: {cluster_id, cluster_name, driver_node_type, worker_node_type,
             worker_count, min_autoscale_workers, max_autoscale_workers,
             auto_termination_minutes, cluster_source}
    Returns a dict the renderer turns into Markdown.
    """
    worker = profile.get("worker") or {}
    driver = profile.get("driver")
    source = profile.get("source", "system_tables")

    cur_worker = node_by_type(catalog, config.get("worker_node_type"))
    result = {
        "cluster_id": config.get("cluster_id"),
        "cluster_name": config.get("cluster_name"),
        "source": source,
        "classification": None,
        "direction": "keep",
        "confidence": "high",
        "current_worker_node_type": config.get("worker_node_type"),
        "current_driver_node_type": config.get("driver_node_type"),
        "recommended_worker_node_type": config.get("worker_node_type"),
        "recommended_driver_node_type": config.get("driver_node_type"),
        "recommended_max_autoscale_workers": config.get("max_autoscale_workers"),
        "est_dbu_delta_pct": 0.0,
        "rationale": "",
        # Cadence/criticality/trend-aware extensions (populated for sized runs).
        "cadence": None,
        "criticality": None,
        "trend": None,
        "options": [],
        "recommended_tier": None,
        "caveats": [],
        "evidence": {"worker": worker, "driver": driver,
                     "observed_peak_workers": profile.get("observed_peak_workers")},
    }

    # Guard: we must know the current node's specs to size anything.
    if cur_worker is None:
        result["classification"] = "unknown_node"
        result["direction"] = "abstain"
        result["confidence"] = "low"
        result["rationale"] = (
            f"Worker node type '{config.get('worker_node_type')}' is not in the "
            f"node catalog, so its vCPU/RAM are unknown. Add it to "
            f"references/node_catalog.csv and re-run.")
        return result

    samples = float(worker.get("sample_minutes") or 0)

    # 1) Insufficient data -> abstain. Never downsize on thin evidence.
    if samples < MIN_SAMPLES:
        result["classification"] = "insufficient_data"
        result["direction"] = "abstain"
        result["confidence"] = "low"
        result["rationale"] = (
            f"Only {int(samples)} minute-samples in the window (need "
            f">= {MIN_SAMPLES}). Not enough signal to recommend a change; "
            f"re-run over a longer or busier window.")
        return result

    cpu_p95 = float(worker.get("cpu_p95") or 0)
    mem_p95 = float(worker.get("mem_p95") or 0)
    swap_max = float(worker.get("swap_max") or 0)
    drv_mem_p95 = float(driver.get("mem_p95")) if driver else 0.0

    # Classify (first match wins). Workers do the heavy lifting, so worker
    # memory pressure outranks a busy driver.
    if mem_p95 >= MEM_HIGH or swap_max > 0:
        classification = "memory_bound"
    elif driver and drv_mem_p95 >= DRIVER_MEM_HIGH:
        classification = "driver_bound"
    elif cpu_p95 >= CPU_HIGH and mem_p95 < MEM_OK_FOR_CPU:
        classification = "cpu_bound"
    elif cpu_p95 < CPU_LOW and mem_p95 < MEM_LOW and swap_max == 0:
        classification = "over_provisioned"
    else:
        classification = "balanced"
    result["classification"] = classification

    # Required per-node capacity to land at our headroom targets.
    req_ram = cur_worker["ram_gb"] * (mem_p95 / TARGET_MEM) if mem_p95 else cur_worker["ram_gb"]
    req_vcpu = cur_worker["vcpu"] * (cpu_p95 / TARGET_CPU) if cpu_p95 else cur_worker["vcpu"]

    if classification == "memory_bound":
        req_ram = max(req_ram, cur_worker["ram_gb"] * SWAP_RAM_MULTIPLIER) if swap_max > 0 else req_ram
        rec = pick_node(catalog, req_ram, max(req_vcpu, cur_worker["vcpu"] * 0.5), prefer_family="memory")
        rec = _clamp_not_smaller(rec, cur_worker, catalog)
        result["direction"] = "up" if rec["rel_dbu"] > cur_worker["rel_dbu"] else "keep"
        result["recommended_worker_node_type"] = rec["node_type"]
        reason = f"swap detected (swap_max={swap_max}%)" if swap_max > 0 else f"mem p95 {mem_p95}% >= {MEM_HIGH}%"
        result["rationale"] = (
            f"Workers are memory-bound ({reason}). Move to {rec['node_type']} "
            f"({rec['ram_gb']:.0f} GB/node) to bring memory back under "
            f"{TARGET_MEM:.0f}% and stop spill.")

    elif classification == "driver_bound":
        cur_driver = node_by_type(catalog, config.get("driver_node_type")) or cur_worker
        d_req_ram = cur_driver["ram_gb"] * max(drv_mem_p95 / TARGET_MEM, SWAP_RAM_MULTIPLIER)
        rec_d = pick_node(catalog, d_req_ram, cur_driver["vcpu"], prefer_family="memory")
        rec_d = _clamp_not_smaller(rec_d, cur_driver, catalog)
        result["direction"] = "up" if rec_d["rel_dbu"] > cur_driver["rel_dbu"] else "keep"
        result["recommended_driver_node_type"] = rec_d["node_type"]
        result["rationale"] = (
            f"The driver is the bottleneck (driver mem p95 {drv_mem_p95}% >= "
            f"{DRIVER_MEM_HIGH}%) while workers have headroom. Upsize the driver "
            f"only to {rec_d['node_type']} ({rec_d['ram_gb']:.0f} GB); likely a "
            f"large collect()/toPandas() or broadcast. Workers unchanged.")

    elif classification == "cpu_bound":
        capped = _is_autoscale_capped(config, profile)
        if capped:
            new_max = int(math.ceil(int(config["max_autoscale_workers"]) * AUTOSCALE_BUMP))
            result["direction"] = "up"
            result["recommended_max_autoscale_workers"] = new_max
            result["classification"] = "autoscale_capped"
            result["rationale"] = (
                f"CPU-bound and pinned at the autoscale ceiling "
                f"({config['max_autoscale_workers']} workers, cpu p95 {cpu_p95}%). "
                f"Raise max workers to {new_max} so the job can scale out; node "
                f"type is already appropriate.")
        else:
            rec = pick_node(catalog, req_ram, req_vcpu, prefer_family=cur_worker["family"])
            rec = _clamp_not_smaller(rec, cur_worker, catalog)
            result["direction"] = "up" if rec["rel_dbu"] > cur_worker["rel_dbu"] else "keep"
            result["recommended_worker_node_type"] = rec["node_type"]
            result["rationale"] = (
                f"Workers are CPU-bound (cpu p95 {cpu_p95}% >= {CPU_HIGH}%, memory "
                f"fine at {mem_p95}%). Move to {rec['node_type']} "
                f"({rec['vcpu']} vCPU/node) or add workers to clear the queue.")

    elif classification == "over_provisioned":
        rec = pick_node(catalog, req_ram, req_vcpu, prefer_family=cur_worker["family"])
        # Only act if it actually saves; otherwise keep.
        if rec["rel_dbu"] < cur_worker["rel_dbu"]:
            result["direction"] = "down"
            result["recommended_worker_node_type"] = rec["node_type"]
            result["rationale"] = (
                f"Workers are over-provisioned (cpu p95 {cpu_p95}% < {CPU_LOW}%, "
                f"mem p95 {mem_p95}% < {MEM_LOW}%, no swap). Downsize to "
                f"{rec['node_type']} ({rec['vcpu']} vCPU / {rec['ram_gb']:.0f} GB) "
                f"and still keep comfortable headroom.")
        else:
            result["direction"] = "keep"
            result["classification"] = "balanced"
            result["rationale"] = (
                "Utilization is low but you are already on the smallest sensible "
                "node; consider trimming worker count or auto-termination instead.")

    else:  # balanced
        result["direction"] = "keep"
        result["rationale"] = (
            f"Utilization is balanced (cpu p95 {cpu_p95}%, mem p95 {mem_p95}%). "
            f"Current size is a good fit; no node change recommended.")

    # Confidence: events fallback is coarser; flag it.
    if source == "events":
        result["confidence"] = "medium"

    result["est_dbu_delta_pct"] = _dbu_delta_pct(result, config, profile, catalog)
    # Upgrade the single verdict into three cadence-aware trade-off tiers with
    # cost + runtime projections, and pick the recommended default. This keeps
    # the legacy top-level keys (set above) as the Balanced/base recommendation
    # unless a cadence/criticality signal selects a different default tier.
    _augment_with_tiers(result, profile, config, catalog)
    return result


def _clamp_not_smaller(rec, current, catalog):
    """For up/keep classifications, never return a node smaller than current."""
    if rec["rel_dbu"] < current["rel_dbu"]:
        return current
    return rec


def _is_autoscale_capped(config, profile):
    peak = profile.get("observed_peak_workers")
    mx = config.get("max_autoscale_workers")
    return bool(mx) and peak is not None and int(peak) >= int(mx)


def _dbu_delta_pct(result, config, profile, catalog):
    cur_w = node_by_type(catalog, result["current_worker_node_type"])
    rec_w = node_by_type(catalog, result["recommended_worker_node_type"])
    cur_d = node_by_type(catalog, result["current_driver_node_type"])
    rec_d = node_by_type(catalog, result["recommended_driver_node_type"])
    if not (cur_w and rec_w and cur_d and rec_d):
        return 0.0
    n = _effective_workers(config, profile)
    cur_total = cur_w["rel_dbu"] * n + cur_d["rel_dbu"]
    rec_total = rec_w["rel_dbu"] * n + rec_d["rel_dbu"]
    if cur_total == 0:
        return 0.0
    return round((rec_total - cur_total) / cur_total * 100.0, 1)


def _rel_dbu_delta(cur_w, rec_w, cur_d, rec_d, n):
    """Relative DBU change (%) for an explicit node selection. Same model as
    _dbu_delta_pct but parameterized so each tier can be priced independently."""
    if not (cur_w and rec_w and cur_d and rec_d):
        return 0.0
    cur_total = cur_w["rel_dbu"] * n + cur_d["rel_dbu"]
    rec_total = rec_w["rel_dbu"] * n + rec_d["rel_dbu"]
    if cur_total == 0:
        return 0.0
    return round((rec_total - cur_total) / cur_total * 100.0, 1)


# ---------------------------------------------------------------------------
# Cadence + criticality derivation
# ---------------------------------------------------------------------------
def _derive_cadence(job):
    """Bucket a job's cadence from its schedule or empirical run history.

    Returns {bucket, runs_per_week, source, descriptor}. bucket is one of
    hourly_or_more / daily / weekly_or_less / irregular / unknown.
    """
    cad = (job or {}).get("cadence") or {}
    rpw = cad.get("runs_per_week")
    trigger = (cad.get("trigger_type") or "").upper()
    gap_std = cad.get("gap_stddev_hours")
    median_gap = cad.get("median_gap_hours")

    if trigger == "CONTINUOUS":
        return {"bucket": "hourly_or_more", "runs_per_week": rpw,
                "source": "schedule",
                "descriptor": "continuous / streaming trigger"}

    if rpw is not None:
        rpw = float(rpw)
        # Irregular if the spread between runs dwarfs the typical gap.
        if gap_std is not None and median_gap and median_gap > 0 \
                and float(gap_std) > 2.0 * float(median_gap):
            bucket = "irregular"
        elif rpw >= CADENCE_HOURLY_RPW:
            bucket = "hourly_or_more"
        elif rpw >= CADENCE_DAILY_RPW:
            bucket = "daily"
        elif rpw > CADENCE_WEEKLY_RPW:
            bucket = "weekly_or_less"
        else:
            bucket = "weekly_or_less"
        return {"bucket": bucket, "runs_per_week": round(rpw, 2),
                "source": "empirical",
                "descriptor": f"~{round(rpw, 1)} runs/week (90-day history)"}

    if cad.get("cron"):
        # Light heuristic: a day-of-week-restricted cron usually means weekly.
        cron = cad["cron"]
        fields = cron.split()
        dow = fields[5] if len(fields) >= 6 else "?"
        if dow not in ("?", "*"):
            return {"bucket": "weekly_or_less", "runs_per_week": None,
                    "source": "schedule", "descriptor": f"cron `{cron}` (day-of-week pinned)"}
        return {"bucket": "daily", "runs_per_week": None,
                "source": "schedule", "descriptor": f"cron `{cron}`"}

    return {"bucket": "unknown", "runs_per_week": None, "source": "unknown",
            "descriptor": "no schedule or run-history signal"}


_CRIT_HIGH = {"high", "critical", "p0", "p1", "tier-1", "tier1", "t1", "gold"}
_CRIT_MED = {"medium", "med", "p2", "tier-2", "tier2", "t2", "silver"}
_CRIT_LOW = {"low", "p3", "p4", "tier-3", "tier3", "t3", "bronze", "dev", "test", "sandbox"}


def _normalize_crit_tier(value):
    """Map a raw criticality string (tag value or explicit input) to one of
    high/medium/low via the shared vocab. Returns 'unknown' if unrecognized.
    This MUST gate every path that feeds spot/tier decisions so a synonym like
    'critical'/'p1'/'gold' is never treated as non-critical."""
    if value is None:
        return "unknown"
    v = str(value).strip().lower()
    if v in _CRIT_HIGH:
        return "high"
    if v in _CRIT_MED:
        return "medium"
    if v in _CRIT_LOW:
        return "low"
    return "unknown"


def _derive_criticality(job, cadence_bucket):
    """Resolve criticality from explicit input, job tags / SLA signals, else
    cadence. Returns {tier, source}; tier in high/medium/low/unknown."""
    job = job or {}
    explicit = job.get("criticality") or {}
    if explicit.get("tier"):
        # Normalize through the shared vocab so 'critical'/'p1'/'gold'/etc.
        # collapse to high — otherwise a raw value would defeat the spot and
        # default-tier guardrails (which branch on the literal 'high').
        norm = _normalize_crit_tier(explicit["tier"])
        return {"tier": norm if norm != "unknown" else str(explicit["tier"]).strip().lower(),
                "source": explicit.get("source") or "user"}

    tags = job.get("tags") or {}
    for key in ("criticality", "tier", "priority", "sla_tier"):
        if tags.get(key) is None:
            continue
        norm = _normalize_crit_tier(tags.get(key))
        if norm != "unknown":
            return {"tier": norm, "source": "tags"}

    # An explicit SLA tag or health rules imply this job is watched -> high.
    if tags.get("sla") or job.get("health_rules"):
        return {"tier": "high", "source": "health_rules" if job.get("health_rules") else "tags"}

    env = str(tags.get("env") or "").strip().lower()
    if env in ("dev", "test", "sandbox", "qa"):
        return {"tier": "low", "source": "tags"}

    bucket_to_tier = {
        "hourly_or_more": "high",
        "daily": "medium",
        "weekly_or_less": "low",
        "irregular": "low",
    }
    if cadence_bucket in bucket_to_tier:
        return {"tier": bucket_to_tier[cadence_bucket], "source": "cadence"}
    return {"tier": "unknown", "source": "unknown"}


def _summarize_trend(trend_in):
    """Normalize the multi-run trend block and attach a human note."""
    if not trend_in:
        return None
    t = dict(trend_in)
    n = t.get("n_runs")
    corr = t.get("runtime_recency_corr")
    p50 = t.get("runtime_seconds_p50")
    std = t.get("runtime_seconds_stddev")
    success = t.get("success_rate")

    notes = []
    if corr is not None:
        c = float(corr)
        if c >= 0.4:
            notes.append("runtime trending UP across recent runs (slowing)")
        elif c <= -0.4:
            notes.append("runtime trending DOWN across recent runs (speeding up)")
        else:
            notes.append("runtime roughly stable across runs")
    if std is not None and p50:
        cv = float(std) / float(p50) if float(p50) else 0.0
        if cv >= 0.3:
            notes.append(f"high run-to-run variance (CV~{cv:.0%})")
    if success is not None and float(success) < 1.0:
        notes.append(f"success rate {float(success):.0%} (reliability risk)")
    if n is not None and int(n) < 5:
        notes.append(f"only {int(n)} runs in window — trend is weak")

    t["note"] = "; ".join(notes) if notes else "stable history"
    return t


# ---------------------------------------------------------------------------
# Projection engine (runtime + cost), all as ranges
# ---------------------------------------------------------------------------
def _project_runtime_range(cur_w, new_w, cur_workers, new_workers,
                           classification, swap_max, photon, workload_type,
                           shuffle_partitions):
    """Project runtime change as a (low%, high%) range using an Amdahl's-Law
    parallel-speedup model plus spill-removal and Photon factors. Negative =
    faster. Returns (delta_lo_pct, delta_hi_pct, factor_lo, factor_hi)."""
    cur_cores = max(1, (cur_w["vcpu"] if cur_w else 1) * max(1, cur_workers))
    new_cores = max(1, (new_w["vcpu"] if new_w else 1) * max(1, new_workers))

    spill_fix = (classification == "memory_bound" and swap_max and swap_max > 0
                 and new_w and cur_w and new_w["ram_gb"] > cur_w["ram_gb"])
    node_same = (new_w and cur_w and new_w["node_type"] == cur_w["node_type"]
                 and new_workers == cur_workers)
    if node_same and not photon and not spill_fix:
        return (0.0, 0.0, 1.0, 1.0)

    # Cap useful cores at the shuffle-partition ceiling (extra cores idle).
    if shuffle_partitions:
        sp = float(shuffle_partitions)
        cur_eff = min(cur_cores, sp)
        new_eff = min(new_cores, sp)
    else:
        cur_eff, new_eff = cur_cores, new_cores
    k = new_eff / cur_eff if cur_eff else 1.0

    p_lo, p_hi = PARALLEL_FRACTION.get(workload_type, PARALLEL_FRACTION[None])
    # Amdahl: factor = (1-p) + p/k. Evaluate at both p bounds.
    rf_a = (1 - p_lo) + p_lo / k
    rf_b = (1 - p_hi) + p_hi / k
    rf_lo, rf_hi = min(rf_a, rf_b), max(rf_a, rf_b)

    mem_lo, mem_hi = (SPILL_SPEEDUP if spill_fix else (1.0, 1.0))
    if photon and workload_type in PHOTON_RUNTIME:
        ph_lo, ph_hi = PHOTON_RUNTIME[workload_type]
    else:
        ph_lo, ph_hi = (1.0, 1.0)

    factor_lo = rf_lo * mem_lo * ph_lo
    factor_hi = rf_hi * mem_hi * ph_hi
    return (round((factor_lo - 1) * 100, 1), round((factor_hi - 1) * 100, 1),
            factor_lo, factor_hi)


def _tier_cost(node_dbu_delta_pct, factor_lo, factor_hi, spot, photon,
               pricing, runs_per_week):
    """Project cost change for a tier. Cost ~ relative-DBU-weight x runtime, then
    apply Photon DBU uplift and blended spot savings. Returns a dict of ranges;
    absolute $ only when a billed baseline is supplied."""
    dbu_ratio = 1 + node_dbu_delta_pct / 100.0
    dbu_lo = dbu_hi = dbu_ratio
    if photon:
        dbu_lo *= PHOTON_DBU_UPLIFT[0]
        dbu_hi *= PHOTON_DBU_UPLIFT[1]

    cf_lo = dbu_lo * factor_lo
    cf_hi = dbu_hi * factor_hi
    if spot:
        cf_lo *= (1 - SPOT_BLENDED_SAVING[1])   # best-case saving lowers the floor
        cf_hi *= (1 - SPOT_BLENDED_SAVING[0])
    lo, hi = min(cf_lo, cf_hi), max(cf_lo, cf_hi)

    out = {
        "cost_delta_pct": [round((lo - 1) * 100, 1), round((hi - 1) * 100, 1)],
        "est_cost_usd_per_run": None,
        "est_annual_cost_delta_usd": None,
        "spot": spot,
        "photon": photon,
    }
    base_usd = (pricing or {}).get("baseline_cost_usd")
    if base_usd is not None:
        base_usd = float(base_usd)
        per_run = [round(base_usd * lo, 2), round(base_usd * hi, 2)]
        out["est_cost_usd_per_run"] = per_run
        delta_per_run = [round(base_usd * (lo - 1), 2), round(base_usd * (hi - 1), 2)]
        out["est_cost_delta_usd_per_run"] = delta_per_run
        if runs_per_week:
            n_year = float(runs_per_week) * WEEKS_PER_YEAR
            out["est_annual_cost_delta_usd"] = [
                round(delta_per_run[0] * n_year, 0),
                round(delta_per_run[1] * n_year, 0)]
    return out


# ---------------------------------------------------------------------------
# Tier construction + default selection
# ---------------------------------------------------------------------------
def _build_tier(name, *, worker, driver, max_as, direction, spot, photon,
                strategy, cur_w, cur_d, n_workers, classification, swap_max,
                workload_type, shuffle_partitions, pricing, runs_per_week,
                catalog):
    new_w = node_by_type(catalog, worker)
    new_d = node_by_type(catalog, driver)
    node_dbu = _rel_dbu_delta(cur_w, new_w, cur_d, new_d, n_workers)
    rt_lo, rt_hi, f_lo, f_hi = _project_runtime_range(
        cur_w, new_w, n_workers, n_workers, classification, swap_max, photon,
        workload_type, shuffle_partitions)
    cost = _tier_cost(node_dbu, f_lo, f_hi, spot, photon, pricing, runs_per_week)
    runtime_known = (workload_type is not None) or (rt_lo, rt_hi) != (0.0, 0.0)
    return {
        "tier": name,
        "strategy": strategy,
        "direction": direction,
        "worker_node_type": worker,
        "driver_node_type": driver,
        "max_autoscale_workers": max_as,
        "spot_workers": spot,
        "photon": photon,
        "est_dbu_delta_pct": node_dbu,
        "runtime_delta_pct": ([rt_lo, rt_hi] if runtime_known else None),
        "cost": cost,
    }


def _choose_default_tier(cadence_bucket, crit_tier, classification):
    """Pick which tier to recommend. Fixes (scale-up) bias to stability for
    critical jobs; cost opportunities bias cheaper for infrequent/non-critical
    jobs. Unknown signal -> Balanced (preserves legacy single-verdict behavior)."""
    is_fix = classification in ("memory_bound", "driver_bound", "cpu_bound",
                                "autoscale_capped")
    if is_fix:
        if crit_tier == "high":
            return "performance"
        if crit_tier == "low":
            return "cost"
        return "balanced"
    # cost opportunity (over_provisioned / balanced). Explicit criticality wins
    # over cadence: a critical job is protected even if it runs infrequently, and
    # a non-critical job is cheap even if it runs often. Cadence only breaks ties
    # when criticality is medium/unknown.
    if crit_tier == "high":
        return "performance"
    if crit_tier == "low":
        return "cost"
    if cadence_bucket == "weekly_or_less":
        return "cost"
    if cadence_bucket == "hourly_or_more":
        return "performance"
    return "balanced"


def _collect_caveats(config, profile, classification, swap_max, tiers, trend):
    workload = profile.get("workload") or {}
    pricing = profile.get("pricing") or {}
    src = (config.get("cluster_source") or "").upper()
    caveats = []
    if src in ("UI", "API"):
        caveats.append(
            "All-purpose compute (cluster_source=%s): job cost is NOT attributable "
            "in system.billing, so cost is shown as relative DBU only." % src)
    if workload.get("is_serverless"):
        caveats.append(
            "Serverless job: system.compute.node_timeline is unavailable, so the "
            "utilization profile is degraded — treat sizing as directional.")
    if pricing.get("baseline_cost_usd") is None:
        caveats.append(
            "No billed $ anchor supplied (system.billing): cost projections are "
            "relative %, not absolute dollars.")
    if swap_max and swap_max > 0:
        caveats.append(
            "Spill detected (swap>0): guardrail blocks any memory downsize; the "
            "Cost tier still never reduces RAM here.")
    p50 = (trend or {}).get("runtime_seconds_p50")
    if p50 is not None and float(p50) < 300 and not workload.get("uses_pool"):
        caveats.append(
            "Short runs (<5 min): avoid autoscale without a warm instance pool "
            "(cluster spin-up would dominate). Use a pool or fixed size.")
    wt = workload.get("workload_type")
    if wt in ("ml", "streaming") and any(t["photon"] for t in tiers):
        caveats.append(
            "Photon disabled for %s workloads (UDF/RDD/streaming see little or no "
            "benefit and may regress)." % wt)
    if wt == "streaming":
        caveats.append(
            "Streaming detected: consider Delta Live Tables / Lakeflow for "
            "autoscaling instead of classic cluster autoscale.")
    return caveats


def _augment_with_tiers(result, profile, config, catalog):
    """Turn the base single verdict into three trade-off tiers + projections and
    select the recommended default. Overrides the top-level recommendation with
    the chosen tier (a no-op when the default is Balanced / no cadence signal)."""
    job = profile.get("job") or {}
    workload = profile.get("workload") or {}
    pricing = profile.get("pricing") or {}
    classification = result["classification"]
    swap_max = float((profile.get("worker") or {}).get("swap_max") or 0)

    cadence = _derive_cadence(job)
    criticality = _derive_criticality(job, cadence["bucket"])
    trend = _summarize_trend(profile.get("trend"))
    result["cadence"] = cadence
    result["criticality"] = criticality
    result["trend"] = trend

    cur_w = node_by_type(catalog, config.get("worker_node_type"))
    cur_d = node_by_type(catalog, config.get("driver_node_type"))
    n = _effective_workers(config, profile)
    base_w = result["recommended_worker_node_type"]
    base_d = result["recommended_driver_node_type"]
    base_max = result["recommended_max_autoscale_workers"]
    base_dir = result["direction"]
    cur_wt = config.get("worker_node_type")
    cur_dt = config.get("driver_node_type")

    crit = criticality["tier"]
    wt = workload.get("workload_type")
    sp = workload.get("shuffle_partitions")
    rpw = cadence.get("runs_per_week")
    spot_ok = crit != "high"
    photon_ok = wt in PHOTON_RUNTIME  # only sql_heavy / simple_etl

    def tier(name, **kw):
        return _build_tier(
            name, cur_w=cur_w, cur_d=cur_d, n_workers=n,
            classification=classification, swap_max=swap_max,
            workload_type=wt, shuffle_partitions=sp, pricing=pricing,
            runs_per_week=rpw, catalog=catalog, **kw)

    tiers = []
    if classification in ("memory_bound", "driver_bound", "cpu_bound",
                          "autoscale_capped"):
        # Mandatory fix — all tiers share the corrective node; knobs differ.
        tiers.append(tier("cost", worker=base_w, driver=base_d, max_as=base_max,
                          direction=base_dir, spot=spot_ok, photon=False,
                          strategy="Cheapest fix: corrective node + spot workers + autoscale."))
        tiers.append(tier("balanced", worker=base_w, driver=base_d, max_as=base_max,
                          direction=base_dir, spot=spot_ok, photon=photon_ok,
                          strategy="Corrective node at target headroom; spot+fallback."))
        tiers.append(tier("performance", worker=base_w, driver=base_d, max_as=base_max,
                          direction=base_dir, spot=False, photon=photon_ok,
                          strategy="Corrective node on-demand for stability; Photon if SQL-heavy."))
    elif classification == "over_provisioned":
        # Real cost/perf trade-off: shrink hard, shrink modestly, or hold.
        tiers.append(tier("cost", worker=base_w, driver=base_d, max_as=base_max,
                          direction="down", spot=spot_ok, photon=False,
                          strategy="Smallest viable node + spot + autoscale; max saving."))
        tiers.append(tier("balanced", worker=base_w, driver=base_d, max_as=base_max,
                          direction="down", spot=False, photon=False,
                          strategy="Downsize to smallest viable node, on-demand."))
        tiers.append(tier("performance", worker=cur_wt, driver=cur_dt, max_as=base_max,
                          direction="keep", spot=False, photon=photon_ok,
                          strategy="Keep the proven size; no runtime risk."))
    else:  # balanced — no resize; save only via knobs
        tiers.append(tier("cost", worker=cur_wt, driver=cur_dt, max_as=base_max,
                          direction="keep", spot=spot_ok, photon=False,
                          strategy="Hold size; trim cost with spot + autoscale + auto-termination."))
        tiers.append(tier("balanced", worker=cur_wt, driver=cur_dt, max_as=base_max,
                          direction="keep", spot=False, photon=False,
                          strategy="Right-sized already; keep as-is."))
        tiers.append(tier("performance", worker=cur_wt, driver=cur_dt, max_as=base_max,
                          direction="keep", spot=False, photon=photon_ok,
                          strategy="Hold size; add Photon if SQL-heavy for headroom."))

    result["options"] = tiers
    default = _choose_default_tier(cadence["bucket"], crit, classification)
    result["recommended_tier"] = default

    chosen = next((t for t in tiers if t["tier"] == default), tiers[1])
    # Override the legacy top-level keys with the chosen tier. When default is
    # Balanced (unknown cadence/criticality) this matches the base verdict, so
    # the offline fixtures are unaffected.
    result["direction"] = chosen["direction"]
    result["recommended_worker_node_type"] = chosen["worker_node_type"]
    result["recommended_driver_node_type"] = chosen["driver_node_type"]
    result["recommended_max_autoscale_workers"] = chosen["max_autoscale_workers"]
    result["est_dbu_delta_pct"] = chosen["est_dbu_delta_pct"]

    result["caveats"] = _collect_caveats(config, profile, classification,
                                         swap_max, tiers, trend)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
def _apply_snippet(result, config, tier=None):
    """Recommended change as a JSON block, applied by a human via the Databricks
    UI or the Clusters/Jobs REST API.

    The SQL MCP server cannot edit compute, and this skill never uses the
    Databricks CLI, so the recommendation is emitted as data to apply by hand.
    When a tier is given, its node + spot/Photon knobs are reflected.
    """
    src = (config.get("cluster_source") or "").upper()
    if tier:
        new_worker = tier["worker_node_type"]
        new_driver = tier["driver_node_type"]
        max_as = tier.get("max_autoscale_workers")
        spot = tier.get("spot_workers")
        photon = tier.get("photon")
    else:
        new_worker = result["recommended_worker_node_type"]
        new_driver = result["recommended_driver_node_type"]
        max_as = result.get("recommended_max_autoscale_workers")
        spot = photon = False

    def _decorate(cluster):
        cluster["node_type_id"] = new_worker
        cluster["driver_node_type_id"] = new_driver
        if max_as:
            cluster["autoscale"] = {
                "min_workers": config.get("min_autoscale_workers") or 1,
                "max_workers": max_as,
            }
        if photon:
            cluster["runtime_engine"] = "PHOTON"
        if spot:
            # Keep the driver on-demand (guardrail G1); workers go spot.
            cluster["azure_attributes"] = {
                "availability": "SPOT_WITH_FALLBACK_AZURE",
                "first_on_demand": 1,
                "spot_bid_max_price": -1,
            }
        return cluster

    if src in ("JOB", "PIPELINE"):
        block = {"new_cluster": _decorate({})}
        return ("Update the job's `new_cluster` via the Jobs UI or the Jobs REST API "
                "(`POST /api/2.2/jobs/update`):\n"
                "```json\n" + json.dumps(block, indent=2) + "\n```")
    block = _decorate({"cluster_id": config.get("cluster_id")})
    return ("Apply to the all-purpose cluster via the Compute UI (Edit) or the "
            "Clusters REST API (`POST /api/2.1/clusters/edit`):\n"
            "```json\n" + json.dumps(block, indent=2) + "\n```")


def _fmt_pct_range(rng):
    """Format a [lo, hi] percent range as '+5% .. +12%' (or 'n/a')."""
    if not rng:
        return "n/a"
    lo, hi = rng
    if lo == hi:
        return f"{lo:+.0f}%"
    return f"{lo:+.0f}% .. {hi:+.0f}%"


def _fmt_usd_range(rng, per="run"):
    if not rng:
        return None
    lo, hi = rng
    if lo == hi:
        return f"${lo:,.2f}/{per}"
    return f"${lo:,.2f} .. ${hi:,.2f}/{per}"


def render_markdown(result, config):
    w = result["evidence"]["worker"] or {}
    d = result["evidence"]["driver"]
    arrow = {"up": "SCALE UP", "down": "SCALE DOWN",
             "keep": "KEEP AS-IS", "abstain": "INSUFFICIENT DATA"}[result["direction"]]
    rec_tier = result.get("recommended_tier")
    lines = [
        f"# Cluster sizing: {result.get('cluster_name') or result.get('cluster_id')}",
        "",
        f"**Verdict:** {arrow}"
        + (f" (recommended tier: **{rec_tier.title()}**)" if rec_tier else "")
        + f"  |  **Class:** `{result['classification']}`  "
        f"|  **Confidence:** {result['confidence']}  "
        f"|  **Signal:** {result['source']}",
    ]

    cad = result.get("cadence")
    crit = result.get("criticality")
    if cad and cad.get("bucket") not in (None, "unknown"):
        line = f"**Cadence:** `{cad['bucket']}` ({cad['descriptor']})"
        if crit and crit.get("tier") not in (None, "unknown"):
            line += f"  |  **Criticality:** `{crit['tier']}` (from {crit['source']})"
        lines += ["", line]

    lines += [
        "",
        "## Evidence (worker nodes)",
        "| metric | value |",
        "|---|---|",
        f"| sample minutes | {w.get('sample_minutes')} |",
        f"| CPU busy p50 / p95 / max | {w.get('cpu_p50')} / {w.get('cpu_p95')} / {w.get('cpu_max')} % |",
        f"| Mem used p95 / max | {w.get('mem_p95')} / {w.get('mem_max')} % |",
        f"| Swap max | {w.get('swap_max')} % |",
    ]
    if d:
        lines.append(f"| Driver mem p95 / max | {d.get('mem_p95')} / {d.get('mem_max')} % |")
    if result["evidence"].get("observed_peak_workers") is not None:
        lines.append(f"| Observed peak workers | {result['evidence']['observed_peak_workers']} |")

    trend = result.get("trend")
    if trend:
        lines += [
            "",
            "## Trend (last %s runs)" % (trend.get("n_runs") or "N"),
            f"- runtime p50 / p90: {trend.get('runtime_seconds_p50')} / "
            f"{trend.get('runtime_seconds_p90')} s",
        ]
        if trend.get("cost_usd_p50") is not None:
            lines.append(f"- cost/run p50 / p90: ${trend.get('cost_usd_p50')} / "
                         f"${trend.get('cost_usd_p90')}")
        if trend.get("success_rate") is not None:
            lines.append(f"- success rate: {float(trend['success_rate']):.0%}")
        lines.append(f"- _{trend.get('note')}_")

    opts = result.get("options") or []
    if opts:
        lines += [
            "",
            "## Options (cost vs performance)",
            "| Tier | Worker node | Δ DBU | Δ runtime | Δ cost | spot / Photon |",
            "|---|---|---|---|---|---|",
        ]
        for o in opts:
            star = " ★" if o["tier"] == rec_tier else ""
            knobs = ("spot" if o["spot_workers"] else "on-demand") + \
                    (" + Photon" if o["photon"] else "")
            cost = o["cost"]
            usd = _fmt_usd_range(cost.get("est_cost_delta_usd_per_run"))
            cost_cell = _fmt_pct_range(cost.get("cost_delta_pct"))
            if usd:
                cost_cell += f" ({usd})"
            lines.append(
                f"| {o['tier'].title()}{star} | "
                f"`{o['worker_node_type']}` | "
                f"{o['est_dbu_delta_pct']:+.0f}% | "
                f"{_fmt_pct_range(o.get('runtime_delta_pct'))} | "
                f"{cost_cell} | {knobs} |")
        # Annualized savings call-out for the recommended tier, if known.
        rec = next((o for o in opts if o["tier"] == rec_tier), None)
        if rec and rec["cost"].get("est_annual_cost_delta_usd"):
            lo, hi = rec["cost"]["est_annual_cost_delta_usd"]  # negative = saving
            if hi <= 0:                      # whole range is a saving
                body = f"~${-hi:,.0f} .. ${-lo:,.0f}/yr save"
            elif lo >= 0:                    # whole range is added cost
                body = f"~${lo:,.0f} .. ${hi:,.0f}/yr add"
            else:                            # range crosses zero
                body = (f"between ~${-lo:,.0f}/yr saved and "
                        f"~${hi:,.0f}/yr added")
            lines.append("")
            lines.append(
                f"> **Annualized ({rec_tier.title()} tier):** {body} "
                f"at this cadence.")

    lines += [
        "",
        "## Recommendation",
        f"- **Worker node:** `{result['current_worker_node_type']}` -> "
        f"`{result['recommended_worker_node_type']}`",
        f"- **Driver node:** `{result['current_driver_node_type']}` -> "
        f"`{result['recommended_driver_node_type']}`",
    ]
    if result.get("recommended_max_autoscale_workers") != config.get("max_autoscale_workers"):
        lines.append(f"- **Max autoscale workers:** {config.get('max_autoscale_workers')} -> "
                     f"{result['recommended_max_autoscale_workers']}")
    lines += [
        f"- **Est. DBU change:** {result['est_dbu_delta_pct']:+.1f}% (relative)",
        "",
        f"> {result['rationale']}",
        "",
        "## Apply",
        _apply_snippet(result, config,
                       next((o for o in opts if o["tier"] == rec_tier), None)),
    ]

    caveats = result.get("caveats") or []
    if caveats:
        lines += ["", "## Caveats"]
        lines += [f"- {c}" for c in caveats]

    if result["confidence"] != "high":
        lines += ["", f"_Confidence is {result['confidence']}; "
                  "treat as directional and validate on a representative run._"]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# JSON ingest + entrypoint (no Databricks access)
# ---------------------------------------------------------------------------
def _read_payload(src):
    """Read the {config, profile} payload from a file path or '-' (stdin)."""
    if src == "-":
        text = sys.stdin.read()
    else:
        with open(src, encoding="utf-8") as fh:
            text = fh.read()
    if not text.strip():
        raise ValueError("empty payload (expected JSON with 'config' and 'profile')")
    return json.loads(text)


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Right-size a Databricks cluster from a JSON utilization "
                    "payload the agent captured via the SQL MCP server. This "
                    "script performs no Databricks access and uses no CLI.")
    p.add_argument("--from-json", required=True, metavar="PATH",
                   help="Path to the {config, profile} JSON payload, or '-' for stdin.")
    p.add_argument("--catalog", default=DEFAULT_CATALOG, help="Path to node_catalog.csv")
    p.add_argument("--json", action="store_true", help="Emit raw JSON instead of Markdown")
    args = p.parse_args(argv)

    # Keep output portable on consoles whose default codec isn't UTF-8.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    try:
        payload = _read_payload(args.from_json)
    except (OSError, ValueError) as e:
        print(f"Error: could not read --from-json payload: {e}", file=sys.stderr)
        return 2

    config = payload.get("config")
    profile = payload.get("profile")
    if not isinstance(config, dict) or not isinstance(profile, dict):
        print("Error: payload must be a JSON object with 'config' and 'profile' "
              "objects. Capture them via the SQL MCP server (see SKILL.md and "
              "references/queries.sql).", file=sys.stderr)
        return 2
    # The agent collects from system tables; default the signal source accordingly.
    profile.setdefault("source", "system_tables")

    catalog = load_catalog(args.catalog)
    result = recommend(profile, config, catalog)

    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(render_markdown(result, config))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
