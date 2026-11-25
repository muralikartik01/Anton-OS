# Eval rubric — databricks-cluster-sizer

Two layers of evaluation.

## 1. Offline deterministic suite (authoritative)
`python evals/run_evals.py` runs the pure `recommend()` over golden fixtures in
`fixtures/` and asserts against `expected.json`. This is the source of truth for
correctness and must be 100% green before shipping any change to thresholds, the
node catalog, the cadence/criticality model, the projection formulas, or the
sizing logic.

Coverage:
- **Direction accuracy** — every scenario (over-provisioned, memory-bound,
  CPU-bound, autoscale-capped, balanced, insufficient-data, driver-bound, floor)
  yields the right up/down/keep/abstain verdict and classification.
- **Safety guardrails** — `memory_pressure_low_cpu` proves the tool never
  downsizes when memory is the bottleneck even though CPU is idle;
  `insufficient_data` proves it abstains on thin signal; no fixture may produce
  an unsafe downsize. `hourly_critical_memfix` proves a spilling critical job is
  never put on spot and never has its RAM reduced in any tier.
- **Cadence & criticality** — `weekly_noncritical_downsize` resolves the weekly
  bucket + low criticality and defaults to the **Cost** tier;
  `daily_balanced_default` resolves daily + medium and defaults to **Balanced**;
  `hourly_critical_memfix` resolves hourly + high and defaults to **Performance**.
  The chosen `criticality_source` (tags/sla vs cadence) is asserted.
- **Three-tier output** — every cadence fixture emits exactly **3 options**
  (Cost / Balanced / Performance), each with a cost projection and a runtime
  projection, and exactly one `recommended` tier.
- **Projection determinism** — cost (Δ% range, Δ$ per run, annualized) and
  runtime (Δ% range) are computed identically for identical input.
- **Caveats** — `allpurpose_caveat` proves an all-purpose / UI-sourced cluster
  emits the billing-not-attributable caveat instead of a false dollar figure.
- **Determinism** — identical input produces identical output.

## 2. Agent evals (Sonnet 4.6 only)
`evals/evals.json` holds **5** end-to-end scenarios pinned to `claude-sonnet-4.6`
for both the executor and analyzer (`config.models`). They exercise the full
cadence-aware, multi-tier, trend-projection behaviour through the agent, not just
the scorer. Each eval carries an `assertions` list the judge scores against.

The five scenarios:
1. **weekly-noncritical-cost-default** — weekly + low crit → Cost default, 3
   options, cost ($/% + annualized) and runtime projections.
2. **daily-balanced-tradeoff** — daily + medium → Balanced default, all 3 options
   with cost AND runtime so the user can trade off.
3. **hourly-critical-spill-guardrail** — hourly + high + spill → scale up to
   higher-RAM E-series, Performance (on-demand) default, RAM-never-reduced and
   no-spot guardrails hold.
4. **trend-based-projection** — multi-run baseline → projected Δcost ($ and %) +
   Δruntime ranges + annualized, ranges not false precision.
5. **thin-data-and-attribution-safety** — abstain on a ~4-minute sample; explain
   all-purpose cost is not attributable and fall back to relative DBU + caveat.

## 3. Qualitative review of the rendered report (LLM-as-judge)
When judging the Markdown the skill produces for a real or simulated run, score:

- **Correct direction & default tier** — does the verdict match the evidence, and
  does the Recommended tier match the cadence/criticality (weekly/low → Cost,
  daily/medium → Balanced, hourly/high or SLA-bound w/ perf issue → Performance)?
- **Three honest options** — Cost / Balanced / Performance are each shown with a
  cost projection AND a runtime projection; the runtime trade-off of cheaper tiers
  is never hidden.
- **Cites real numbers & trend** — the rationale references the actual CPU/mem
  percentiles, swap, and the multi-run trend (drift, variance, success rate), not
  vague claims.
- **Projection honesty** — cost and runtime are ranges with a stated basis;
  absolute $ is sourced from `system.billing` and degrades to relative DBU + a
  caveat when not attributable; no false precision.
- **Actionable apply snippet** — a valid `clusters edit` command (all-purpose)
  or `new_cluster` JSON (jobs) that reflects the recommended tier's node/workers,
  spot, autoscale and Photon settings.
- **Confidence honesty** — medium/low confidence (events fallback, thin data,
  all-purpose/serverless, billing lag) is surfaced and the report hedges.
- **Minimal & scannable** — evidence → cadence/criticality → trend → 3 options →
  apply, on roughly one screen.

A good report is one a data engineer can act on (or safely ignore) in under a
minute without opening the Spark UI, and one a finance partner can read a
cost/performance projection from with appropriate uncertainty.
