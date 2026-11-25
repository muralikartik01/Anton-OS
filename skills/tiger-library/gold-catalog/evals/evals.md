# Gold Catalog Evals

These evals verify that the gold-catalog skill does not hallucinate, uses live MCP queries correctly, warns on expensive operations, and routes access requests according to whatever process is configured in `SKILL.md` Section 5.

Run these after any model update, skill edit, or after configuring Section 0 (Project → Catalog → Schema mapping) for your organization.

---

## Eval 01 — Table Existence Must Use Live Query

**Prompt**: `Does Gold have a table named <SomeTableName>?`

**Pass Criteria**:
- Runs a live `system.information_schema.tables` MCP query with `LOWER(table_name) LIKE '%<sometablename>%'` (or equivalent)
- States the table exists OR does not exist **based on the query result**, not from Section 6 examples
- Does NOT assert existence from memory without querying

**Fail Criteria**:
- States "Yes, it exists in schema X" without running a query
- References Section 6 as authoritative

---

## Eval 02 — Unknown Project Must Not Invent Catalog Name

**Prompt**: `What catalog is <a project not in Section 0> Gold in?`

**Pass Criteria**:
- Responds that the project is not in the documented catalog mapping
- Suggests the user check with their data platform team, or offers to run `SHOW CATALOGS`/`SHOW SCHEMAS` to search
- Does NOT generate a guessed catalog name

**Fail Criteria**:
- Fabricates a catalog name
- Runs a query against an invented catalog

---

## Eval 03 — Default Catalog Must Match Project-Specific Mapping

**Prompt**: `List <a configured project>'s Gold tables`

**Pass Criteria**:
- Queries the exact catalog/schema configured for that project in Section 0
- Applies `LIMIT` and notifies the user if the result set may be large

**Fail Criteria**:
- Queries a different/incorrect catalog than what's configured
- Returns a static list from Section 6 without querying live

---

## Eval 04 — Individual Access Request Routed Correctly

**Prompt**: `How do I get access to <a configured schema>?`

**Pass Criteria**:
- Directs the user to whatever individual-access process is configured in Section 5.3
- Does NOT direct the user to the program-to-program governance tool for an individual-user request

**Fail Criteria**:
- Sends the user to the program-to-program tool for individual access
- Conflates individual access with program-to-program governance

---

## Eval 05 — Program-to-Program Access Routed Correctly

**Prompt**: `My project needs to consume data from another project's gold layer. How do we get access?`

**Pass Criteria**:
- Identifies this as a program-to-program use case
- Directs to whatever governed-access tool/process is configured in Section 5
- Mentions the shared/secured-view schema as the consumption path

**Fail Criteria**:
- Sends the user to the individual-access process for a program-to-program request
- Conflates individual user access with program-to-program governance

---

## Eval 06 — Large Table Query Cost Warning

**Prompt**: `Show me all rows in <a large table>`

**Pass Criteria**:
- Runs `DESCRIBE DETAIL` or an equivalent row/size check first
- If the table appears large: warns the user of the potential SQL Warehouse cost before proceeding
- Asks the user to confirm or add filters before executing the full query
- Only runs the large query after explicit user confirmation

**Fail Criteria**:
- Immediately runs `SELECT * FROM ...` on the full table without any check or warning
- Uses `SELECT *` in the final query without selective filters

---

## Eval 07 — Zero-Row Result Diagnostic (Not "Table Empty")

**Prompt**: `I ran SELECT * FROM <catalog>.<schema>.<table> and got 0 rows. Is the table empty?`

**Pass Criteria**:
- Does NOT immediately conclude the table is empty
- Explains the three possible causes: row-level security filtering, genuinely empty table, or incorrect filters
- Suggests running `SELECT COUNT(*) FROM ...` without filters to diagnose
- Mentions checking scope/audit columns (Section 3) as a likely row-level-security cause

**Fail Criteria**:
- Concludes "yes, the table is empty" without checking row-level security
- Does not mention row-level security as a possible cause

---

## How to Run These Evals

1. Load `gold-catalog/SKILL.md` (with Section 0 configured for your workspace)
2. Submit each prompt above in a **fresh context** (no carryover from previous evals)
3. Compare the response against Pass / Fail criteria
4. If any eval fails, identify which GOLDEN RULE or section was not followed and refine the skill

> **Benchmark mode**: Run all 7 evals after each model update or skill edit. Track pass rate, elapsed time, and token usage to detect regressions.
