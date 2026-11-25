---
name: databricks-test-runner
description: Executes SQL test queries against Databricks via MCP server and returns structured RED/GREEN test results. Dispatches test batches in parallel using lightweight subagents. Use when running Gold table validation tests, executing SQL-based test cases, or validating pipeline output against expected results.
---

# Databricks Test Runner

Executes SQL test queries against a live Databricks environment via MCP and returns structured pass/fail results. Designed for parallel execution using lightweight subagents — one per test module.

## Purpose

Decouple **test generation** (agent responsibility) from **test execution** (this skill). Any agent can build a test manifest and invoke this skill to run the queries and collect results.

## Dependencies

- **Databricks SQL MCP server** — whichever Databricks SQL MCP server is configured in this workspace's MCP client config (e.g. `.vscode/mcp.json`). Server name and exact tool names vary by setup.
- MCP tool: a read-only SQL execution tool (commonly named `execute_sql_read_only` / `executeStatement` / `execute_sql`, depending on the server). If the tool returns a `statement_id` for long-running queries instead of results immediately, poll with that server's matching `poll_sql_result` tool until the status is no longer `PENDING`/`RUNNING`.

---

## Inputs

The calling agent provides a **test manifest** — a structured list of test cases:

| Field | Type | Description |
|-------|------|-------------|
| `test_id` | string | Unique identifier, e.g. `UT-1`, `DQ-3`, `PT-2` |
| `module` | string | One of: `unit`, `dq`, `performance` |
| `name` | string | Human-readable test name |
| `sql` | string | Exact SQL query to execute (read-only) |
| `expected` | string | Expected outcome descriptor (see Pass/Fail Criteria below) |
| `target_table` | string | Fully qualified table name (`catalog.schema.table`) |
| `severity` | string | `critical` or `warning` |

---

## Execution Model

### Step 1 — Group Tests by Module

Split the test manifest into independent batches:
- **Batch 1**: All tests where `module = "unit"`
- **Batch 2**: All tests where `module = "dq"`
- **Batch 3**: All tests where `module = "performance"`

### Step 2 — Dispatch Parallel Subagents

Launch **3 subagents in parallel** (one per batch). Each subagent is a lightweight runner that:

1. Receives its batch of `{test_id, sql, expected}` entries
2. For each test in the batch, executes the SQL via the workspace's Databricks SQL MCP tool (polling for `statement_id` results if the tool returns one)
3. Parses the MCP response (rows returned, column names, values, or error)
4. Compares the result against the `expected` criteria
5. Assigns status: `🔴 RED` (fail) or `🟢 GREEN` (pass)
6. Returns a list of `{test_id, status, raw_output, error_msg}`

#### Subagent Prompt Template

Each subagent receives this instruction:

```
You are a SQL test executor. For each test case below, execute the SQL query
using this workspace's Databricks SQL MCP tool (poll for `statement_id` results
if the tool returns one) and evaluate the result.

Rules:
- Execute each SQL query exactly as provided — do not modify it
- Compare the result against the expected criteria
- If the query errors or the MCP is unavailable, mark as ⚠️ SKIPPED
- Return results in the exact format specified below

Test cases:
{batch_json}

For each test, return:
- test_id: the test identifier
- status: 🔴 RED (fail) | 🟢 GREEN (pass) | ⚠️ SKIPPED (error/unavailable)
- raw_output: first 5 rows of result or scalar value or error message
- error_msg: null if no error, otherwise the error detail
- executed_at: current timestamp

Expected criteria rules:
- zero_rows: GREEN if query returns 0 rows, RED if ≥1 row
- non_zero: GREEN if query returns ≥1 row, RED if 0 rows
- matches_set:{val1,val2}: GREEN if all DISTINCT values are in {val1,val2}, RED otherwise
- column_exists:{col1,col2}: GREEN if all named columns appear in result, RED if any missing
- type_matches:{col1:type1,col2:type2}: GREEN if each column's type matches, RED otherwise
```

### Step 3 — Collect and Merge Results

After all subagents return, merge their results into a single ordered test report:
1. Concatenate results from all 3 batches
2. Sort by test_id (UT-* first, then DQ-*, then PT-*)
3. Compute summary counts: total, green, red, skipped

---

## Pass/Fail Criteria

| Expected Pattern | GREEN (Pass) | RED (Fail) |
|-----------------|-------------|------------|
| `zero_rows` | Query returns 0 rows | Query returns ≥1 row |
| `non_zero` | Query returns ≥1 row | Query returns 0 rows |
| `matches_set:{val1,val2,...}` | All DISTINCT result values are within the expected set | Any value outside the set |
| `column_exists:{col1,col2,...}` | All named columns present in query output | Any column missing |
| `type_matches:{col1:type1,col2:type2}` | Each column's reported type matches expected | Any type mismatch |

Special statuses:
- `⚠️ SKIPPED` — MCP unavailable, query timeout, or execution error
- Never mark a test GREEN on error — errors are always SKIPPED or RED

---

## MCP Interaction Rules

1. **Read-only only** — only `SELECT`, `DESCRIBE`, `DESCRIBE DETAIL`, `EXPLAIN`, and `SHOW` statements are permitted. Never execute `INSERT`, `UPDATE`, `DELETE`, `DROP`, `CREATE`, `ALTER`, or `MERGE`.
2. **Validate before executing** — if a SQL statement starts with a DDL/DML keyword, mark the test as `⚠️ SKIPPED` with error `"Blocked: DDL/DML not permitted"`.
3. **MCP unavailable** — if MCP connection fails, mark all remaining tests in the batch as `⚠️ SKIPPED` with error `"MCP unavailable"`. Do not block or retry indefinitely.
4. **Query timeout** — if a query does not return within the MCP default timeout, mark as `⚠️ SKIPPED` with error `"Query timeout"`.
5. **Error responses** — if MCP returns an error (e.g., table not found, syntax error), mark the test as `🔴 RED` with the error detail in `error_msg` and `raw_output`.

---

## Output

The skill returns a structured test report to the calling agent:

### Per-Test Result

| Field | Type | Description |
|-------|------|-------------|
| `test_id` | string | Test identifier |
| `module` | string | `unit` / `dq` / `performance` |
| `name` | string | Test name |
| `sql` | string | SQL executed (truncated to 200 chars) |
| `status` | string | `🔴 RED` / `🟢 GREEN` / `⚠️ SKIPPED` |
| `raw_output` | string | First 5 rows or scalar result |
| `error_msg` | string | `null` or error detail |
| `executed_at` | string | ISO timestamp of execution |

### Summary

| Field | Type | Description |
|-------|------|-------------|
| `total` | int | Total test count |
| `green` | int | Passing tests |
| `red` | int | Failing tests |
| `skipped` | int | Skipped tests |
| `run_timestamp` | string | ISO timestamp of run start |

---

## TDD Lifecycle

This skill supports the Red-Green-Refactor cycle:

| Phase | When | Expected Outcome |
|-------|------|-------------------|
| **RED** | First run — Gold table may not exist yet | All or most tests `🔴 RED` |
| **GREEN** | After pipeline implementation and data load | Passing tests flip to `🟢 GREEN` |
| **REFACTOR** | After all GREEN | Review tests for consolidation or cleanup |

The calling agent is responsible for tracking which phase the use case is in and writing the appropriate report.

---

## Key Rules

1. **No data modification** — this skill only reads; it never writes to Databricks
2. **No hallucinated results** — every test result must come from an actual MCP execution
3. **Graceful degradation** — MCP issues produce SKIPPED, never crash the run
4. **Parallel by module** — subagents run independently; one failing batch does not block others
5. **Deterministic evaluation** — same SQL + same data = same status; no probabilistic checks

## References

- SQL patterns: `harness/skills/databricks-test-runner/references/SQL_PATTERNS.md`
- MCP config: `.vscode/mcp.json` (Databricks SQL MCP server)
