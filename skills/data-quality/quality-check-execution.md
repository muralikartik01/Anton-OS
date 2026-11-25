# Skill: Quality check execution

**Used by:** Validation Agent.

**Purpose:** Turn generated quality rules into real, executed checks against the declared connection and record a truthful pass/fail/blocked status for each one. This closes the loop that `quality-rule-generation` leaves open — generating a rule document is not the same as checking the data.

**Adapted from:** `skills/tiger-library/databricks-test-runner/SKILL.md` — its RED/GREEN/SKIPPED model maps onto DB-Kit's `fail`/`pass`/`blocked`, and its pass/fail criteria and parallel-by-module dispatch are adopted. It is otherwise new to DB-Kit: `data-product-orchestrator` only generates the rule document, but this framework's Validation Agent runs deterministic checks (design principle #5). Tiger's `.vscode/mcp.json` server routing and emoji statuses are dropped.

## Procedure

For every rule from `quality-rule-generation`:

1. Take the rule's `sql` and run it **unmodified** with `execute_sql_read_only(sql, row_limit)` on `db-kit-databricks` (subject to `hooks/pre-execution/` like any call). Only `SELECT`/`WITH`/`DESCRIBE`/`SHOW`/`EXPLAIN` are accepted; a rule whose SQL starts with DDL/DML is `blocked` ("DDL/DML not permitted"), never run. Materializing approved Bronze/Silver artifacts with `execute_statement` happens before this skill, at the start of Stage 6, and is not part of rule execution.
2. Evaluate against `expected`: `zero_rows` passes on 0 rows; `non_zero` on at least 1; `matches_set` when all distinct values are in the set; `column_exists` when every named column is present; `type_matches` when every type matches.
3. Record one of:
   - `pass` — ran and met `expected`.
   - `fail` — ran and did not (include violation count and up to 5 sample keys). A query error such as a missing table is a `fail` with the error text as evidence.
   - `blocked` — could not run (connection unreachable, timeout, insufficient access, DML blocked); state the reason.
4. Never report `pass` on error, and never for a rule that wasn't actually executed. Results come only from real tool output.
5. **Optional parallel dispatch:** for larger rule sets, group rules by `category` and run one subagent per group, each given its rules and told to execute SQL exactly as written. One failing batch doesn't block the others. Merge by `rule_id`, then report totals (pass/fail/blocked).

## CSV export

After `results.md` is written, update `artifacts/validation/<project-id>/<run-id>/quality-rules.csv` (columns `rule_id,table,column,category,expected,severity,sql,evidence_ref,status,detail`, created by `quality-rule-generation`; create it from `test-plan.md` if absent). Fill `status` with `pass`, `fail` or `blocked` for every rule and `detail` with the violation count/reason (sample keys only, never row contents beyond the key columns). It is generated from the same results as `results.md`: the markdown stays primary and the hooks keep checking `results.md`, not the CSV. Statistics and statuses only, never raw row samples.

## Output

`artifacts/validation/<project-id>/<run-id>/results.md`: one row per rule with status, evidence (row counts, sample keys, first rows of output), `executed_at`, and — for `blocked` rules — the reason, plus a pass/fail/blocked summary. This is the artifact the validation-gate hook checks for completeness (every planned rule has a status, none silently omitted).
