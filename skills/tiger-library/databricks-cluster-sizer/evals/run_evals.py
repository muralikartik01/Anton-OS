#!/usr/bin/env python3
"""
run_evals.py — offline, deterministic checks for the cluster-sizer brain.

Loads each fixture (a synthetic utilization profile + cluster config), runs the
pure recommend() function, and asserts against evals/expected.json. No network
or Databricks access required, so this doubles as the skill's unit-test suite.

Run:
    python evals/run_evals.py
Exit code 0 = all green; 1 = at least one failure.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(SKILL_ROOT, "scripts"))

from size_cluster import load_catalog, main, node_by_type, recommend  # noqa: E402

CATALOG = load_catalog(os.path.join(SKILL_ROOT, "references", "node_catalog.csv"))


def _check(name, result, config, checks):
    """Evaluate the generic check keys in expected.json against a result."""
    cur_w = node_by_type(CATALOG, config["worker_node_type"])
    rec_w = node_by_type(CATALOG, result["recommended_worker_node_type"])
    failures = []

    def fail(msg):
        failures.append(msg)

    for key, want in checks.items():
        if key == "worker_node_unchanged" and want:
            if result["recommended_worker_node_type"] != config["worker_node_type"]:
                fail(f"worker node changed ({config['worker_node_type']} -> {result['recommended_worker_node_type']})")
        elif key == "driver_node_unchanged" and want:
            if result["recommended_driver_node_type"] != config["driver_node_type"]:
                fail("driver node changed but should not")
        elif key == "driver_changed" and want:
            if result["recommended_driver_node_type"] == config["driver_node_type"]:
                fail("driver node unchanged but should have been upsized")
        elif key == "rec_worker_family":
            if not rec_w or rec_w["family"] != want:
                fail(f"rec worker family {rec_w and rec_w['family']} != {want}")
        elif key == "rec_worker_min_ram":
            if not rec_w or rec_w["ram_gb"] < want:
                fail(f"rec worker ram {rec_w and rec_w['ram_gb']} < {want}")
        elif key == "rec_worker_min_vcpu":
            if not rec_w or rec_w["vcpu"] < want:
                fail(f"rec worker vcpu {rec_w and rec_w['vcpu']} < {want}")
        elif key == "rec_vcpu_increases" and want:
            if not (rec_w and cur_w and rec_w["vcpu"] > cur_w["vcpu"]):
                fail("rec worker vcpu did not increase")
        elif key == "not_smaller_than_current" and want:
            if rec_w and cur_w and rec_w["rel_dbu"] < cur_w["rel_dbu"]:
                fail(f"SAFETY: recommended smaller node ({rec_w['node_type']}) than current ({cur_w['node_type']})")
        elif key == "smaller_than_current" and want:
            if not (rec_w and cur_w and rec_w["rel_dbu"] < cur_w["rel_dbu"]):
                fail("expected a smaller node but did not get one")
        elif key == "rec_max_autoscale":
            if result.get("recommended_max_autoscale_workers") != want:
                fail(f"rec max autoscale {result.get('recommended_max_autoscale_workers')} != {want}")
        elif key == "saves_dbu" and want:
            if not result["est_dbu_delta_pct"] < 0:
                fail(f"expected DBU savings, got {result['est_dbu_delta_pct']:+}%")
        elif key == "increases_dbu" and want:
            if not result["est_dbu_delta_pct"] > 0:
                fail("expected DBU increase, got none")
        elif key == "recommended_tier":
            if result.get("recommended_tier") != want:
                fail(f"recommended_tier {result.get('recommended_tier')} != {want}")
        elif key == "num_options":
            n = len(result.get("options") or [])
            if n != want:
                fail(f"num_options {n} != {want}")
        elif key == "cadence_bucket":
            got = (result.get("cadence") or {}).get("bucket")
            if got != want:
                fail(f"cadence_bucket {got} != {want}")
        elif key == "criticality_tier":
            got = (result.get("criticality") or {}).get("tier")
            if got != want:
                fail(f"criticality_tier {got} != {want}")
        elif key == "criticality_source":
            got = (result.get("criticality") or {}).get("source")
            if got != want:
                fail(f"criticality_source {got} != {want}")
        elif key == "rec_tier_runtime_projected" and want:
            tier = _rec_tier(result)
            if not tier or tier.get("runtime_delta_pct") is None:
                fail("recommended tier has no runtime projection")
        elif key == "rec_tier_cost_dollars" and want:
            tier = _rec_tier(result)
            cost = (tier or {}).get("cost") or {}
            if cost.get("est_cost_usd_per_run") is None:
                fail("recommended tier has no absolute $ cost projection")
        elif key == "rec_tier_on_demand" and want:
            tier = _rec_tier(result)
            if not tier or tier.get("spot_workers"):
                fail("recommended tier uses spot but should be on-demand")
        elif key == "has_caveat_substr":
            caveats = result.get("caveats") or []
            if not any(want.lower() in c.lower() for c in caveats):
                fail(f"no caveat containing '{want}' (got {len(caveats)} caveats)")
    return failures


def _rec_tier(result):
    """Return the recommended tier dict from a result, or None."""
    rec = result.get("recommended_tier")
    for o in result.get("options") or []:
        if o.get("tier") == rec:
            return o
    return None


def _ingest_smoke():
    """Exercise scripts/size_cluster.py --from-json end to end and assert the
    emitted verdict matches a direct recommend() call. Uses only local fixtures
    (including the abstain-when-system-tables-unavailable case); performs no
    Databricks access."""
    names = ["over_provisioned", "memory_bound_swap", "cpu_bound",
             "unavailable_system_tables", "weekly_noncritical_downsize",
             "hourly_critical_memfix", "weekly_critical_explicit"]
    errs = []
    for name in names:
        path = os.path.join(HERE, "fixtures", name + ".json")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = main(["--from-json", path, "--json"])
        if rc != 0:
            errs.append(f"{name}: exit code {rc}")
            continue
        try:
            out = json.loads(buf.getvalue())
        except json.JSONDecodeError:
            errs.append(f"{name}: ingest did not emit valid JSON")
            continue
        fx = json.load(open(path, encoding="utf-8"))
        ref = recommend(fx["profile"], fx["config"], CATALOG)
        if (out.get("direction"), out.get("classification")) != \
           (ref["direction"], ref["classification"]):
            errs.append(f"{name}: ingest verdict diverged from recommend()")
    # The stdin path ('-') must work too.
    payload = json.dumps(json.load(open(
        os.path.join(HERE, "fixtures", "balanced.json"), encoding="utf-8")))
    buf = io.StringIO()
    real_stdin = sys.stdin
    try:
        sys.stdin = io.StringIO(payload)
        with contextlib.redirect_stdout(buf):
            rc = main(["--from-json", "-", "--json"])
    finally:
        sys.stdin = real_stdin
    if rc != 0 or not buf.getvalue().strip():
        errs.append("stdin ('-') ingest failed")
    return errs


def run():
    expected = json.load(open(os.path.join(HERE, "expected.json"), encoding="utf-8"))
    fixtures_dir = os.path.join(HERE, "fixtures")
    total = passed = 0
    print("=" * 68)
    print("databricks-cluster-sizer :: offline eval suite")
    print("=" * 68)
    for name in sorted(expected):
        total += 1
        fx = json.load(open(os.path.join(fixtures_dir, name + ".json"), encoding="utf-8"))
        config, profile = fx["config"], fx["profile"]
        result = recommend(profile, config, CATALOG)

        errs = []
        exp = expected[name]
        if result["direction"] != exp["direction"]:
            errs.append(f"direction {result['direction']} != {exp['direction']}")
        want_class = exp["classification"]
        ok_class = result["classification"] in (want_class if isinstance(want_class, list) else [want_class])
        if not ok_class:
            errs.append(f"classification {result['classification']} != {want_class}")
        errs += _check(name, result, config, exp.get("checks", {}))

        # Determinism: identical input -> identical output.
        if recommend(profile, config, CATALOG) != result:
            errs.append("non-deterministic output")

        if errs:
            print(f"[FAIL] {name}")
            for e in errs:
                print(f"        - {e}")
        else:
            passed += 1
            print(f"[PASS] {name:<24} {result['direction']:>7}  "
                  f"{result['recommended_worker_node_type']}  "
                  f"({result['est_dbu_delta_pct']:+.0f}% DBU)")

    # End-to-end check of the --from-json ingest entrypoint (no Databricks access).
    total += 1
    ingest_errs = _ingest_smoke()
    if ingest_errs:
        print("[FAIL] --from-json ingest")
        for e in ingest_errs:
            print(f"        - {e}")
    else:
        passed += 1
        print(f"[PASS] {'--from-json ingest':<24} end-to-end parity OK")

    print("-" * 68)
    print(f"{passed}/{total} passed")
    # Global safety sweep: no fixture may produce an unsafe downsize.
    print("Safety: no downsize under memory pressure or thin data — "
          + ("OK" if passed == total else "CHECK FAILURES"))
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(run())
