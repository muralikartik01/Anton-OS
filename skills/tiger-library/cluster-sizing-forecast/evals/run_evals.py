#!/usr/bin/env python3
"""
run_evals.py - offline, deterministic checks for the cluster-sizing forecaster.

Loads each fixture (a design-time sizing payload), runs the pure forecast()
function, and asserts against evals/expected.json. No network or Databricks
access required, so this doubles as the skill's regression suite.

Run:
    python evals/run_evals.py
Exit code 0 = all green; 1 = at least one failure.
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL_ROOT = HERE.parent
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from forecast_size import (  # noqa: E402
    forecast, load_catalog, main, node_by_type, render_markdown,
)

CATALOG = load_catalog(SKILL_ROOT / "references" / "node_catalog.csv")
TOP_LEVEL_KEYS = {
    "abstained", "abstain_reasons", "workload_class", "recommended_cluster",
    "recommended_tier", "options", "rationale", "cost_projection",
    "assumptions", "citations", "generated_by",
}
FORBIDDEN_SUBSTRINGS = ["spark.executor.memory", "spark.dynamicAllocation"]


def _path(obj, dotted):
    cur = obj
    for part in dotted.split("."):
        if isinstance(cur, list):
            cur = cur[int(part)]
        elif isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def _as_list(value):
    return value if isinstance(value, list) else [value]


def _check(name, result, checks):
    """Evaluate generic check keys in expected.json against a forecast result."""
    failures = []

    def fail(msg):
        failures.append(msg)

    for path, want in checks.get("equals", {}).items():
        got = _path(result, path)
        if got != want:
            fail(f"{path} {got!r} != {want!r}")

    for path, choices in checks.get("one_of", {}).items():
        got = _path(result, path)
        if got not in choices:
            fail(f"{path} {got!r} not in {choices!r}")

    for path, prefix in checks.get("startswith", {}).items():
        got = _path(result, path)
        if not isinstance(got, str) or not got.startswith(prefix):
            fail(f"{path} {got!r} does not start with {prefix!r}")

    for path, bounds in checks.get("range", {}).items():
        got = _path(result, path)
        lo, hi = bounds
        if got is None or got < lo or got > hi:
            fail(f"{path} {got!r} outside [{lo!r}, {hi!r}]")

    for path, want in checks.get("gte", {}).items():
        got = _path(result, path)
        if got is None or got < want:
            fail(f"{path} {got!r} < {want!r}")

    for path, want in checks.get("lte", {}).items():
        got = _path(result, path)
        if got is None or got > want:
            fail(f"{path} {got!r} > {want!r}")

    for path, want_len in checks.get("length", {}).items():
        got = _path(result, path)
        if len(got or []) != want_len:
            fail(f"{path} length {len(got or [])} != {want_len}")

    for path in _as_list(checks.get("not_empty", [])):
        got = _path(result, path)
        if not got:
            fail(f"{path} is empty")

    for path in _as_list(checks.get("is_null", [])):
        if _path(result, path) is not None:
            fail(f"{path} is not null")

    for path, family in checks.get("node_family", {}).items():
        node_type = _path(result, path)
        node = node_by_type(CATALOG, node_type) if node_type else None
        if not node or node.get("family") != family:
            fail(f"{path} family {node and node.get('family')!r} != {family!r}")

    for path in _as_list(checks.get("cost_band", [])):
        band = _path(result, path) or {}
        if not (band.get("low") <= band.get("expected") <= band.get("high")):
            fail(f"{path} is not ordered low<=expected<=high: {band!r}")

    for text in _as_list(checks.get("assumption_contains", [])):
        assumptions = "\n".join(result.get("assumptions") or []).lower()
        if text.lower() not in assumptions:
            fail(f"no assumption contains {text!r}")

    return failures


def _global_checks(name, result):
    errs = []
    if set(result.keys()) != TOP_LEVEL_KEYS:
        errs.append(f"top-level keys differ: {sorted(result.keys())}")
    if result.get("generated_by") != "cluster-forecaster":
        errs.append("generated_by != cluster-forecaster")

    serialized = json.dumps(result, sort_keys=True)
    for forbidden in FORBIDDEN_SUBSTRINGS:
        if forbidden in serialized:
            errs.append(f"forbidden Spark config substring emitted: {forbidden}")

    cites = result.get("citations") or []
    if not cites or not all(isinstance(c, str) and c.startswith("[O]") for c in cites):
        errs.append("citations missing [O] official-source markers")

    if not result.get("abstained"):
        tiers = [o.get("tier") for o in result.get("options") or []]
        if tiers != ["lean", "recommended", "conservative"]:
            errs.append(f"options tiers {tiers!r} != ['lean', 'recommended', 'conservative']")
        band = ((result.get("cost_projection") or {}).get("per_run_usd") or {})
        if not (band.get("low") <= band.get("expected") <= band.get("high")):
            errs.append(f"cost_projection.per_run_usd unordered: {band!r}")
        rec = result.get("recommended_cluster") or {}
        if rec.get("node_type_id") != rec.get("driver_node_type_id"):
            errs.append("driver node does not match worker node")
    return errs


def _ingest_smoke(expected):
    """Exercise scripts/forecast_size.py --from-json and stdin end to end."""
    errs = []
    for name in sorted(expected):
        path = HERE / "fixtures" / f"{name}.json"
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = main(["--from-json", str(path), "--json"])
        if rc != 0:
            errs.append(f"{name}: exit code {rc}")
            continue
        try:
            out = json.loads(buf.getvalue())
        except json.JSONDecodeError:
            errs.append(f"{name}: ingest did not emit valid JSON")
            continue
        inputs = json.loads(path.read_text(encoding="utf-8"))["inputs"]
        ref = forecast(inputs, CATALOG)
        if out != ref:
            errs.append(f"{name}: ingest output diverged from forecast()")

    first = sorted(expected)[0]
    payload = (HERE / "fixtures" / f"{first}.json").read_text(encoding="utf-8")
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
    expected = json.loads((HERE / "expected.json").read_text(encoding="utf-8"))
    total = passed = 0
    print("=" * 68)
    print("cluster-sizing-forecast :: offline eval suite")
    print("=" * 68)

    for name in sorted(expected):
        total += 1
        fx = json.loads((HERE / "fixtures" / f"{name}.json").read_text(encoding="utf-8"))
        result = forecast(fx["inputs"], CATALOG)
        exp = expected[name]
        errs = []
        if result.get("abstained") != exp.get("abstained"):
            errs.append(f"abstained {result.get('abstained')} != {exp.get('abstained')}")
        if result.get("workload_class") != exp.get("workload_class"):
            errs.append(f"workload_class {result.get('workload_class')} != {exp.get('workload_class')}")
        errs += _global_checks(name, result)
        errs += _check(name, result, exp.get("checks", {}))

        # Markdown report guardrails: non-abstain must carry a human-gated Apply
        # Block (and no forbidden Spark configs); abstain must verdict ABSTAIN
        # and emit no Apply Block.
        md = render_markdown(result)
        if result.get("abstained"):
            if "ABSTAIN" not in md.upper():
                errs.append("abstain markdown missing ABSTAIN verdict")
            if "Apply Block" in md:
                errs.append("abstain markdown must not emit an Apply Block")
        else:
            if "## Apply Block" not in md:
                errs.append("non-abstain markdown missing Apply Block")
            for forbidden in FORBIDDEN_SUBSTRINGS:
                if forbidden in md:
                    errs.append(f"markdown emits forbidden Spark config: {forbidden}")

        # Determinism: identical input -> identical output.
        if forecast(fx["inputs"], CATALOG) != result:
            errs.append("non-deterministic output")

        if errs:
            print(f"[FAIL] {name}")
            for e in errs:
                print(f"        - {e}")
        else:
            passed += 1
            rec = result.get("recommended_cluster") or {}
            node = rec.get("node_type_id") or "<none>"
            cost = ((result.get("cost_projection") or {}).get("per_run_usd") or {}).get("expected")
            print(f"[PASS] {name:<24} {str(result.get('workload_class')):>13}  {node}  ${cost}/run")

    total += 1
    ingest_errs = _ingest_smoke(expected)
    if ingest_errs:
        print("[FAIL] --from-json ingest")
        for e in ingest_errs:
            print(f"        - {e}")
    else:
        passed += 1
        print(f"[PASS] {'--from-json ingest':<24} end-to-end parity OK")

    print("-" * 68)
    print(f"{passed}/{total} passed")
    print("Safety: contract keys, tier shape, cost bands, and Spark-config guardrails - "
          + ("OK" if passed == total else "CHECK FAILURES"))
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(run())

