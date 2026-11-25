# Skill: Data reconciliation

**Used by:** Validation Agent.

**Purpose:** Verify that migrated data in the target actually matches the source it was derived from — distinct from `data-quality/quality-check-execution`, which checks a dataset's *internal* quality rules (not-null, uniqueness, etc.) independent of any source comparison.

## Procedure

Against the declared non-production source and target connections, for each migrated table:

1. **Row counts:** source vs. target row count for the mapped scope (accounting for any declared filter/incremental window — do not compare full-table counts against a filtered load).
2. **Key parity:** source primary keys not present in target, and vice versa (sample and report, don't just assert "matches").
3. **Value-level spot check:** for a sample of keys, compare source and mapped-target values per `source-to-target-mapping.yaml`'s declared transformation — a mismatch here means either the mapping or the generated code is wrong, not a data-quality issue.

Every check is a real executed query against both connections — this is subject to `hooks/pre-execution/` like any other execution.

## Output

Reconciliation results appended to `results.md` alongside the quality-rule checks, each with an explicit pass/fail/blocked status and the evidence (counts, sample keys) behind it.
